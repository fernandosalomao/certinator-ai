"""
Certinator AI — Thread Store

In-memory persistence for conversation threads.

Maps CopilotKit thread_id → AgentThread instance.  Threads persist
across requests within the same server process, enabling conversation
continuity.

WARNING: Lost on server restart.  Production should use Redis/DB.
"""

import logging

from agent_framework import AgentThread

logger = logging.getLogger(__name__)

_thread_store: dict[str, AgentThread] = {}


def get_or_create_thread(thread_id: str, run_id: str | None = None) -> AgentThread:
    """
    Retrieve an existing thread or create a new one.

    Parameters:
        thread_id: The CopilotKit thread ID (from frontend).
        run_id: Optional AG-UI run ID for metadata.

    Returns:
        AgentThread: Existing or newly created thread.
    """
    if thread_id in _thread_store:
        thread = _thread_store[thread_id]
        logger.info(
            "Thread store: retrieved existing thread_id=%s (history_len=%d)",
            thread_id,
            len(getattr(thread, "messages", []) or []),
        )
        # Update run_id in metadata for current request
        if run_id and hasattr(thread, "metadata"):
            thread.metadata["ag_ui_run_id"] = run_id
        return thread

    # Create new thread
    thread = AgentThread()
    thread.metadata = {
        "ag_ui_thread_id": thread_id,
        "ag_ui_run_id": run_id or "",
    }
    _thread_store[thread_id] = thread
    logger.info(
        "Thread store: created new thread_id=%s (total_threads=%d)",
        thread_id,
        len(_thread_store),
    )
    return thread


def get_thread_count() -> int:
    """Return the number of threads in the store.

    Returns:
        int: Current thread count.
    """
    return len(_thread_store)
