"""
Certinator AI — Executor Event Emission Helpers

Utilities for emitting ``AgentRunUpdateEvent`` instances so the
AG-UI event bridge forwards them to the CopilotKit frontend.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from agent_framework import (
    AgentRunResponseUpdate,
    AgentRunUpdateEvent,
    ChatMessage,
    FunctionCallContent,
    FunctionResultContent,
    Role,
    TextContent,
    WorkflowContext,
)

from executors.retry import safe_agent_run_stream

logger = logging.getLogger(__name__)


async def stream_and_accumulate(
    ctx: WorkflowContext,
    executor_id: str,
    agent: Any,
    messages: list[ChatMessage],
    fallback: str = "",
) -> str:
    """Stream agent tokens to the user while accumulating full text.

    Calls ``agent.run_stream()`` (via :func:`safe_agent_run_stream`)
    and emits each text chunk as an ``AgentRunUpdateEvent`` so the
    AG-UI event bridge forwards it to CopilotKit for progressive
    rendering.  Simultaneously accumulates the complete text for
    downstream processing (e.g. Critic validation).

    Parameters:
        ctx (WorkflowContext): Current workflow context.
        executor_id (str): Identifier of the emitting executor.
        agent (Any): Agent with ``run_stream()`` capability.
        messages (list[ChatMessage]): Prompt messages for the agent.
        fallback (str): Text returned when no content is streamed.

    Returns:
        str: The full accumulated response text, or *fallback* when
        the stream produced no text content.
    """
    accumulated = ""
    response_id = str(uuid4())
    async for update in safe_agent_run_stream(agent, messages):
        for content in getattr(update, "contents", None) or []:
            text = getattr(content, "text", None)
            if isinstance(text, str) and text:
                accumulated += text
                await ctx.add_event(
                    AgentRunUpdateEvent(
                        executor_id,
                        data=AgentRunResponseUpdate(
                            contents=[TextContent(text=text)],
                            role=Role.ASSISTANT,
                            response_id=response_id,
                        ),
                    )
                )
    return accumulated if accumulated.strip() else fallback


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


async def emit_response_streamed(
    ctx: WorkflowContext,
    executor_id: str,
    text: str,
    *,
    chunk_size: int = 120,
) -> None:
    """Emit text in progressive chunks for streaming UX (G17 Option B).

    Splits *text* on line boundaries into chunks of roughly
    *chunk_size* characters and emits each chunk as a separate
    ``AgentRunUpdateEvent`` sharing the same ``response_id``.
    The AG-UI event bridge relays each event to CopilotKit which
    appends the fragments, producing a progressive-render effect
    identical to real token streaming.

    Parameters:
        ctx (WorkflowContext): Current workflow context.
        executor_id (str): Identifier of the emitting executor.
        text (str): Full text to stream progressively.
        chunk_size (int): Target character count per chunk.
    """
    if not text:
        return

    response_id = str(uuid4())
    lines = text.split("\n")
    chunk: list[str] = []
    length = 0

    for line in lines:
        chunk.append(line)
        length += len(line) + 1  # +1 for the newline
        if length >= chunk_size:
            await ctx.add_event(
                AgentRunUpdateEvent(
                    executor_id,
                    data=AgentRunResponseUpdate(
                        contents=[TextContent(text="\n".join(chunk) + "\n")],
                        role=Role.ASSISTANT,
                        response_id=response_id,
                    ),
                )
            )
            chunk = []
            length = 0

    # Flush remaining lines.
    if chunk:
        await ctx.add_event(
            AgentRunUpdateEvent(
                executor_id,
                data=AgentRunResponseUpdate(
                    contents=[TextContent(text="\n".join(chunk))],
                    role=Role.ASSISTANT,
                    response_id=response_id,
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
    reasoning: str | None = None,
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
        reasoning (str | None): Optional human-readable explanation of
            why the agent made this decision at this step. Rendered as
            a muted sub-line in the WorkflowProgress UI component.
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
    if reasoning:
        progress["reasoning"] = reasoning

    await emit_state_snapshot(
        ctx=ctx,
        executor_id=active_executor,
        tool_name="update_workflow_progress",
        tool_argument="progress",
        state_value=progress,
    )
