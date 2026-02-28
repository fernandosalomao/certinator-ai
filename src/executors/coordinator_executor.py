"""
Certinator AI — Coordinator Executor

Entry-point node of the workflow graph. Receives user messages,
calls the CoordinatorAgent to produce a structured routing decision,
and forwards the decision downstream via switch-case edges.
"""

import logging
from typing import Any

from agent_framework import (
    ChatAgent,
    ChatMessage,
    Executor,
    WorkflowContext,
    handler,
)

import metrics
from executors import (
    emit_response,
    extract_response_text,
    get_user_friendly_error,
    safe_agent_run,
    update_workflow_progress,
)
from executors.models import CoordinatorResponse, RoutingDecision

logger = logging.getLogger(__name__)


class CoordinatorExecutor(Executor):
    """
    Analyse user intent and emit a RoutingDecision.

    Uses structured response_format output and falls back to ``general``
    route on invalid or missing structured data.
    """

    agent: ChatAgent

    def __init__(self, agent: ChatAgent, id: str = "coordinator-executor"):
        """
        Initialise the Coordinator executor.

        Parameters:
            agent (ChatAgent): Coordinator chat agent.
            id (str): Executor identifier in the workflow graph.
        """
        self.agent = agent
        super().__init__(id=id)

    @handler
    async def handle(
        self,
        messages: list[ChatMessage],
        ctx: WorkflowContext[RoutingDecision],
    ) -> None:
        """
        Route incoming messages to the appropriate specialist.

        1. Call the Coordinator LLM.
        2. Parse the JSON routing decision.
        3. Forward via ``ctx.send_message``.

        Parameters:
            messages (list[ChatMessage]): Full conversation history.
            ctx (WorkflowContext[RoutingDecision]): Typed context that
                sends a RoutingDecision to downstream nodes.
        """
        try:
            response = await safe_agent_run(
                self.agent,
                messages,
                response_format=CoordinatorResponse,
            )
        except Exception as exc:
            logger.error(
                "Coordinator agent call failed: %s",
                exc,
                exc_info=True,
            )
            await emit_response(
                ctx,
                self.id,
                get_user_friendly_error(
                    exc,
                    "I encountered an issue processing your request. Please try again.",
                ),
            )
            return
        decision = self._extract_routing(response)
        logger.info(
            "Routing → %s (cert=%s) | reasoning: %s",
            decision.route,
            decision.certification or "n/a",
            (decision.reasoning or "")[:200],
        )
        metrics.routing_decisions.add(1, {"route": decision.route})

        route_totals = {
            "certification-info": 3,
            "study-plan-generator": 5,
            "practice-questions": 3,
            "general": 2,
        }
        route_messages = {
            "certification-info": "Coordinator: Routing to certification information specialist...",
            "study-plan-generator": "Coordinator: Routing to study plan workflow...",
            "practice-questions": "Coordinator: Routing to practice workflow...",
            "general": "Coordinator: Preparing a direct answer...",
        }
        route = decision.route if decision.route in route_totals else "general"

        # Use LLM-produced chain-of-thought reasoning (G7).
        reasoning = decision.reasoning or ""

        await update_workflow_progress(
            ctx=ctx,
            route=route,
            active_executor=self.id,
            message=route_messages.get(
                route, "Coordinator Agent: Routing your request..."
            ),
            current_step=1,
            total_steps=route_totals.get(route, 2),
            reasoning=reasoning,
        )

        await ctx.send_message(decision)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_routing(response: Any) -> RoutingDecision:
        """
        Extract a RoutingDecision from structured response output.

        Falls back to a ``general`` route containing raw text when the
        structured payload is missing or invalid.

        Parameters:
            response (Any): Agent response object.

        Returns:
            RoutingDecision: Parsed or fallback routing decision.
        """
        structured = getattr(response, "value", None)

        try:
            if isinstance(structured, CoordinatorResponse):
                return RoutingDecision.model_validate(
                    structured.model_dump(mode="python")
                )

            if isinstance(structured, dict):
                return RoutingDecision.model_validate(structured)
        except Exception as exc:  # pragma: no cover - defensive fallback
            logger.warning(
                "Failed to parse structured routing output: %s", exc)

        fallback_text = extract_response_text(response)
        if not fallback_text.strip():
            fallback_text = "How can I help you today?"

        logger.warning("Coordinator returned no structured routing decision.")
        return RoutingDecision(
            route="general",
            task="Direct response",
            response=fallback_text,
        )
