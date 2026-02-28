"""
Certinator AI — Executor helpers

Shared utilities used by all executor modules.

This package re-exports all public helpers from sub-modules so that
existing ``from executors import X`` imports continue to work.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Azure credential / auth error detection
# ---------------------------------------------------------------------------

# Marker strings that appear in Azure Identity / Azure SDK auth exceptions.
_AUTH_MARKERS: tuple[str, ...] = (
    "defaultazurecredential failed",
    "clientauthenticationerror",
    "please run 'az login'",
    "authentication unavailable",
    "no accounts were found in the cache",
    "credentialunavailableerror",
    "httpresponseerror",
    "status: 401",
    "status: 403",
)


def is_azure_auth_error(exc: BaseException) -> bool:
    """Return True when *exc* is an Azure credential / authentication failure.

    Checks both the exception class hierarchy (``ClientAuthenticationError``,
    ``CredentialUnavailableError``) and common marker strings that appear in
    ``DefaultAzureCredential`` error messages.

    Parameters:
        exc (BaseException): The exception to inspect.

    Returns:
        bool: True if the error is caused by missing or invalid Azure credentials.
    """
    # Class-name based detection (avoids hard import of azure.core.exceptions)
    exc_class_name = type(exc).__name__
    if exc_class_name in {
        "ClientAuthenticationError",
        "CredentialUnavailableError",
        "HttpResponseError",
    }:
        return True

    # Walk the exception chain (may be chained with __cause__ / __context__)
    current: BaseException | None = exc
    while current is not None:
        msg = str(current).lower()
        if any(marker in msg for marker in _AUTH_MARKERS):
            return True
        current = current.__cause__ or current.__context__
        # Avoid infinite loops on self-referencing chains
        if current is exc:
            break

    return False


_AZURE_AUTH_USER_MESSAGE: str = (
    "⚠️ **Azure authentication failed.** "
    "The app cannot connect to Azure AI Foundry because no valid credentials "
    "were found.\n\n"
    "**To fix this**, open a terminal and run:\n\n"
    "```\naz login\n```\n\n"
    "Then restart the application. "
    "For more details see: https://aka.ms/azsdk/python/identity/defaultazurecredential/troubleshoot"
)


def get_user_friendly_error(exc: BaseException, fallback: str) -> str:
    """Return a user-facing error message, with special handling for auth failures.

    If *exc* is an Azure credential / authentication error, a clear
    remediation message is returned. Otherwise *fallback* is returned.

    Parameters:
        exc (BaseException): The caught exception.
        fallback (str): Generic user-facing message for non-auth errors.

    Returns:
        str: Message safe to display in the chat UI.
    """
    if is_azure_auth_error(exc):
        return _AZURE_AUTH_USER_MESSAGE
    return fallback

# ---------------------------------------------------------------------------
# Re-exports from sub-modules
# ---------------------------------------------------------------------------


# Retry utilities
# Event emission helpers
from executors.events import (  # noqa: F401
    emit_response,
    emit_response_streamed,
    emit_state_snapshot,
    stream_and_accumulate,
    update_workflow_progress,
)
from executors.retry import (  # noqa: F401
    MAX_RETRY_ATTEMPTS,
    _is_transient_error,
    safe_agent_run,
    safe_agent_run_stream,
)

# ---------------------------------------------------------------------------
# extract_response_text — lightweight, kept here directly
# ---------------------------------------------------------------------------


def extract_response_text(
    response: Any,
    fallback: str = "",
) -> str:
    """
    Extract the latest assistant text from an agent response.

    Agent responses can include non-text content items (for example,
    function-call payloads). This helper searches message contents in
    reverse order and returns the newest available text segment.

    Parameters:
        response (Any): Agent response object with optional messages.
        fallback (str): Text returned when no text content is found.

    Returns:
        str: Extracted text content or fallback.
    """
    messages = getattr(response, "messages", None) or []

    for message in reversed(messages):
        contents = getattr(message, "contents", None) or []
        for content in reversed(contents):
            text = getattr(content, "text", None)
            if isinstance(text, str) and text.strip():
                return text

    return fallback


# ---------------------------------------------------------------------------
# Shared helper — affirmative reply detection
# ---------------------------------------------------------------------------

_AFFIRMATIVE_WORDS: frozenset[str] = frozenset(
    {"yes", "y", "sure", "ok", "okay", "please", "yeah"}
)


def is_affirmative_reply(text: str) -> bool:
    """Return True when *text* looks like the user is saying 'yes'.

    Used by HITL response handlers (study-plan offer, practice offer)
    to determine whether the student accepted or declined.

    Parameters:
        text (str): Raw reply string from the frontend.

    Returns:
        bool: True if the reply is affirmative.
    """
    reply = text.strip().lower()
    return reply in _AFFIRMATIVE_WORDS or "yes" in reply
