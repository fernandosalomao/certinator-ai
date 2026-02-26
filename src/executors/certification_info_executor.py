"""
Certinator AI — CertificationInfo Executor

Workflow node that retrieves certification information using the
CertificationInfoAgent (with MS Learn MCP tool).  Outputs a SpecialistOutput
that the CriticExecutor validates downstream.

Graph position::

    CoordinatorExecutor ──► CertificationInfoExecutor ──► CriticExecutor
                              ▲                    │
                              └── RevisionRequest ─┘
"""

import logging
from typing import Optional

from agent_framework import (
    ChatAgent,
    ChatMessage,
    Executor,
    Role,
    WorkflowContext,
    handler,
)

import metrics
from executors import (
    emit_response,
    extract_response_text,
    safe_agent_run,
    update_workflow_progress,
)
from executors.models import RevisionRequest, RoutingDecision, SpecialistOutput
from tools.mcp import is_mcp_error

logger = logging.getLogger(__name__)


class CertificationInfoExecutor(Executor):
    """
    Retrieve Microsoft certification information.

    Uses the CertificationInfoAgent (equipped with the MS Learn MCP tool)
    to search official Microsoft Learn content.  Output flows to the
    CriticExecutor for quality validation.
    """

    cert_info_agent: ChatAgent
    cert_info_fallback_agent: Optional[ChatAgent]

    def __init__(
        self,
        cert_info_agent: ChatAgent,
        cert_info_fallback_agent: Optional[ChatAgent] = None,
        id: str = "certification-info-executor",
    ):
        """
        Initialise the executor with the CertificationInfoAgent.

        Parameters:
            cert_info_agent (ChatAgent): Agent with MS Learn MCP access.
            cert_info_fallback_agent (Optional[ChatAgent]): Agent without
                MCP used when ``learn.microsoft.com/api/mcp`` is down.
                When ``None``, MCP failures emit a generic error message.
            id (str): Executor identifier in the workflow graph.
        """
        self.cert_info_agent = cert_info_agent
        self.cert_info_fallback_agent = cert_info_fallback_agent
        super().__init__(id=id)

    @handler
    async def handle(
        self,
        decision: RoutingDecision,
        ctx: WorkflowContext[SpecialistOutput],
    ) -> None:
        """
        Fetch certification info and forward to the Critic.

        Parameters:
            decision (RoutingDecision): Routing decision from Coordinator.
            ctx (WorkflowContext): Workflow context for messaging.
        """
        await update_workflow_progress(
            ctx=ctx,
            route="certification-info",
            active_executor=self.id,
            message="Certification Agent: Retrieving certification details from Microsoft Learn...",
            current_step=2,
            total_steps=3,
        )
        try:
            result_text = await self._fetch_cert_info(decision)
            metrics.mcp_calls.add(
                1,
                {"executor": "certification-info", "status": "success"},
            )
        except Exception as exc:
            metrics.mcp_calls.add(
                1,
                {"executor": "certification-info", "status": "error"},
            )
            if is_mcp_error(exc) and self.cert_info_fallback_agent is not None:
                metrics.mcp_unavailable_events.add(
                    1,
                    {
                        "executor": "certification-info",
                        "degraded": "true",
                    },
                )
                logger.warning(
                    "CertificationInfo MCP unavailable; degrading to "
                    "general knowledge: %s",
                    exc,
                )
                try:
                    result_text = await self._fetch_cert_info_general(
                        decision,
                    )
                except Exception as fallback_exc:
                    logger.error(
                        "CertificationInfo fallback agent failed: %s",
                        fallback_exc,
                        exc_info=True,
                    )
                    await emit_response(
                        ctx,
                        self.id,
                        "I encountered an issue retrieving that "
                        "information. Please try again.",
                    )
                    return
            else:
                logger.error(
                    "CertificationInfo agent call failed: %s",
                    exc,
                    exc_info=True,
                )
                await emit_response(
                    ctx,
                    self.id,
                    "I encountered an issue retrieving that information. "
                    "Please try again.",
                )
                return
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
        ctx: WorkflowContext[SpecialistOutput],
    ) -> None:
        """
        Revise certification info based on Critic feedback.

        Parameters:
            revision (RevisionRequest): Revision request with feedback.
            ctx (WorkflowContext): Workflow context for messaging.
        """
        await update_workflow_progress(
            ctx=ctx,
            route="certification-info",
            active_executor=self.id,
            message="Certification Agent: Refining certification details based on quality review...",
            current_step=2,
            total_steps=3,
        )
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
            "CertificationInfo revision (iteration %d): %s",
            revision.iteration,
            cert,
        )
        try:
            response = await safe_agent_run(self.cert_info_agent, messages)
            metrics.mcp_calls.add(
                1,
                {"executor": "certification-info", "status": "success"},
            )
        except Exception as exc:
            metrics.mcp_calls.add(
                1,
                {"executor": "certification-info", "status": "error"},
            )
            if is_mcp_error(exc) and self.cert_info_fallback_agent is not None:
                metrics.mcp_unavailable_events.add(
                    1,
                    {
                        "executor": "certification-info",
                        "degraded": "true",
                    },
                )
                logger.warning(
                    "CertificationInfo revision MCP unavailable; degrading "
                    "to general knowledge: %s",
                    exc,
                )
                try:
                    response = await safe_agent_run(
                        self.cert_info_fallback_agent, messages
                    )
                except Exception as fallback_exc:
                    logger.error(
                        "CertificationInfo fallback revision failed: %s",
                        fallback_exc,
                        exc_info=True,
                    )
                    await emit_response(
                        ctx,
                        self.id,
                        "I encountered an issue refining that information. "
                        "Please try again.",
                    )
                    return
            else:
                logger.error(
                    "CertificationInfo revision agent call failed: %s",
                    exc,
                    exc_info=True,
                )
                await emit_response(
                    ctx,
                    self.id,
                    "I encountered an issue refining that information. "
                    "Please try again.",
                )
                return
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
        """Call the CertificationInfoAgent (with MCP tool).

        Parameters:
            decision (RoutingDecision): Original routing decision.

        Returns:
            str: Certification information text.
        """
        cert = decision.certification or "the requested certification"
        prompt = (
            f"{decision.task}\n\n"
            f"Certification: {cert}\n"
            f"Additional context: {decision.context}"
        )
        messages = [ChatMessage(role=Role.USER, text=prompt)]

        logger.info("CertificationInfo agent call: %s", cert)
        response = await safe_agent_run(self.cert_info_agent, messages)
        return extract_response_text(
            response,
            fallback="I could not retrieve certification information.",
        )

    async def _fetch_cert_info_general(
        self,
        decision: RoutingDecision,
    ) -> str:
        """Call the fallback agent (no MCP).

        Used when ``learn.microsoft.com/api/mcp`` is unavailable.
        The fallback agent responds from training knowledge and is
        instructed to prepend an unavailability disclaimer.

        Parameters:
            decision (RoutingDecision): Original routing decision.

        Returns:
            str: General-knowledge certification information text
            with a Microsoft Learn unavailability disclaimer.
        """
        cert = decision.certification or "the requested certification"
        prompt = (
            f"{decision.task}\n\n"
            f"Certification: {cert}\n"
            f"Additional context: {decision.context}"
        )
        messages = [ChatMessage(role=Role.USER, text=prompt)]
        logger.info(
            "CertificationInfo fallback (no MCP) for: %s",
            cert,
        )
        response = await safe_agent_run(self.cert_info_fallback_agent, messages)
        return extract_response_text(
            response,
            fallback=(
                "\u26a0\ufe0f **Microsoft Learn is temporarily "
                "unavailable.** I was unable to retrieve "
                "certification information right now. Please try "
                "again later or visit "
                "https://learn.microsoft.com directly."
            ),
        )
