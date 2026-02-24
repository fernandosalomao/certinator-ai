"""
Certinator AI — Main Entrypoint

Multi-agent system for Microsoft certification exam preparation.
Runs as an HTTP server for use with AI Toolkit Agent Inspector,
or in CLI mode for quick testing.

Usage:
    # HTTP server mode (default, used by agentdev / Agent Inspector)
    python src/app.py

    # CLI mode (interactive terminal)
    python src/app.py --cli
"""

import asyncio
import logging
from collections.abc import AsyncGenerator
from typing import Any

from ag_ui.core import BaseEvent
from agent_framework import (
    FunctionResultContent,
    Role,
)
from agent_framework.observability import configure_otel_providers
from agent_framework_ag_ui import AgentFrameworkAgent
from agent_framework_ag_ui._orchestrators import (
    DefaultOrchestrator,
    ExecutionContext,
    HumanInTheLoopOrchestrator,
    Orchestrator,
)
from dotenv import load_dotenv
from opentelemetry import metrics as otel_metrics
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import (
    OTLPMetricExporter,
)
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import (
    ConsoleMetricExporter,
    PeriodicExportingMetricReader,
)

# Configure logging so our debug output is visible
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)


def _build_predict_state_config() -> dict[str, dict[str, str]]:
    """Return AG-UI predict_state_config mapping synthetic tool calls to state keys."""
    return {
        "workflow_progress": {
            "tool": "update_workflow_progress",
            "tool_argument": "progress",
        },
        "active_quiz_state": {
            "tool": "update_active_quiz_state",
            "tool_argument": "quiz_state",
        },
        "post_study_plan_context": {
            "tool": "update_post_study_plan_context",
            "tool_argument": "context",
        },
    }


def _build_state_schema() -> dict[str, dict[str, str]]:
    """Return AG-UI state schema used by frontend shared-state hooks."""
    return {
        "active_quiz_state": {
            "type": "object",
            "description": "Current quiz session state",
        },
        "post_study_plan_context": {
            "type": "object",
            "description": "Post-study-plan context for HITL practice offer",
        },
        "workflow_progress": {
            "type": "object",
            "description": "Current multi-step workflow execution progress",
        },
    }


# Load environment variables (override=True for deployed environments)
load_dotenv(override=True)

# ---------------------------------------------------------------------------
# OpenTelemetry Tracing
# ---------------------------------------------------------------------------
configure_otel_providers()

# ---------------------------------------------------------------------------
# OpenTelemetry Metrics
# ---------------------------------------------------------------------------
# configure_otel_providers only registers a TracerProvider.  We register a
# MeterProvider separately so that the custom instruments in metrics.py
# actually export data.
#
# Two readers are used:
#   1. OTLPMetricExporter → same gRPC collector on port 4317 that receives
#      traces.  Metrics appear in any OTLP-compatible backend (e.g. the AI
#      Toolkit collector, piped to Prometheus/Grafana).
# _metric_readers = [
#     PeriodicExportingMetricReader(
#         OTLPMetricExporter(endpoint="http://localhost:4317", insecure=True),
#         export_interval_millis=60_000,  # flush every 60 s
#     )
# ]
# otel_metrics.set_meter_provider(MeterProvider(metric_readers=_metric_readers))


# ---------------------------------------------------------------------------
# Custom Orchestrator: request_info HITL message filter
# ---------------------------------------------------------------------------
# CopilotKit's AG-UI bridge sends the *full* conversation history on
# every turn.  When a MAF workflow agent has pending ``request_info``
# calls, the SDK's ``WorkflowAgent._extract_function_responses()``
# raises ``AgentExecutionException`` if *any* message contains
# non-function content (e.g. TextContent from an earlier user turn).
#
# This orchestrator is placed **first** in the chain so that, when
# ``pending_requests`` exist, it converts only the ``role: tool``
# raw AG-UI messages to ``FunctionResultContent``-carrying objects and
# **directly** to ``WorkflowAgent.run_stream()``, completely
# bypassing ``DefaultOrchestrator`` whose ``sanitize_tool_history``
# would drop orphan tool results that lack a preceding assistant
# tool-call message.
# ---------------------------------------------------------------------------


