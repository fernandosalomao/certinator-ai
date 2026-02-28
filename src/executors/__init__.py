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
