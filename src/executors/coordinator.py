"""
Certinator AI — Coordinator Router Executor

Entry-point node of the workflow graph. Receives user messages,
calls the Coordinator LLM to produce a structured routing decision,
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

from executors import extract_response_text, update_workflow_progress
from executors.models import CoordinatorResponse, RoutingDecision

logger = logging.getLogger(__name__)

# Workflow-state key used to share the original conversation with handlers.
MESSAGES_KEY = "conversation_messages"


class CoordinatorRouter(Executor):
    """
    Analyse user intent and emit a RoutingDecision.

    Uses structured response_format output and falls back to ``general``
    route on invalid or missing structured data.
    """

    agent: ChatAgent

    def __init__(self, agent: ChatAgent, id: str = "coordinator-router"):
        """
        Initialise the Coordinator router.

        Parameters:
            agent (ChatAgent): Coordinator chat agent (gpt-4.1-mini).
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

        1. Store conversation in workflow state for downstream access.
        2. Call the Coordinator LLM.
        3. Parse the JSON routing decision.
        4. Forward via ``ctx.send_message``.

        Parameters:
            messages (list[ChatMessage]): Full conversation history.
            ctx (WorkflowContext[RoutingDecision]): Typed context that
                sends a RoutingDecision to downstream nodes.
        """
        # Persist the conversation so specialist handlers can retrieve it.
        await ctx.shared_state.set(MESSAGES_KEY, messages)

        response = await self.agent.run(
            messages,
            response_format=CoordinatorResponse,
        )
        decision = self._extract_routing(response)
        logger.info(
            "Routing → %s (cert=%s)",
            decision.route,
            decision.certification or "n/a",
        )

        route_totals = {
            "cert_info": 3,
            "study_plan": 5,
            "practice": 3,
            "general": 2,
        }
        route_messages = {
            "cert_info": "Routing to certification information specialist...",
            "study_plan": "Routing to study plan workflow...",
            "practice": "Routing to practice workflow...",
            "general": "Preparing a direct answer...",
        }
        route = decision.route if decision.route in route_totals else "general"
        await update_workflow_progress(
            ctx=ctx,
            route=route,
            active_executor=self.id,
            message=route_messages.get(route, "Routing your request..."),
            current_step=1,
            total_steps=route_totals.get(route, 2),
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
            logger.warning("Failed to parse structured routing output: %s", exc)

        fallback_text = extract_response_text(response)
        if not fallback_text.strip():
            fallback_text = "How can I help you today?"

        logger.warning("Coordinator returned no structured routing decision.")
        return RoutingDecision(
            route="general",
            task="Direct response",
            response=fallback_text,
        )