class RequestInfoOrchestrator(Orchestrator):
    """Clean up request_info HITL artifacts and handle responses.

    Placed first in the orchestrator chain.  This orchestrator
    handles two scenarios:

    **A) Pending requests exist** — the user just submitted an
    HITL response (quiz answers, study plan accept/reject).
    Converts only matching ``role: "tool"`` messages and passes
    them directly to ``WorkflowAgent.run_stream()``, bypassing
    ``DefaultOrchestrator``'s ``sanitize_tool_history`` which
    would drop orphan tool results.

    **B) No pending requests** — a normal user message, but the
    conversation history may contain stale ``request_info`` tool
    call/result pairs from previous HITL exchanges.  These cause
    ``KeyError`` in ``_prepare_messages_for_openai`` because the
    tool result's ``call_id`` has no matching ``FunctionCallContent``
    after message sanitisation.  Strips those artifacts from
    ``input_data["messages"]`` then delegates to
    ``DefaultOrchestrator``.
    """

    # ── helpers ────────────────────────────────────────────────────

    # Names of synthetic predict-state tools injected by AG-UI that must
    # never be forwarded to the LLM as conversation history.
    _PREDICT_STATE_TOOL_NAMES: frozenset[str] = frozenset(
        {
            "update_workflow_progress",
            "update_active_quiz_state",
            "update_post_study_plan_context",
        }
    )

    @staticmethod
    def _find_request_info_call_ids(
        raw_messages: list[dict],
    ) -> set[str]:
        """Collect tool-call IDs for request_info calls."""
        ids: set[str] = set()
        for msg in raw_messages:
            if msg.get("role") != "assistant":
                continue
            for tc in msg.get("tool_calls") or msg.get("toolCalls") or []:
                fn = tc.get("function") or {}
                if fn.get("name") == "request_info":
                    tc_id = tc.get("id", "")
                    if tc_id:
                        ids.add(tc_id)
        return ids

    @classmethod
    def _find_predict_state_call_ids(
        cls,
        raw_messages: list[dict],
    ) -> set[str]:
        """Collect tool-call IDs for predict-state synthetic tools.

        These are tools like ``update_workflow_progress`` that are
        injected by the AG-UI bridge for shared-state updates.  They
        must be stripped from conversation history before the messages
        are forwarded to the LLM, otherwise
        ``_prepare_messages_for_openai`` raises a ``KeyError`` because
        the matching ``FunctionCallContent`` is removed by
        ``sanitize_tool_history`` while the orphaned tool-result is
        kept.
        """
        ids: set[str] = set()
        for msg in raw_messages:
            if msg.get("role") != "assistant":
                continue
            for tc in msg.get("tool_calls") or msg.get("toolCalls") or []:
                fn = tc.get("function") or {}
                if fn.get("name") in cls._PREDICT_STATE_TOOL_NAMES:
                    tc_id = tc.get("id", "")
                    if tc_id:
                        ids.add(tc_id)
        return ids

    @staticmethod
    def _strip_request_info_artifacts(
        raw_messages: list[dict],
        request_info_ids: set[str],
    ) -> list[dict]:
        """Remove request_info tool calls and their results.

        Returns a new list of raw AG-UI messages with:
        - ``request_info`` entries removed from assistant
          ``tool_calls`` arrays.
        - ``role: "tool"`` messages whose ``tool_call_id``
          matches a request_info call removed entirely.
        - Assistant messages left empty after stripping are
          dropped (unless they have text content).
        """
        cleaned: list[dict] = []
        for msg in raw_messages:
            role = msg.get("role", "")

            # Drop tool results for request_info calls
            if role == "tool":
                tc_id = (
                    msg.get("tool_call_id")
                    or msg.get("toolCallId")
                    or msg.get("actionExecutionId")
                    or ""
                )
                if tc_id in request_info_ids:
                    continue
                cleaned.append(msg)
                continue

            # Strip request_info entries from assistant tool_calls
            if role == "assistant":
                tc_key = (
                    "tool_calls"
                    if "tool_calls" in msg
                    else "toolCalls"
                    if "toolCalls" in msg
                    else None
                )
                if tc_key:
                    original_tcs = msg[tc_key] or []
                    filtered_tcs = [
                        tc
                        for tc in original_tcs
                        if tc.get("id", "") not in request_info_ids
                    ]
                    if len(filtered_tcs) < len(original_tcs):
                        msg = dict(msg)  # shallow copy
                        if filtered_tcs:
                            msg[tc_key] = filtered_tcs
                        else:
                            msg.pop(tc_key, None)
                            # If no text content either, drop msg
                            content = msg.get("content", "")
                            if not content:
                                continue
                cleaned.append(msg)
                continue

            cleaned.append(msg)
        return cleaned

    # ── Orchestrator interface ────────────────────────────────────

    def can_handle(self, context: ExecutionContext) -> bool:
        """Always handle — we clean every request."""
        agent = context.agent
        pending = getattr(agent, "pending_requests", None) or {}
        raw_msgs = context.input_data.get("messages", [])
        ri_ids = self._find_request_info_call_ids(raw_msgs)
        logger.info(
            "RequestInfoOrchestrator.can_handle: "
            "pending=%d, request_info_ids=%d → True",
            len(pending),
            len(ri_ids),
        )
        return True

    async def run(
        self,
        context: ExecutionContext,
    ) -> AsyncGenerator[BaseEvent, None]:
        """Route to direct-call or cleanup-and-delegate."""
        agent = context.agent
        pending = getattr(agent, "pending_requests", None) or {}

        if pending:
            async for event in self._run_with_pending(context):
                yield event
        else:
            async for event in self._run_cleanup(context):
                yield event

    # ── Path A: pending requests (direct call) ────────────────────

    async def _run_with_pending(
        self,
        context: ExecutionContext,
    ) -> AsyncGenerator[BaseEvent, None]:
        """Handle HITL response by calling agent.run_stream directly."""
        from agent_framework import AgentThread
        from agent_framework_ag_ui._events import AgentFrameworkEventBridge
        from agent_framework_ag_ui._message_adapters import (
            agui_messages_to_agent_framework,
        )

        raw = context.input_data.get("messages", [])
        tool_only_raw = [m for m in raw if m.get("role") == "tool"]
        logger.info(
            "RequestInfoOrchestrator[pending]: %d/%d raw messages are tool-role",
            len(tool_only_raw),
            len(raw),
        )

        if not tool_only_raw:
            logger.warning(
                "RequestInfoOrchestrator[pending]: no tool "
                "messages — delegating to DefaultOrchestrator"
            )
            default = DefaultOrchestrator()
            async for event in default.run(context):
                yield event
            return

        # Convert and filter to pending IDs only
        tool_messages = agui_messages_to_agent_framework(tool_only_raw)
        pending_ids = set(getattr(context.agent, "pending_requests", {}).keys())
        filtered_messages = []
        for msg in tool_messages:
            keep_contents = []
            for c in msg.contents or []:
                if isinstance(c, FunctionResultContent):
                    if c.call_id in pending_ids:
                        keep_contents.append(c)
                    else:
                        logger.info(
                            "  dropping stale call_id=%s",
                            c.call_id,
                        )
                else:
                    keep_contents.append(c)
            if keep_contents:
                msg.contents = keep_contents
                filtered_messages.append(msg)

        tool_messages = filtered_messages
        logger.info(
            "RequestInfoOrchestrator[pending]: %d msgs after pending-ID filter",
            len(tool_messages),
        )

        # Set up event bridge and call agent directly
        event_bridge = AgentFrameworkEventBridge(
            run_id=context.run_id,
            thread_id=context.thread_id,
            input_messages=tool_only_raw,
        )
        yield event_bridge.create_run_started_event()

        thread = AgentThread()
        thread.metadata = {
            "ag_ui_thread_id": context.thread_id,
            "ag_ui_run_id": context.run_id,
        }
        update_count = 0
        async for update in context.agent.run_stream(
            tool_messages,
            thread=thread,
        ):
            update_count += 1
            events = await event_bridge.from_agent_run_update(update)
            for event in events:
                yield event

        logger.info(
            "[RequestInfoOrch] stream done. Updates: %d",
            update_count,
        )

        # Finalize: close open text message
        if event_bridge.current_message_id:
            yield event_bridge.create_message_end_event(
                event_bridge.current_message_id,
            )

        # Close pending tool calls
        if event_bridge.pending_tool_calls:
            from ag_ui.core import ToolCallEndEvent

            for tc in event_bridge.pending_tool_calls:
                tc_id = tc.get("id")
                if tc_id and tc_id not in event_bridge.tool_calls_ended:
                    yield ToolCallEndEvent(tool_call_id=tc_id)

        yield event_bridge.create_run_finished_event()

    # ── Path B: no pending requests (cleanup + delegate) ──────────

    async def _run_cleanup(
        self,
        context: ExecutionContext,
    ) -> AsyncGenerator[BaseEvent, None]:
        """Strip stale request_info and predict-state artifacts, then delegate."""
        raw = context.input_data.get("messages", [])
        ri_ids = self._find_request_info_call_ids(raw)
        ps_ids = self._find_predict_state_call_ids(raw)
        all_ids = ri_ids | ps_ids

        if all_ids:
            cleaned = self._strip_request_info_artifacts(raw, all_ids)
            logger.info(
                "RequestInfoOrchestrator[cleanup]: stripped "
                "%d artifact(s) (request_info=%d, predict_state=%d) "
                "(%d→%d messages)",
                len(all_ids),
                len(ri_ids),
                len(ps_ids),
                len(raw),
                len(cleaned),
            )
            context.input_data["messages"] = cleaned
        else:
            logger.info(
                "RequestInfoOrchestrator[cleanup]: no request_info artifacts to strip"
            )

        # Delegate to DefaultOrchestrator
        default = DefaultOrchestrator()
        async for event in default.run(context):
            yield event


