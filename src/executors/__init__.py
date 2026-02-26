"""
Certinator AI — Executor helpers

Shared utilities used by all executor modules.
"""

import json
import logging
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
from tenacity import (
    AsyncRetrying,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)

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
    retried with exponential backoff (1s → 30s). Non-transient errors
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
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=2, min=1, max=30),
        reraise=True,
    ):
        with attempt:
            attempt_number += 1
            if attempt_number > 1:
                logger.warning(
                    "safe_agent_run: retrying agent call (attempt %d/5)",
                    attempt_number,
                )
            return await agent.run(*args, **kwargs)


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
