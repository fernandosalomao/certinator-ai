"""
Certinator AI — Executor helpers

Shared utilities used by all executor modules.
"""

import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from agent_framework import (
    AgentRunResponseUpdate,
    AgentRunUpdateEvent,
    FunctionCallContent,
    FunctionResultContent,
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


async def emit_state_snapshot(
    ctx: WorkflowContext,
    executor_id: str,
    tool_name: str,
    tool_argument: str,
    state_value: Any,
) -> None:
    """
    Emit a synthetic tool call + result pair so the AG-UI event bridge
    converts it into a ``STATE_SNAPSHOT`` event for CopilotKit.

    Each call gets a fresh ``call_id``, creating one new render slot in the
    chat. ``useRenderToolCall`` on the frontend renders each slot as a single
    step row, so the agent's progress appears as a growing list of steps.

    Parameters:
        ctx (WorkflowContext): Current workflow context.
        executor_id (str): Identifier of the calling executor.
        tool_name (str): Synthetic tool name matching ``predict_state_config``.
        tool_argument (str): Argument name matching ``predict_state_config``.
        state_value (Any): JSON-serialisable value to send as state.
    """
    # Each call gets a fresh call_id — each progress update becomes its own
    # chat slot rendered by useRenderToolCall as a single step row.
    call_id = str(uuid4())
    arguments = json.dumps({tool_argument: state_value})

    # FunctionCallContent — opens the render slot and triggers StateDeltaEvent.
    await ctx.add_event(
        AgentRunUpdateEvent(
            executor_id,
            data=AgentRunResponseUpdate(
                contents=[
                    FunctionCallContent(
                        call_id=call_id,
                        name=tool_name,
                        arguments=arguments,
                    )
                ],
                role=Role.ASSISTANT,
                response_id=str(uuid4()),
            ),
        )
    )

    # FunctionResultContent — triggers StateSnapshotEvent emission.
    await ctx.add_event(
        AgentRunUpdateEvent(
            executor_id,
            data=AgentRunResponseUpdate(
                contents=[
                    FunctionResultContent(
                        call_id=call_id,
                        result="State updated.",
                    )
                ],
                role=Role.TOOL,
                response_id=str(uuid4()),
            ),
        )
    )


async def update_workflow_progress(
    ctx: WorkflowContext,
    route: str,
    active_executor: str,
    message: str,
    current_step: int,
    total_steps: int,
    status: str = "in_progress",
) -> None:
    """Stream the current workflow progress to the CopilotKit frontend.

    Emits a progress snapshot on every call. The frontend renders one
    step row per tool call via ``useRenderToolCall``. Each row reads the
    live agent state to decide whether it has been superseded (done).

    Parameters:
        ctx (WorkflowContext): Current workflow context.
        route (str): Active route (e.g. ``study_plan``).
        active_executor (str): Executor currently processing work.
        message (str): Human-readable step status text.
        current_step (int): 1-based current step index.
        total_steps (int): Total expected steps for the route.
        status (str): Progress status value.
    """
    safe_total = max(total_steps, 1)
    safe_step = min(max(current_step, 1), safe_total)

    progress = {
        "route": route,
        "active_executor": active_executor,
        "message": message,
        "current_step": safe_step,
        "total_steps": safe_total,
        "status": status,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    await emit_state_snapshot(
        ctx=ctx,
        executor_id=active_executor,
        tool_name="update_workflow_progress",
        tool_argument="progress",
        state_value=progress,
    )
