"""
Certinator AI — Critic Executor

Workflow node that validates specialist output through the Critic
agent and either emits the final response or routes back to the
specialist handler for revision via a RevisionRequest.

Graph position::

    CertInfoHandler  ──┐
    StudyPlanHandler ──┤
                       ▼
                  CriticExecutor
                   ├── PASS → emit response (terminal)
                   └── FAIL → RevisionRequest → source handler (loop)
"""

import json
import logging

from agent_framework import (
    ChatAgent,
    ChatMessage,
    Executor,
    Role,
    WorkflowContext,
    handler,
)

from executors import emit_response, extract_response_text
from executors.models import CriticVerdict, RevisionRequest, SpecialistOutput

logger = logging.getLogger(__name__)

# Maximum critic-review iterations before auto-approving.
MAX_CRITIC_ITERATIONS = 2


class CriticExecutor(Executor):
    """
    Validate specialist content and decide: approve or request revision.

    Receives ``SpecialistOutput`` from specialist handlers, runs the
    Critic agent, and either emits the final response (PASS or max
    iterations reached) or sends a ``RevisionRequest`` back to the
    source handler (FAIL).
    """

    critic_agent: ChatAgent

    def __init__(
        self,
        critic_agent: ChatAgent,
        id: str = "critic-executor",
    ):
        """
        Initialise the Critic executor.

        Parameters:
            critic_agent (ChatAgent): Critic chat agent (gpt-4.1-mini).
            id (str): Executor identifier in the workflow graph.
        """
        self.critic_agent = critic_agent
        super().__init__(id=id)

    @handler
    async def handle(
        self,
        output: SpecialistOutput,
        ctx: WorkflowContext,
    ) -> None:
        """
        Validate content and route accordingly.

        On PASS (or max iterations): stream the response to the user.
        On FAIL: send a RevisionRequest back to the source handler.

        Parameters:
            output (SpecialistOutput): Content from a specialist.
            ctx (WorkflowContext): Workflow context for messaging.
        """
        verdict = await self._validate(output.content, output.content_type)

        if verdict.verdict == "PASS" or output.iteration >= MAX_CRITIC_ITERATIONS:
            text = output.content
            if verdict.verdict == "FAIL":
                logger.warning(
                    "Critic FAIL at max iterations (%d) — "
                    "auto-approving with disclaimer for %s",
                    output.iteration,
                    output.source_executor_id,
                )
                text += (
                    "\n\n---\n*Note: some details may need "
                    "verification. Please cross-check with the "
                    "official Microsoft Learn study guide.*"
                )
            else:
                logger.info(
                    "Critic PASS for %s (iteration %d, confidence=%d)",
                    output.source_executor_id,
                    output.iteration,
                    verdict.confidence,
                )
            await emit_response(ctx, output.source_executor_id, text)
        else:
            logger.info(
                "Critic FAIL for %s (iteration %d) — requesting revision",
                output.source_executor_id,
                output.iteration,
            )
            await ctx.send_message(
                RevisionRequest(
                    original_decision=output.original_decision,
                    previous_content=output.content,
                    feedback=verdict.issues + verdict.suggestions,
                    iteration=output.iteration + 1,
                    source_executor_id=output.source_executor_id,
                )
            )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _validate(
        self,
        content: str,
        content_type: str,
    ) -> CriticVerdict:
        """
        Send *content* through the Critic agent and return a verdict.

        Parameters:
            content (str): The text to validate.
            content_type (str): Label such as "certification_info"
                or "study_plan".

        Returns:
            CriticVerdict: Structured validation result.
        """
        prompt = (
            f"Review the following {content_type} output and "
            f"validate it.\n\n"
            f"Content to review:\n---\n{content}\n---\n\n"
            "Respond with your validation JSON."
        )
        messages = [ChatMessage(role=Role.USER, text=prompt)]

        try:
            response = await self.critic_agent.run(messages)
            verdict_text = extract_response_text(response)
            data = json.loads(verdict_text)
            verdict = CriticVerdict.model_validate(data)
        except (json.JSONDecodeError, IndexError, Exception) as exc:
            logger.warning("Critic produced unparseable output: %s", exc)
            verdict = CriticVerdict(verdict="PASS", confidence=50)

        if verdict.verdict == "FAIL":
            logger.info(
                "Critic flagged issues (confidence=%d): %s",
                verdict.confidence,
                verdict.issues,
            )

        return verdict
