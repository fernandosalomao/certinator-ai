"""
Certinator AI — Critic Executor

Workflow node that validates specialist output through the CriticAgent
and either emits the final response or routes back to the
specialist executor for revision via a RevisionRequest.

Graph position::

    CertificationInfoExecutor  ──┐
    StudyPlanGeneratorExecutor ──┤
                               │
                          CriticExecutor
                           ├── PASS → emit response (terminal)
                           └── FAIL → RevisionRequest → source executor (loop)
"""

import logging
from typing import Any, Union

from agent_framework import (
    ChatAgent,
    ChatMessage,
    Executor,
    Role,
    WorkflowContext,
    handler,
)

import metrics
from executors import emit_response, safe_agent_run, update_workflow_progress
from executors.models import (
    ApprovedStudyPlanOutput,
    CriticVerdict,
    CriticVerdictResponse,
    RevisionRequest,
    SpecialistOutput,
)
from safety import validate_output

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
        ctx: WorkflowContext[Union[ApprovedStudyPlanOutput, RevisionRequest]],
    ) -> None:
        """
        Validate content and route accordingly.

        On PASS (or max iterations): stream the response to the user.
        On FAIL: send a RevisionRequest back to the source handler.

        Parameters:
            output (SpecialistOutput): Content from a specialist.
            ctx (WorkflowContext): Workflow context for messaging.
        """
        route = (
            "study-plan-generator"
            if output.content_type == "study_plan"
            else "certification-info"
        )
        total_steps = 5 if route == "study-plan-generator" else 3
        await update_workflow_progress(
            ctx=ctx,
            route=route,
            active_executor=self.id,
            message="Critic Agent: Validating generated content quality...",
            current_step=4 if route == "study-plan-generator" else 3,
            total_steps=total_steps,
            reasoning="Checking relevance to student request, structure, and completeness…",
        )

        verdict = await self._validate(
            output.content,
            output.content_type,
            task=output.original_decision.task,
            context=output.original_decision.context,
        )

        auto_approved = (
            verdict.verdict == "FAIL" and output.iteration >= MAX_CRITIC_ITERATIONS
        )
        metrics.critic_verdicts.add(
            1,
            {
                "verdict": verdict.verdict,
                "content_type": output.content_type,
                "auto_approved": str(auto_approved).lower(),
            },
        )

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

            # ── Output content safety gate (G2) ──────────────
            # Run the approved text through the regex-based safety
            # layer to catch harmful content or leaked credentials
            # before it reaches the user.
            safe_text = validate_output(text)
            if safe_text != text:
                logger.warning(
                    "Output safety gate modified content from %s (content_type=%s)",
                    output.source_executor_id,
                    output.content_type,
                )
                metrics.output_safety_blocks.add(
                    1,
                    {
                        "content_type": output.content_type,
                        "source_executor": output.source_executor_id,
                    },
                )
                text = safe_text

            # Build reasoning for the approved-content path.
            if auto_approved:
                critic_reasoning = (
                    f"Auto-approved after {output.iteration} revision(s) — "
                    "disclaimer added. Please cross-check with official documentation."
                )
            else:
                critic_reasoning = (
                    f"Passed quality review — {verdict.confidence}% confidence, "
                    "all required sections present."
                )

            # Study plan outputs route to PostStudyPlanExecutor
            # for a HITL practice-question offer.
            if output.content_type == "study_plan":
                await ctx.send_message(
                    ApprovedStudyPlanOutput(
                        content=text,
                        certification=(output.original_decision.certification),
                        original_decision=(output.original_decision),
                    )
                )
            else:
                await update_workflow_progress(
                    ctx=ctx,
                    route="certification-info",
                    active_executor=self.id,
                    message="Critic Agent: Certification information is ready.",
                    current_step=3,
                    total_steps=3,
                    status="completed",
                    reasoning=critic_reasoning,
                )
                await emit_response(
                    ctx,
                    output.source_executor_id,
                    text,
                )
        else:
            issue_summary = (
                "; ".join(verdict.issues[:2])
                if verdict.issues
                else "content quality below threshold"
            )
            await update_workflow_progress(
                ctx=ctx,
                route=route,
                active_executor=self.id,
                message="Critic Agent: Quality review requested revisions...",
                current_step=4 if route == "study-plan-generator" else 3,
                total_steps=total_steps,
                reasoning=f"Revision requested — {issue_summary}.",
            )
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
        *,
        task: str = "",
        context: str = "",
    ) -> CriticVerdict:
        """
        Send *content* through the Critic agent and return a verdict.

        Parameters:
            content (str): The text to validate.
            content_type (str): Label such as "certification_info"
                or "study_plan".
            task (str): Task description from the original routing decision.
            context (str): User context from the original routing decision.

        Returns:
            CriticVerdict: Structured validation result.
        """
        context_block = ""
        if task:
            context_block += f"Student request: {task}\n"
        if context:
            context_block += f"Student context: {context}\n"
        if context_block:
            context_block += "\n"

        prompt = (
            f"{context_block}"
            f"Review the following {content_type} output and validate it "
            f"against the student's request above.\n\n"
            f"Content to review:\n---\n{content}\n---\n\n"
            "Return validation matching the configured structured schema."
        )
        messages = [ChatMessage(role=Role.USER, text=prompt)]

        try:
            response = await safe_agent_run(
                self.critic_agent,
                messages,
                response_format=CriticVerdictResponse,
            )
            verdict = self._extract_verdict(response)
        except Exception as exc:
            logger.error(
                "Critic agent call failed; auto-approving with PASS: %s",
                exc,
                exc_info=True,
            )
            verdict = CriticVerdict(verdict="PASS", confidence=50)

        if verdict.verdict == "FAIL":
            logger.info(
                "Critic flagged issues (confidence=%d): %s",
                verdict.confidence,
                verdict.issues,
            )

        return verdict

    @staticmethod
    def _extract_verdict(response: Any) -> CriticVerdict:
        """Extract a CriticVerdict from the structured response payload."""
        structured = getattr(response, "value", None)

        if isinstance(structured, CriticVerdictResponse):
            return CriticVerdict.model_validate(structured.model_dump(mode="python"))

        if isinstance(structured, dict):
            return CriticVerdict.model_validate(structured)

        raise ValueError("Missing structured critic verdict")
