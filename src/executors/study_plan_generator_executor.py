"""
Certinator AI — Study Plan Generator Executor

Workflow node that converts structured learning-path / module data into a
concrete, week-by-week study plan.  Receives ``LearningPathsData`` from
``LearningPathFetcherExecutor``, then computes a deterministic schedule
and asks the StudyPlanGeneratorAgent to format it as Markdown.
Output flows to ``CriticExecutor`` for quality validation.

Graph position::

    LearningPathFetcherExecutor ──► StudyPlanGeneratorExecutor ──► CriticExecutor
                                            ▲                          │
                                            └──── RevisionRequest ─────┘
"""

import logging
import re
from datetime import datetime

from agent_framework import (
    ChatAgent,
    ChatMessage,
    Executor,
    Role,
    WorkflowContext,
    handler,
)

from executors import (
    emit_response,
    extract_response_text,
    get_user_friendly_error,
    safe_agent_run,
    update_workflow_progress,
)
from executors.models import (
    LearningPathsData,
    RevisionRequest,
    ScheduleResult,
    SpecialistOutput,
    StudyConstraints,
)
from tools.schedule import compute_schedule

logger = logging.getLogger(__name__)


class StudyPlanGeneratorExecutor(Executor):
    """
    Generate a week-by-week study plan from learning paths + modules.

    Flow (initial):
    1. Receive ``LearningPathsData`` from the fetcher.
    2. Derive study constraints (hours/week, weeks, deadline mode).
    3. Execute ``schedule_study_plan`` directly to guarantee arithmetic.
    4. Ask the StudyPlanGeneratorAgent to format the computed schedule as Markdown.
    5. Forward the resulting ``SpecialistOutput``.

    Flow (revision after Critic FAIL):
    1. Receive ``RevisionRequest`` with previous content + feedback.
    2. Re-run the StudyPlanGeneratorAgent asking it to fix the issues.
    3. Forward updated ``SpecialistOutput`` to the CriticExecutor.
    """

    study_plan_agent: ChatAgent

    def __init__(
        self,
        study_plan_agent: ChatAgent,
        id: str = "study-plan-generator-executor",
    ):
        """
        Initialise with the study plan generator agent.

        Parameters:
            study_plan_agent (ChatAgent): Agent with schedule_study_plan tool.
            id (str): Executor identifier in the workflow graph.
        """
        self.study_plan_agent = study_plan_agent
        super().__init__(id=id)

    @handler
    async def handle(
        self,
        data: LearningPathsData,
        ctx: WorkflowContext[SpecialistOutput],
    ) -> None:
        """
        Schedule the study plan and forward to the Critic.

        Parameters:
            data (LearningPathsData): Learning paths + original routing decision.
            ctx (WorkflowContext): Workflow context for messaging.
        """
        await update_workflow_progress(
            ctx=ctx,
            route="study-plan-generator",
            active_executor=self.id,
            message="Study Plan Agent: Building a week-by-week study schedule...",
            current_step=3,
            total_steps=5,
        )
        try:
            plan_text = await self._generate_plan(data)
        except Exception as exc:
            logger.error(
                "StudyPlanGenerator agent call failed: %s",
                exc,
                exc_info=True,
            )
            await emit_response(
                ctx,
                self.id,
                get_user_friendly_error(
                    exc,
                    "I encountered an issue generating the study plan. Please try again.",
                ),
            )
            return
        await ctx.send_message(
            SpecialistOutput(
                content=plan_text,
                content_type="study_plan",
                source_executor_id=self.id,
                iteration=1,
                original_decision=data.original_decision,
            )
        )

    @handler
    async def handle_revision(
        self,
        revision: RevisionRequest,
        ctx: WorkflowContext[SpecialistOutput],
    ) -> None:
        """
        Revise the study plan based on Critic feedback.

        Parameters:
            revision (RevisionRequest): Revision request with feedback.
            ctx (WorkflowContext): Workflow context for messaging.
        """
        await update_workflow_progress(
            ctx=ctx,
            route="study-plan-generator",
            active_executor=self.id,
            message="Study Plan Agent: Refining the study schedule based on quality review...",
            current_step=3,
            total_steps=5,
        )
        cert = revision.original_decision.certification or "the requested certification"
        feedback_text = "\n".join(f"- {f}" for f in revision.feedback)
        prompt = (
            f"Revise and improve the following study plan for "
            f"{cert}.\n\n"
            f"Previous plan:\n---\n{revision.previous_content}"
            f"\n---\n\n"
            f"Reviewer feedback:\n{feedback_text}\n\n"
            f"Student request: {revision.original_decision.task}\n"
            f"Student context: {revision.original_decision.context}\n"
            "Please address all feedback points. "
            "Do NOT recalculate hours — use the same schedule data."
        )
        plan_messages = [ChatMessage(role=Role.USER, text=prompt)]

        logger.info(
            "StudyPlanGenerator revision (iteration %d): %s",
            revision.iteration,
            cert,
        )
        try:
            response = await safe_agent_run(
                self.study_plan_agent,
                plan_messages,
            )
        except Exception as exc:
            logger.error(
                "StudyPlanGenerator revision agent call failed: %s",
                exc,
                exc_info=True,
            )
            await emit_response(
                ctx,
                self.id,
                get_user_friendly_error(
                    exc,
                    "I encountered an issue refining the study plan. Please try again.",
                ),
            )
            return
        plan_text = extract_response_text(
            response,
            fallback="I could not generate a study plan at this time.",
        )

        await ctx.send_message(
            SpecialistOutput(
                content=plan_text,
                content_type="study_plan",
                source_executor_id=self.id,
                iteration=revision.iteration,
                original_decision=revision.original_decision,
            )
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _generate_plan(
        self,
        data: LearningPathsData,
    ) -> str:
        """Build a prompt with learning paths JSON + context, compute
        the schedule deterministically, then ask the LLM to format it.

        Parameters:
            data (LearningPathsData): Learning paths and original
                routing decision.

        Returns:
            str: Generated study plan in Markdown format.
        """
        cert = data.certification or "the requested certification"
        decision = data.original_decision

        constraints = self._derive_study_constraints(
            task=decision.task,
            context=decision.context,
        )

        logger.info(
            "StudyPlanGenerator: invoking compute_schedule "
            "(hours_per_week=%s, total_weeks=%s, "
            "prioritize_by_date=%s)",
            constraints.hours_per_week,
            constraints.total_weeks,
            constraints.prioritize_by_date,
        )

        schedule = compute_schedule(
            paths_list=data.learning_paths,
            hours_per_week=constraints.hours_per_week,
            total_weeks=constraints.total_weeks,
            prioritize_by_date=constraints.prioritize_by_date,
        )
        schedule_pretty = schedule.model_dump_json(indent=2)

        prompt = (
            f"Create a personalised study plan for {cert}.\n\n"
            f"Student request: {decision.task}\n"
            f"Student context: {decision.context}\n\n"
            f"Computed schedule JSON (already calculated — do NOT recalculate):\n"
            f"```json\n{schedule_pretty}\n```\n\n"
            "Convert this schedule to a student-friendly Markdown response. "
            "Do NOT return JSON. "
            "Include: summary, week-by-week plan grouped by exam skill, "
            "skill coverage table, skipped modules (if any), "
            "scheduler notes, and exam tips."
        )
        plan_messages = [ChatMessage(role=Role.USER, text=prompt)]

        logger.info("StudyPlanGenerator: running plan for %s", cert)
        try:
            response = await safe_agent_run(
                self.study_plan_agent,
                plan_messages,
            )
            plan_text = extract_response_text(
                response,
                fallback="I could not generate a study plan at this time.",
            )
        except Exception as exc:
            logger.error(
                "StudyPlanGenerator agent call failed for %s: %s",
                cert,
                exc,
                exc_info=True,
            )
            raise
        if self._looks_like_json(plan_text):
            logger.warning(
                "StudyPlanGenerator: agent returned JSON; "
                "using deterministic Markdown fallback"
            )
            return self._render_markdown_from_schedule(
                cert=cert,
                schedule=schedule,
                constraints=constraints,
            )
        return plan_text

    @staticmethod
    def _looks_like_json(text: str) -> bool:
        """Check whether the response appears to be raw JSON."""
        candidate = text.strip()
        return (candidate.startswith("{") and candidate.endswith("}")) or (
            candidate.startswith("[") and candidate.endswith("]")
        )

    @staticmethod
    def _derive_study_constraints(
        task: str,
        context: str,
    ) -> StudyConstraints:
        """Derive study constraints from task/context text.

        Parameters:
            task (str): User's task description.
            context (str): Additional user context.

        Returns:
            StudyConstraints: Typed study constraints.
        """
        text = f"{task} {context}".lower()

        hours_per_week = 6.0
        match_week = re.search(
            r"(\d+(?:\.\d+)?)\s*hours?\s*(?:per|/)\s*week", text)
        match_day = re.search(
            r"(\d+(?:\.\d+)?)\s*hours?\s*(?:per|/)\s*day", text)
        if match_week:
            hours_per_week = float(match_week.group(1))
        elif match_day:
            hours_per_week = float(match_day.group(1)) * 7.0

        total_weeks = 8
        prioritize_by_date = False

        match_weeks = re.search(r"(\d+)\s*weeks?", text)
        if match_weeks:
            total_weeks = max(1, int(match_weeks.group(1)))
            prioritize_by_date = True

        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"):
            match = re.search(
                r"(\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{4})", text)
            if not match:
                continue
            try:
                exam_date = datetime.strptime(match.group(1), fmt).date()
                today = datetime.utcnow().date()
                days_delta = (exam_date - today).days
                if days_delta > 0:
                    total_weeks = max(1, days_delta // 7)
                    prioritize_by_date = True
                break
            except ValueError:
                continue

        return StudyConstraints(
            hours_per_week=hours_per_week,
            total_weeks=total_weeks,
            prioritize_by_date=prioritize_by_date,
        )

    @staticmethod
    def _render_markdown_from_schedule(
        cert: str,
        schedule: ScheduleResult,
        constraints: StudyConstraints,
    ) -> str:
        """Render a deterministic Markdown study plan.

        Parameters:
            cert (str): Certification code.
            schedule (ScheduleResult): Computed schedule.
            constraints (StudyConstraints): Study constraints.

        Returns:
            str: Formatted Markdown study plan.
        """
        lines: list[str] = []
        lines.append(f"# {cert} Study Plan")
        lines.append("")
        lines.append(f"- **Timeline:** {constraints.total_weeks} weeks")
        lines.append(
            f"- **Availability:** {constraints.hours_per_week:.1f} hours/week")
        lines.append(
            f"- **Coverage:** {schedule.coverage_pct}% of modules included")
        lines.append(
            f"- **Study time:** "
            f"{schedule.total_hours_planned}h planned / "
            f"{schedule.total_hours_available}h available"
        )
        lines.append("")

        for week in schedule.weekly_plan:
            lines.append(f"## Week {week.week} ({week.hours}h)")

            # Group items by exam skill
            current_skill = None
            for item in week.items:
                if item.exam_skill != current_skill:
                    weight_str = (
                        f" ({item.exam_weight_pct}%)" if item.exam_weight_pct else ""
                    )
                    lines.append(f"\n**{item.exam_skill}{weight_str}**")
                    current_skill = item.exam_skill

                if item.url:
                    lines.append(
                        f"- [{item.module}]({item.url}) — {item.hours}h")
                else:
                    lines.append(f"- {item.module} — {item.hours}h")
            lines.append("")

        # Exam skill coverage summary
        if schedule.skill_summary:
            lines.append("## Exam Skill Coverage")
            lines.append(
                "| Exam Skill | Weight | Total Time | "
                "Modules Included | Modules Skipped |"
            )
            lines.append("|---|---:|---:|---:|---:|")
            for sk in schedule.skill_summary:
                hours_str = f"{round(sk.total_minutes / 60, 1)}h"
                weight_str = f"{sk.exam_weight_pct}%" if sk.exam_weight_pct else "—"
                lines.append(
                    f"| {sk.exam_skill} | "
                    f"{weight_str} | "
                    f"{hours_str} | "
                    f"{sk.modules_included} | "
                    f"{sk.modules_skipped} |"
                )
            lines.append("")

        # Skipped modules
        if schedule.skipped_modules:
            lines.append("## Skipped Modules")
            lines.append("*These modules are recommended if time allows.*\n")
            for mod in schedule.skipped_modules:
                dur = round(mod.duration_minutes / 60, 2)
                if mod.url:
                    lines.append(
                        f"- **{mod.exam_skill}**: [{mod.module}]({mod.url}) — {dur}h"
                    )
                else:
                    lines.append(
                        f"- **{mod.exam_skill}**: {mod.module} — {dur}h")
            lines.append("")

        if schedule.notes:
            lines.append("## Notes")
            for note in schedule.notes:
                lines.append(f"> {note}")
            lines.append("")

        lines.append("## Exam Tips")
        lines.append(
            "- Reserve one session each week for review and weak areas.")
        lines.append(
            "- Complete the knowledge checks in each Microsoft Learn module.")
        lines.append(
            "- In the final week, focus on breadth and timing practice.")

        return "\n".join(lines).strip()
