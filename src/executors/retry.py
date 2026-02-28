"""
Certinator AI — Transient-Error Retry Utilities

Provides ``safe_agent_run`` and ``safe_agent_run_stream`` helpers that
wrap agent calls with exponential-backoff retry for transient failures
(timeouts, rate-limits, connection errors).
"""

import logging
from collections.abc import AsyncIterable
from typing import Any

from agent_framework import AgentRunResponseUpdate
from tenacity import (
    AsyncRetrying,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)

# Maximum number of retry attempts for transient errors
MAX_RETRY_ATTEMPTS = 5

# ---------------------------------------------------------------------------
# Transient error detection
# ---------------------------------------------------------------------------

_TRANSIENT_TYPES: tuple[type[BaseException], ...] = (
    TimeoutError,
    OSError,
    ConnectionError,
)

try:
    import httpx

    _TRANSIENT_TYPES = _TRANSIENT_TYPES + (httpx.TimeoutException,)
except ImportError:  # pragma: no cover — httpx not always installed
    pass

# Add OpenAI rate limit errors to transient types
try:
    import openai

    _TRANSIENT_TYPES = _TRANSIENT_TYPES + (
        openai.RateLimitError,
        openai.APITimeoutError,
        openai.APIConnectionError,
    )
except ImportError:  # pragma: no cover — openai not always installed
    pass

# Import ServiceResponseException for 429 detection
try:
    from agent_framework.exceptions import ServiceResponseException

    _HAS_SERVICE_RESPONSE_EXCEPTION = True
except ImportError:
    _HAS_SERVICE_RESPONSE_EXCEPTION = False


def _is_transient_error(exc: BaseException) -> bool:
    """Return True when *exc* is a transient network/timeout/rate-limit failure.

    Transient errors are retried with exponential backoff. All other
    exceptions are re-raised immediately after the first attempt.

    Parameters:
        exc (BaseException): The exception to classify.

    Returns:
        bool: True if the error is transient and should be retried.
    """
    # Direct match on known transient exception types
    if isinstance(exc, _TRANSIENT_TYPES):
        return True

    # Check if ServiceResponseException wraps a rate limit (429) error
    if _HAS_SERVICE_RESPONSE_EXCEPTION and isinstance(exc, ServiceResponseException):
        error_msg = str(exc).lower()
        if (
            "429" in error_msg
            or "too many requests" in error_msg
            or "rate" in error_msg
        ):
            return True

    return False


# ---------------------------------------------------------------------------
# Safe agent runner with retry
# ---------------------------------------------------------------------------


async def safe_agent_run(agent: Any, *args: Any, **kwargs: Any) -> Any:
    """Run an agent with automatic retry on transient failures.

    Wraps ``agent.run(*args, **kwargs)`` with up to 5 attempts.
    Transient errors (timeouts, connection errors, rate limits) are
    retried with exponential backoff (1s -> 30s). Non-transient errors
    are re-raised on the first attempt so callers can handle them
    immediately.

    Parameters:
        agent (Any): Agent instance with an async ``run()`` method.
        *args (Any): Positional arguments forwarded to ``agent.run()``.
        **kwargs (Any): Keyword arguments forwarded to ``agent.run()``.

    Returns:
        Any: The response from ``agent.run()``.

    Raises:
        Exception: Any exception not classified as transient, or the
            final transient exception after all retries are exhausted.
    """
    attempt_number = 0
    async for attempt in AsyncRetrying(
        retry=retry_if_exception(_is_transient_error),
        stop=stop_after_attempt(MAX_RETRY_ATTEMPTS),
        wait=wait_exponential(multiplier=2, min=1, max=30),
        reraise=True,
    ):
        with attempt:
            attempt_number += 1
            if attempt_number > 1:
                logger.warning(
                    "safe_agent_run: retrying agent call (attempt %d/%d)",
                    attempt_number,
                    MAX_RETRY_ATTEMPTS,
                )
            return await agent.run(*args, **kwargs)


# ---------------------------------------------------------------------------
# Streaming agent runner with retry
# ---------------------------------------------------------------------------


async def safe_agent_run_stream(
    agent: Any,
    *args: Any,
    **kwargs: Any,
) -> AsyncIterable[AgentRunResponseUpdate]:
    """Stream agent responses with automatic retry on transient failures.

    Wraps ``agent.run_stream(*args, **kwargs)`` with up to 5 attempts.
    On retry the entire stream is restarted — no partial state is
    committed because callers accumulate text independently.

    Parameters:
        agent (Any): Agent with an async ``run_stream()`` method.
        *args (Any): Positional arguments forwarded to
            ``agent.run_stream()``.
        **kwargs (Any): Keyword arguments forwarded to
            ``agent.run_stream()``.

    Yields:
        AgentRunResponseUpdate: Incremental response chunks.

    Raises:
        Exception: Any non-transient exception, or the final
            transient exception after all retries are exhausted.
    """
    attempt_number = 0
    async for attempt in AsyncRetrying(
        retry=retry_if_exception(_is_transient_error),
        stop=stop_after_attempt(MAX_RETRY_ATTEMPTS),
        wait=wait_exponential(multiplier=2, min=1, max=30),
        reraise=True,
    ):
        with attempt:
            attempt_number += 1
            if attempt_number > 1:
                logger.warning(
                    "safe_agent_run_stream: retrying (attempt %d/%d)",
                    attempt_number,
                    MAX_RETRY_ATTEMPTS,
                )
            async for update in agent.run_stream(*args, **kwargs):
                yield update
