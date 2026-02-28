"""
Certinator AI — Rate Limiting Middleware (G12)

Custom FastAPI middleware that enforces per-IP and per-session
(thread_id) sliding-window rate limits.  Returns HTTP 429 with a
human-readable message and ``Retry-After`` header when limits are
exceeded.

Design decisions:
    - In-memory sliding window (60-second buckets) — matches the
      current in-memory thread store.  When G8 (persistent thread
      store) is implemented, rate limiting can move to Redis too.
    - Health / readiness probes (``/health``, ``/ready``) are
      always exempt.
    - Session key is extracted from the AG-UI JSON request body's
      ``threadId`` field.  Falls back to IP-only if body parsing
      fails.

Configuration (env vars — see ``config.py``):
    RATE_LIMIT_ENABLED       — toggle on/off (default: true)
    RATE_LIMIT_PER_SESSION   — requests/min per thread_id (default: 20)
    RATE_LIMIT_PER_IP        — requests/min per IP (default: 60)
"""

from __future__ import annotations

import json
import logging
import time
from collections import defaultdict

from starlette.middleware.base import (
    BaseHTTPMiddleware,
    RequestResponseEndpoint,
)
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = logging.getLogger(__name__)

# Paths that are never rate-limited (ops probes).
_EXEMPT_PATHS: frozenset[str] = frozenset({"/health", "/ready"})

# Sliding-window duration in seconds.
_WINDOW_SECONDS: float = 60.0


class _SlidingWindowCounter:
    """In-memory sliding-window request counter.

    Stores a list of monotonic timestamps per key and counts how
    many fall within the last ``_WINDOW_SECONDS``.  Old entries are
    pruned lazily on each ``hit()`` call.
    """

    def __init__(self) -> None:
        self._buckets: dict[str, list[float]] = defaultdict(list)

    def hit(self, key: str, now: float | None = None) -> int:
        """Record a hit and return the request count within the window.

        Parameters:
            key: Identifier (IP address or thread_id).
            now: Current monotonic time (injectable for tests).

        Returns:
            int: Number of requests in the current window
                 **including** this one.
        """
        if now is None:
            now = time.monotonic()
        bucket = self._buckets[key]
        # Prune entries outside the window.
        cutoff = now - _WINDOW_SECONDS
        self._buckets[key] = [t for t in bucket if t > cutoff]
        self._buckets[key].append(now)
        return len(self._buckets[key])

    def seconds_until_available(
        self,
        key: str,
        now: float | None = None,
    ) -> int:
        """Seconds until at least one slot is freed for *key*.

        Returns:
            int: Ceiling of time until the oldest entry in the
                 window expires.  Minimum 1.
        """
        if now is None:
            now = time.monotonic()
        bucket = self._buckets.get(key, [])
        if not bucket:
            return 1
        oldest_in_window = min(bucket)
        remaining = _WINDOW_SECONDS - (now - oldest_in_window)
        return max(1, int(remaining) + 1)

    def reset(self) -> None:
        """Clear all counters (useful in tests)."""
        self._buckets.clear()


# Module-level counters (shared across requests within the process).
ip_counter = _SlidingWindowCounter()
session_counter = _SlidingWindowCounter()


