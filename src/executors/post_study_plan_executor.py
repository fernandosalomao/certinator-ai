"""
Certinator AI — Post-Study-Plan Executor

HITL executor that offers practice questions after a study plan
has been approved by the Critic.  Intercepts approved study plan
output and asks the student if they want to practice.

Graph position::

    CriticExecutor ──[study-plan-generator PASS]──► PostStudyPlanExecutor
                                             ├── HITL YES → RoutingDecision
                                             │               → PracticeQuestionsExecutor
                                             └── HITL NO  → end
"""

import logging

from agent_framework import (
    Executor,
    WorkflowContext,
    handler,
    response_handler,
)

import metrics
from executors import emit_response, emit_state_snapshot, update_workflow_progress
from executors.models import (
    ApprovedStudyPlanOutput,
    RoutingDecision,
)

logger = logging.getLogger(__name__)

# Shared-state key for persisting context across HITL turns.
POST_STUDY_PLAN_CTX_KEY = "post_study_plan_context"


class PostStudyPlanExecutor(Executor):
    """Offer practice questions after a study plan is delivered.

    Receives ``ApprovedStudyPlanOutput`` from CriticExecutor,
    emits the study plan text to the user, and asks via HITL
    whether they want practice questions.
    """

    def __init__(
        self,
        id: str = "post-study-plan-executor",
    ):
        """Initialise the post-study-plan executor.

        Parameters:
            id (str): Executor identifier.
        """
        super().__init__(id=id)

    # ------------------------------------------------------------------
    # Entry: emit study plan and offer practice
    # ------------------------------------------------------------------

    @handler
    async def handle(
        self,
        approved: ApprovedStudyPlanOutput,
        ctx: WorkflowContext[RoutingDecision],
    ) -> None:
        """Emit the approved study plan and offer practice.

        Parameters:
            approved (ApprovedStudyPlanOutput): Critic-approved
                study plan.
            ctx (WorkflowContext): Workflow context.
        """
        await update_workflow_progress(
            ctx=ctx,
            route="study-plan-generator",
            active_executor=self.id,
            message="Study plan is ready.",
            current_step=5,
            total_steps=5,
            status="completed",
        )

        # Stream the approved study plan text to the user.
        await emit_response(ctx, self.id, approved.content)

        context_data = {
            "certification": approved.certification,
            "context": approved.original_decision.context,
        }
        # Persist for HITL response handler internal reads.
        await ctx.shared_state.set(POST_STUDY_PLAN_CTX_KEY, context_data)
        # Emit to frontend AG-UI state via synthetic tool call pair.
        await emit_state_snapshot(
            ctx=ctx,
            executor_id=self.id,
            tool_name="update_post_study_plan_context",
            tool_argument="context",
            state_value=context_data,
        )

        # Offer practice questions via HITL.
        cert = approved.certification or "your certification"
        offer = (
            "Would you like some **practice questions** "
            f"for **{cert}** based on your study plan?"
        )
        await ctx.request_info(
            request_data={
                "type": "practice_offer",
                "prompt": offer,
                "certification": cert,
            },
            response_type=str,
        )

    # ------------------------------------------------------------------
    # HITL: student responds to practice offer
    # ------------------------------------------------------------------

    @response_handler
    async def on_practice_offer(
        self,
        original_request: dict,
        answer: str,
        ctx: WorkflowContext[RoutingDecision],
    ) -> None:
        """Route to practice quiz or end conversation.

        Parameters:
            original_request (dict): Serialised HITL payload.
            answer (str): Student's response (yes/no).
            ctx (WorkflowContext): Workflow context.
        """
        reply = answer.strip().lower()
        affirmative = (
            reply
            in (
                "yes",
                "y",
                "sure",
                "ok",
                "okay",
                "please",
                "yeah",
            )
            or "yes" in reply
        )

        metrics.hitl_practice_offers.add(
            1,
            {"accepted": str(affirmative).lower()},
        )

        # Retrieve stored certification context.
        state = await ctx.shared_state.get(
            POST_STUDY_PLAN_CTX_KEY,
        )
        cert = state.get("certification", "") if state else ""
        context = state.get("context", "") if state else ""

        if affirmative:
            await emit_response(
                ctx,
                self.id,
                "Starting practice questions based on your study plan...",
            )

            # Send a RoutingDecision that the
            # PracticeQuestionsExecutor will handle.
            await ctx.send_message(
                RoutingDecision(
                    route="practice-questions",
                    task=(f"Generate practice questions for {cert}"),
                    certification=cert,
                    context=(f"Based on study plan. {context}"),
                )
            )
        else:
            await emit_response(
                ctx,
                self.id,
                "No problem! You can always come back for "
                "practice questions later. Good luck with "
                "your studies!",
            )
