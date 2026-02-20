"""
Certinator AI — Executor helpers

Shared utilities used by all executor modules.
"""

from typing import Any
from uuid import uuid4

from agent_framework import (
    AgentRunResponseUpdate,
    AgentRunUpdateEvent,
    Role,
    TextContent,
    WorkflowContext,
)


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


def extract_message_text(
    message: Any,
    fallback: str = "",
) -> str:
    """
    Extract text from a single chat message content list.

    Parameters:
        message (Any): Chat message with optional ``contents`` list.
        fallback (str): Text returned when no text content is found.

    Returns:
        str: Extracted text content or fallback.
    """
    contents = getattr(message, "contents", None) or []
    for content in reversed(contents):
        text = getattr(content, "text", None)
        if isinstance(text, str) and text.strip():
            return text
    return fallback


async def emit_response(
    ctx: WorkflowContext,
    executor_id: str,
    text: str,
) -> None:
    """
    Emit an AgentRunUpdateEvent so the HTTP server streams the response.

    Parameters:
        ctx (WorkflowContext): Current workflow context.
        executor_id (str): Identifier of the emitting executor.
        text (str): Response text to stream to the client.
    """
    await ctx.add_event(
        AgentRunUpdateEvent(
            executor_id,
            data=AgentRunResponseUpdate(
                contents=[TextContent(text=text)],
                role=Role.ASSISTANT,
                response_id=str(uuid4()),
            ),
        )
    )
