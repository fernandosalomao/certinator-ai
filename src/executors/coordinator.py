"""
Certinator AI — Coordinator Router Executor

Entry-point node of the workflow graph. Receives user messages,
calls the Coordinator LLM to produce a structured routing decision,
and forwards the decision downstream via switch-case edges.
"""

import json
import logging

from agent_framework import (
    ChatAgent,
    ChatMessage,
    Executor,
    WorkflowContext,
    handler,
)

from executors import extract_response_text
from executors.models import RoutingDecision

logger = logging.getLogger(__name__)

# Workflow-state key used to share the original conversation with handlers.
MESSAGES_KEY = "conversation_messages"


class CoordinatorRouter(Executor):
    """
    Analyse user intent and emit a RoutingDecision.

    The Coordinator LLM is instructed to return JSON.  If parsing fails
    the executor falls back to the ``general`` route so the user always
    receives a response.
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

        response = await self.agent.run(messages)
        raw_text = extract_response_text(response)

        decision = self._parse_routing(raw_text)
        logger.info(
            "Routing → %s (cert=%s)",
            decision.route,
            decision.certification or "n/a",
        )
        await ctx.send_message(decision)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_routing(text: str) -> RoutingDecision:
        """
        Attempt to parse the LLM output as a RoutingDecision.

        Falls back to a ``general`` route containing the raw text if the
        JSON cannot be decoded.

        Parameters:
            text (str): Raw LLM output (expected JSON).

        Returns:
            RoutingDecision: Parsed or fallback routing decision.
        """
        try:
            data = json.loads(text)
            return RoutingDecision.model_validate(data)
        except (json.JSONDecodeError, Exception) as exc:
            logger.warning("Failed to parse routing JSON: %s", exc)
            return RoutingDecision(
                route="general",
                task="Direct response",
                response=text,
            )
