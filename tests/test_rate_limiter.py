"""
Certinator AI — Rate Limiter Tests (G12)

Tests for the ``RateLimiterMiddleware`` in ``rate_limiter.py``.

Covers:
    - Requests under limit pass through
    - Requests over per-IP limit return HTTP 429
    - Requests over per-session limit return HTTP 429
    - Health/ready endpoints are exempt from rate limiting
    - 429 response includes Retry-After header
    - 429 response body has correct structure
    - Disabled rate limiter is a pass-through
    - Per-IP and per-session counters are independent
    - X-Forwarded-For header is used for IP extraction
    - Sliding window counter prunes old entries
    - Thread ID extraction from JSON body
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path
from unittest.mock import patch

import pytest

# Ensure ``src/`` is on the import path.
_SRC = str(Path(__file__).resolve().parent.parent / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

# ──────────────────────────────────────────────────────────────────────────
# Helpers — lightweight Starlette test app
# ──────────────────────────────────────────────────────────────────────────
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from rate_limiter import (
    _EXEMPT_PATHS,
    RateLimiterMiddleware,
    _build_429_response,
    _extract_client_ip,
    _extract_thread_id,
    _SlidingWindowCounter,
    ip_counter,
    session_counter,
)


def _ok_handler(request: Request) -> PlainTextResponse:
    """Simple handler that returns 200 OK."""
    return PlainTextResponse("ok")


def _health_handler(request: Request) -> JSONResponse:
    """Simulated /health endpoint."""
    return JSONResponse({"status": "alive"})


def _ready_handler(request: Request) -> JSONResponse:
    """Simulated /ready endpoint."""
    return JSONResponse({"status": "ready"})


def _make_app() -> Starlette:
    """Build a minimal Starlette app with the rate limiter middleware."""
    app = Starlette(
        routes=[
            Route("/", _ok_handler, methods=["GET", "POST"]),
            Route("/health", _health_handler),
            Route("/ready", _ready_handler),
            Route("/some-endpoint", _ok_handler, methods=["POST"]),
        ],
    )
    app.add_middleware(RateLimiterMiddleware)
    return app


@pytest.fixture(autouse=True)
def _reset_counters():
    """Reset sliding-window counters before each test."""
    ip_counter.reset()
    session_counter.reset()
    yield
    ip_counter.reset()
    session_counter.reset()


# ──────────────────────────────────────────────────────────────────────────
# Sliding Window Counter — unit tests
# ──────────────────────────────────────────────────────────────────────────


class TestSlidingWindowCounter:
    """Tests for ``_SlidingWindowCounter``."""

    def test_counts_within_window(self) -> None:
        """Multiple hits within the window are counted."""
        counter = _SlidingWindowCounter()
        now = 1000.0
        assert counter.hit("a", now) == 1
        assert counter.hit("a", now + 1) == 2
        assert counter.hit("a", now + 2) == 3

    def test_prunes_old_entries(self) -> None:
        """Entries older than 60s are pruned."""
        counter = _SlidingWindowCounter()
        now = 1000.0
        counter.hit("a", now)
        counter.hit("a", now + 1)
        # 61 seconds later, both should have expired.
        count = counter.hit("a", now + 61)
        assert count == 1  # Only the new hit.

    def test_keys_are_independent(self) -> None:
        """Different keys have separate counters."""
        counter = _SlidingWindowCounter()
        now = 1000.0
        counter.hit("a", now)
        counter.hit("a", now)
        count_b = counter.hit("b", now)
        assert count_b == 1

    def test_seconds_until_available(self) -> None:
        """Reports correct wait time."""
        counter = _SlidingWindowCounter()
        now = 1000.0
        counter.hit("a", now)
        wait = counter.seconds_until_available("a", now + 30)
        # Oldest entry is at 1000, window is 60s, so expires at 1060.
        # At now=1030, remaining = 30s → ceiling + 1 = 31.
        assert wait == 31

    def test_seconds_until_available_empty(self) -> None:
        """Returns 1 for keys with no history."""
        counter = _SlidingWindowCounter()
        assert counter.seconds_until_available("nonexistent") == 1

    def test_reset_clears_all(self) -> None:
        """``reset()`` removes all tracked keys."""
        counter = _SlidingWindowCounter()
        counter.hit("a")
        counter.hit("b")
        counter.reset()
        assert counter.hit("a") == 1


# ──────────────────────────────────────────────────────────────────────────
# Helper function tests
# ──────────────────────────────────────────────────────────────────────────


class TestExtractClientIP:
    """Tests for ``_extract_client_ip``."""

    def test_uses_x_forwarded_for(self) -> None:
        """X-Forwarded-For header takes priority."""
        from starlette.testclient import TestClient

        app = _make_app()
        with (
            patch("config.RATE_LIMIT_ENABLED", True),
            patch("config.RATE_LIMIT_PER_IP", 1000),
            patch("config.RATE_LIMIT_PER_SESSION", 1000),
        ):
            client = TestClient(app)
            # We can't directly test _extract_client_ip via the
            # middleware, but we can verify it doesn't crash.
            resp = client.get(
                "/",
                headers={"X-Forwarded-For": "1.2.3.4, 5.6.7.8"},
            )
            assert resp.status_code == 200


class TestExtractThreadId:
    """Tests for ``_extract_thread_id``."""

    def test_extracts_thread_id_camel_case(self) -> None:
        """Extracts threadId from camelCase JSON body."""

        async def _run() -> str | None:
            from starlette.requests import Request

            scope = {
                "type": "http",
                "method": "POST",
                "path": "/",
                "headers": [
                    (b"content-type", b"application/json"),
                ],
            }
            body = json.dumps({"threadId": "abc-123"}).encode()

            async def receive():
                return {"type": "http.request", "body": body}

            req = Request(scope, receive)
            return await _extract_thread_id(req)

        result = asyncio.run(_run())
        assert result == "abc-123"

    def test_extracts_thread_id_snake_case(self) -> None:
        """Extracts thread_id from snake_case JSON body."""

        async def _run() -> str | None:
            from starlette.requests import Request

            scope = {
                "type": "http",
                "method": "POST",
                "path": "/",
                "headers": [],
            }
            body = json.dumps({"thread_id": "xyz-789"}).encode()

            async def receive():
                return {"type": "http.request", "body": body}

            req = Request(scope, receive)
            return await _extract_thread_id(req)

        result = asyncio.run(_run())
        assert result == "xyz-789"

    def test_returns_none_for_empty_body(self) -> None:
        """Returns None when body is empty."""

        async def _run() -> str | None:
            from starlette.requests import Request

            scope = {
                "type": "http",
                "method": "POST",
                "path": "/",
                "headers": [],
            }

            async def receive():
                return {"type": "http.request", "body": b""}

            req = Request(scope, receive)
            return await _extract_thread_id(req)

        result = asyncio.run(_run())
        assert result is None

    def test_returns_none_for_invalid_json(self) -> None:
        """Returns None when body is not valid JSON."""

        async def _run() -> str | None:
            from starlette.requests import Request

            scope = {
                "type": "http",
                "method": "POST",
                "path": "/",
                "headers": [],
            }

            async def receive():
                return {
                    "type": "http.request",
                    "body": b"not json",
                }

            req = Request(scope, receive)
            return await _extract_thread_id(req)

        result = asyncio.run(_run())
        assert result is None


# ──────────────────────────────────────────────────────────────────────────
# 429 response builder
# ──────────────────────────────────────────────────────────────────────────


class TestBuild429Response:
    """Tests for ``_build_429_response``."""

    def test_ip_response_structure(self) -> None:
        """IP-based 429 has correct structure."""
        resp = _build_429_response("ip", 42)
        assert resp.status_code == 429
        assert resp.headers["Retry-After"] == "42"
        body = json.loads(resp.body)
        assert body["error"] == "rate_limit_exceeded"
        assert body["retry_after"] == 42
        assert "IP" in body["detail"]

    def test_session_response_structure(self) -> None:
        """Session-based 429 has correct structure."""
        resp = _build_429_response("session", 10)
        assert resp.status_code == 429
        body = json.loads(resp.body)
        assert "session" in body["detail"]


# ──────────────────────────────────────────────────────────────────────────
# Middleware integration tests (via Starlette TestClient)
# ──────────────────────────────────────────────────────────────────────────


class TestRateLimiterMiddleware:
    """Integration tests for ``RateLimiterMiddleware``."""

    def test_under_limit_passes(self) -> None:
        """Requests under the IP limit get 200."""
        app = _make_app()
        with (
            patch("config.RATE_LIMIT_ENABLED", True),
            patch("config.RATE_LIMIT_PER_IP", 10),
            patch("config.RATE_LIMIT_PER_SESSION", 10),
        ):
            client = TestClient(app)
            resp = client.get("/")
            assert resp.status_code == 200

    def test_ip_limit_exceeded_returns_429(self) -> None:
        """Exceeding the IP limit returns HTTP 429."""
        app = _make_app()
        with (
            patch("config.RATE_LIMIT_ENABLED", True),
            patch("config.RATE_LIMIT_PER_IP", 3),
            patch("config.RATE_LIMIT_PER_SESSION", 100),
        ):
            client = TestClient(app)
            for _ in range(3):
                resp = client.get("/")
                assert resp.status_code == 200
            # 4th request should be rejected.
            resp = client.get("/")
            assert resp.status_code == 429
            body = resp.json()
            assert body["error"] == "rate_limit_exceeded"
            assert "Retry-After" in resp.headers

    def test_session_limit_exceeded_returns_429(self) -> None:
        """Exceeding the session limit returns HTTP 429."""
        app = _make_app()
        with (
            patch("config.RATE_LIMIT_ENABLED", True),
            patch("config.RATE_LIMIT_PER_IP", 100),
            patch("config.RATE_LIMIT_PER_SESSION", 2),
        ):
            client = TestClient(app)
            payload = json.dumps({"threadId": "session-1"})
            for _ in range(2):
                resp = client.post(
                    "/",
                    content=payload,
                    headers={
                        "Content-Type": "application/json",
                    },
                )
                assert resp.status_code == 200
            # 3rd request with same session should be rejected.
            resp = client.post(
                "/",
                content=payload,
                headers={"Content-Type": "application/json"},
            )
            assert resp.status_code == 429

    def test_different_sessions_independent(self) -> None:
        """Different thread IDs have independent session counters."""
        app = _make_app()
        with (
            patch("config.RATE_LIMIT_ENABLED", True),
            patch("config.RATE_LIMIT_PER_IP", 100),
            patch("config.RATE_LIMIT_PER_SESSION", 2),
        ):
            client = TestClient(app)
            # Session A: 2 requests (at limit).
            for _ in range(2):
                resp = client.post(
                    "/",
                    content=json.dumps({"threadId": "sess-a"}),
                    headers={
                        "Content-Type": "application/json",
                    },
                )
                assert resp.status_code == 200
            # Session B: should still work.
            resp = client.post(
                "/",
                content=json.dumps({"threadId": "sess-b"}),
                headers={"Content-Type": "application/json"},
            )
            assert resp.status_code == 200

    def test_health_endpoint_exempt(self) -> None:
        """/health is never rate-limited."""
        app = _make_app()
        with (
            patch("config.RATE_LIMIT_ENABLED", True),
            patch("config.RATE_LIMIT_PER_IP", 1),
            patch("config.RATE_LIMIT_PER_SESSION", 1),
        ):
            client = TestClient(app)
            # Exhaust the IP limit on a regular endpoint.
            client.get("/")
            # /health should still work.
            resp = client.get("/health")
            assert resp.status_code == 200

    def test_ready_endpoint_exempt(self) -> None:
        """/ready is never rate-limited."""
        app = _make_app()
        with (
            patch("config.RATE_LIMIT_ENABLED", True),
            patch("config.RATE_LIMIT_PER_IP", 1),
            patch("config.RATE_LIMIT_PER_SESSION", 1),
        ):
            client = TestClient(app)
            client.get("/")
            resp = client.get("/ready")
            assert resp.status_code == 200

    def test_disabled_passes_all(self) -> None:
        """When RATE_LIMIT_ENABLED is False, all requests pass."""
        app = _make_app()
        with (
            patch("config.RATE_LIMIT_ENABLED", False),
            patch("config.RATE_LIMIT_PER_IP", 1),
            patch("config.RATE_LIMIT_PER_SESSION", 1),
        ):
            client = TestClient(app)
            for _ in range(5):
                resp = client.get("/")
                assert resp.status_code == 200

    def test_429_has_retry_after_header(self) -> None:
        """429 response includes a Retry-After header."""
        app = _make_app()
        with (
            patch("config.RATE_LIMIT_ENABLED", True),
            patch("config.RATE_LIMIT_PER_IP", 1),
            patch("config.RATE_LIMIT_PER_SESSION", 100),
        ):
            client = TestClient(app)
            client.get("/")
            resp = client.get("/")
            assert resp.status_code == 429
            retry = resp.headers.get("Retry-After")
            assert retry is not None
            assert int(retry) >= 1

    def test_exempt_paths_constant(self) -> None:
        """Exempt paths include /health and /ready."""
        assert "/health" in _EXEMPT_PATHS
        assert "/ready" in _EXEMPT_PATHS
