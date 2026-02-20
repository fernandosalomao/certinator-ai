"""
Certinator AI — CertInfo Handler Executor

Workflow node that retrieves certification information using the
CertInfo agent (with MS Learn MCP tool).  Outputs a SpecialistOutput
that the CriticExecutor validates downstream.

Graph position::

    CoordinatorRouter ──► CertInfoHandler ──► CriticExecutor
                              ▲                    │
                              └── RevisionRequest ─┘
"""

import logging

from agent_framework import (
    ChatAgent,
    ChatMessage,
    Executor,
    Role,
    WorkflowContext,
    handler,
)

from executors import extract_response_text
from executors.models import RevisionRequest, RoutingDecision, SpecialistOutput

logger = logging.getLogger(__name__)


class CertInfoHandler(Executor):
    """
    Retrieve Microsoft certification information.

    Uses the CertInfo ChatAgent (equipped with the MS Learn MCP tool)
    to search official Microsoft Learn content.  Output flows to the
    CriticExecutor for quality validation.
    """

    cert_info_agent: ChatAgent

    def __init__(
        self,
        cert_info_agent: ChatAgent,
        id: str = "cert-info-handler",
    ):
        """
        Initialise the handler with the CertInfo agent.

        Parameters:
            cert_info_agent (ChatAgent): Agent with MS Learn MCP access.
            id (str): Executor identifier in the workflow graph.
        """
        self.cert_info_agent = cert_info_agent
        super().__init__(id=id)

    @handler
    async def handle(
        self,
        decision: RoutingDecision,
        ctx: WorkflowContext,
    ) -> None:
        """
        Fetch certification info and forward to the Critic.

        Parameters:
            decision (RoutingDecision): Routing decision from Coordinator.
            ctx (WorkflowContext): Workflow context for messaging.
        """
        result_text = await self._fetch_cert_info(decision)
        await ctx.send_message(
            SpecialistOutput(
                content=result_text,
                content_type="certification_info",
                source_executor_id=self.id,
                iteration=1,
                original_decision=decision,
            )
        )

    @handler
    async def handle_revision(
        self,
        revision: RevisionRequest,
        ctx: WorkflowContext,
    ) -> None:
        """
        Revise certification info based on Critic feedback.

        Parameters:
            revision (RevisionRequest): Revision request with feedback.
            ctx (WorkflowContext): Workflow context for messaging.
        """
        cert = revision.original_decision.certification or "the requested certification"
        feedback_text = "\n".join(f"- {f}" for f in revision.feedback)
        prompt = (
            f"Revise and improve the following certification "
            f"information for {cert}.\n\n"
            f"Previous content:\n---\n{revision.previous_content}"
            f"\n---\n\n"
            f"Reviewer feedback:\n{feedback_text}\n\n"
            f"Please address all feedback points and provide an "
            f"improved, accurate response."
        )
        messages = [ChatMessage(role=Role.USER, text=prompt)]

        logger.info(
            "CertInfo revision (iteration %d): %s",
            revision.iteration,
            cert,
        )
        response = await self.cert_info_agent.run(messages)
        result_text = extract_response_text(
            response,
            fallback="I could not retrieve certification information.",
        )

        await ctx.send_message(
            SpecialistOutput(
                content=result_text,
                content_type="certification_info",
                source_executor_id=self.id,
                iteration=revision.iteration,
                original_decision=revision.original_decision,
            )
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _fetch_cert_info(
        self,
        decision: RoutingDecision,
    ) -> str:
        """
        Call the CertInfo agent with the routing decision context.

        Parameters:
            decision (RoutingDecision): Original routing decision.

        Returns:
            str: Generated certification information text.
        """
        cert = decision.certification or "the requested certification"
        prompt = (
            f"{decision.task}\n\n"
            f"Certification: {cert}\n"
            f"Additional context: {decision.context}"
        )
        messages = [ChatMessage(role=Role.USER, text=prompt)]

        logger.info("CertInfo agent processing: %s", cert)
        response = await self.cert_info_agent.run(messages)
        return extract_response_text(
            response,
            fallback="I could not retrieve certification information.",
        )