# ---------------------------------------------------------------------------
# AG-UI Server
# ---------------------------------------------------------------------------
async def run_agui() -> None:
    """Start the AG-UI FastAPI server.

    Builds the MAF workflow, wraps it in an ``AgentFrameworkAgent``
    with the custom orchestrator chain, and serves it on port 8000
    via Uvicorn.
    """
    import uvicorn
    from agent_framework.ag_ui import add_agent_framework_fastapi_endpoint
    from fastapi import FastAPI

    from workflow import build_workflow

    # Build workflow asynchronously because it returns coroutine-based resources.
    agent, credential = await build_workflow()

    # Use a custom orchestrator chain:
    #   1. RequestInfoOrchestrator — filters messages when
    #      the workflow has pending request_info HITL calls.
    #   2. HumanInTheLoopOrchestrator — handles tool approval
    #      responses (accept / reject).
    #   3. DefaultOrchestrator — standard agent execution.
    ag_agent = AgentFrameworkAgent(
        agent=agent,
        name="Certinator AI",
        description=(
            "Multi-agent system for Microsoft certification exam preparation."
        ),
        state_schema=_build_state_schema(),
        predict_state_config=_build_predict_state_config(),
        require_confirmation=False,
        orchestrators=[
            RequestInfoOrchestrator(),
            HumanInTheLoopOrchestrator(),
            DefaultOrchestrator(),
        ],
    )

    app = FastAPI(title="Microsoft Agent Framework (Python) - Quickstart")
    add_agent_framework_fastapi_endpoint(app=app, agent=ag_agent, path="/")

    config = uvicorn.Config(app=app, host="0.0.0.0", port=8000)
    server = uvicorn.Server(config=config)

    try:
        await server.serve()
    finally:
        # Close async credential resource on shutdown.
        await credential.close()


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------


def main():
    """Launch the AG-UI server."""
    asyncio.run(run_agui())


if __name__ == "__main__":
    main()