def _extract_client_ip(request: Request) -> str:
    """Best-effort client IP extraction.

    Checks ``X-Forwarded-For`` first (common behind reverse
    proxies), then falls back to ``request.client.host``.

    Parameters:
        request: The incoming Starlette request.

    Returns:
        str: Client IP address, or ``"unknown"`` if unavailable.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        # First IP in the chain is the original client.
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


async def _extract_thread_id(request: Request) -> str | None:
    """Try to extract ``threadId`` from the JSON request body.

    AG-UI sends ``threadId`` in the top-level JSON payload.
    Returns ``None`` if parsing fails or the field is absent.

    Parameters:
        request: The incoming Starlette request.

    Returns:
        str | None: The thread ID if found, otherwise None.
    """
    try:
        body = await request.body()
        if not body:
            return None
        data = json.loads(body)
        return data.get("threadId") or data.get("thread_id")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None


def _build_429_response(
    limit_type: str,
    retry_after: int,
) -> JSONResponse:
    """Build a standardised HTTP 429 response.

    Parameters:
        limit_type: ``"ip"`` or ``"session"``.
        retry_after: Seconds until a retry is allowed.

    Returns:
        JSONResponse: 429 response with ``Retry-After`` header.
    """
    if limit_type == "session":
        detail = (
            "You've sent too many requests in this session. "
            "Please wait a moment before trying again."
        )
    else:
        detail = (
            "Too many requests from your IP address. "
            "Please wait a moment before trying again."
        )

    return JSONResponse(
        status_code=429,
        content={
            "error": "rate_limit_exceeded",
            "detail": detail,
            "retry_after": retry_after,
        },
        headers={"Retry-After": str(retry_after)},
    )


class RateLimiterMiddleware(BaseHTTPMiddleware):
    """Starlette middleware enforcing per-IP and per-session rate limits.

    Exempt paths (``/health``, ``/ready``) are always forwarded.
    When ``RATE_LIMIT_ENABLED`` is ``False``, the middleware is a
    pass-through.

    Order of checks:
    1. IP rate limit (broader, higher cap)
    2. Session rate limit (narrower, lower cap — only when
       ``threadId`` is present in the request body)

    On rejection, an OTel counter (``certinator.rate_limit.rejections``)
    is incremented with ``limit_type`` and ``client_ip`` attributes.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        """Process an incoming request through rate-limit checks.

        Parameters:
            request: The incoming HTTP request.
            call_next: Callback to forward the request downstream.

        Returns:
            Response: Either the downstream response or HTTP 429.
        """
        # Import config lazily to allow patching in tests.
        from config import (
            RATE_LIMIT_ENABLED,
            RATE_LIMIT_PER_IP,
            RATE_LIMIT_PER_SESSION,
        )

        # Skip if disabled or path is exempt.
        if not RATE_LIMIT_ENABLED:
            return await call_next(request)

        if request.url.path in _EXEMPT_PATHS:
            return await call_next(request)

        client_ip = _extract_client_ip(request)
        now = time.monotonic()

        # ── IP rate limit ──────────────────────────────────────
        ip_count = ip_counter.hit(client_ip, now)
        if ip_count > RATE_LIMIT_PER_IP:
            retry_after = ip_counter.seconds_until_available(client_ip, now)
            logger.warning(
                "Rate limit exceeded (IP): ip=%s count=%d limit=%d",
                client_ip,
                ip_count,
                RATE_LIMIT_PER_IP,
            )
            _record_rejection("ip", client_ip)
            return _build_429_response("ip", retry_after)

        # ── Session rate limit ─────────────────────────────────
        thread_id = await _extract_thread_id(request)
        if thread_id:
            session_count = session_counter.hit(thread_id, now)
            if session_count > RATE_LIMIT_PER_SESSION:
                retry_after = session_counter.seconds_until_available(thread_id, now)
                logger.warning(
                    "Rate limit exceeded (session): thread_id=%s count=%d limit=%d",
                    thread_id,
                    session_count,
                    RATE_LIMIT_PER_SESSION,
                )
                _record_rejection("session", client_ip)
                return _build_429_response("session", retry_after)

        return await call_next(request)


def _record_rejection(limit_type: str, client_ip: str) -> None:
    """Increment the OTel rate-limit rejection counter.

    Parameters:
        limit_type: ``"ip"`` or ``"session"``.
        client_ip: The client IP address for attribution.
    """
    try:
        from metrics import rate_limit_rejections

        rate_limit_rejections.add(
            1,
            {"limit_type": limit_type, "client_ip": client_ip},
        )
    except Exception:
        # Metrics are best-effort; never block the request path.
        pass
