"""
Certinator AI — Study Plan Scheduler Executor

Workflow node that converts structured topic/learning-path data into a
concrete, week-by-week study plan.  Receives ``LearningPathsData`` from
``LearningPathFetcherHandler``, then instructs the StudyPlan agent
(equipped with the ``schedule_study_plan`` math tool) to generate a
Markdown schedule.  Output flows to ``CriticExecutor`` for quality
validation.

Graph position::

    LearningPathFetcherHandler ──► StudyPlanSchedulerHandler ──► CriticExecutor
                                            ▲                          │
                                            └──── RevisionRequest ─────┘
"""

import json
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

from executors import extract_response_text, update_workflow_progress
from executors.models import LearningPathsData, RevisionRequest, SpecialistOutput
from tools.schedule import schedule_study_plan

logger = logging.getLogger(__name__)


class StudyPlanSchedulerHandler(Executor):
    """
    Generate a week-by-week study plan using topic data + a math tool.

    Flow (initial):
    1. Receive ``LearningPathsData`` from the fetcher.
    2. Derive study constraints (hours/week, weeks, deadline mode).
    3. Execute ``schedule_study_plan`` directly to guarantee arithmetic.
    4. Ask the StudyPlan agent to format the computed schedule as Markdown.
    5. Forward the resulting ``SpecialistOutput``.

    Flow (revision after Critic FAIL):
    1. Receive ``RevisionRequest`` with previous content + feedback.
    2. Re-run the StudyPlan agent asking it to fix the issues.
    3. Forward updated ``SpecialistOutput`` to the CriticExecutor.
    """

    study_plan_agent: ChatAgent

    def __init__(
        self,
        study_plan_agent: ChatAgent,
        id: str = "study-plan-scheduler",
    ):
        """
        Initialise with the study plan agent.

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
        ctx: WorkflowContext,
    ) -> None:
        """
        Schedule the study plan and forward to the Critic.

        Parameters:
            data (LearningPathsData): Topics + original routing decision.
            ctx (WorkflowContext): Workflow context for messaging.
        """
        await update_workflow_progress(
            ctx=ctx,
            route="study_plan",
            active_executor=self.id,
            message="Building a week-by-week study schedule...",
            current_step=3,
            total_steps=5,
        )
        plan_text = await self._generate_plan(data)
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
        ctx: WorkflowContext,
    ) -> None:
        """
        Revise the study plan based on Critic feedback.

        Parameters:
            revision (RevisionRequest): Revision request with feedback.
            ctx (WorkflowContext): Workflow context for messaging.
        """
        await update_workflow_progress(
            ctx=ctx,
            route="study_plan",
            active_executor=self.id,
            message="Refining the study schedule based on quality review...",
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
            "Use the schedule_study_plan tool if you need to recalculate hours."
        )
        plan_messages = [ChatMessage(role=Role.USER, text=prompt)]

        logger.info(
            "StudyPlanScheduler revision (iteration %d): %s",
            revision.iteration,
            cert,
        )
        response = await self.study_plan_agent.run(plan_messages)
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
        """
        Build a prompt with topics JSON + context and run the agent.

        Parameters:
            data (LearningPathsData): Topics and original routing decision.

        Returns:
            str: Generated study plan in Markdown format.
        """
        cert = data.certification or "the requested certification"
        decision = data.original_decision

        constraints = self._derive_study_constraints(
            task=decision.task,
            context=decision.context,
        )
        topics_json = json.dumps(data.topics, ensure_ascii=False)

        logger.info(
            "StudyPlanScheduler: invoking schedule_study_plan (hours_per_week=%s, total_weeks=%s, prioritize_by_date=%s)",
            constraints["hours_per_week"],
            constraints["total_weeks"],
            constraints["prioritize_by_date"],
        )

        schedule_json_text = schedule_study_plan(
            topics=topics_json,
            hours_per_week=constraints["hours_per_week"],
            total_weeks=constraints["total_weeks"],
            prioritize_by_date=constraints["prioritize_by_date"],
        )
        schedule_data = self._safe_json_loads(schedule_json_text)
        schedule_pretty = json.dumps(schedule_data, ensure_ascii=False, indent=2)

        prompt = (
            f"Create a personalised study plan for {cert}.\n\n"
            f"Student request: {decision.task}\n"
            f"Student context: {decision.context}\n\n"
            f"Computed schedule JSON (already calculated):\n"
            f"```json\n{schedule_pretty}\n```\n\n"
            "Convert this schedule to a student-friendly Markdown response. "
            "Do NOT return JSON. "
            "Include: summary, week-by-week plan, coverage table, skipped paths, "
            "and exam tips."
        )
        plan_messages = [ChatMessage(role=Role.USER, text=prompt)]

        logger.info("StudyPlanScheduler: generating plan for %s", cert)
        response = await self.study_plan_agent.run(plan_messages)
        plan_text = extract_response_text(
            response,
            fallback="I could not generate a study plan at this time.",
        )
        if self._looks_like_json(plan_text):
            logger.warning(
                "StudyPlanScheduler: agent returned JSON; using deterministic Markdown fallback"
            )
            return self._render_markdown_from_schedule(
                cert=cert,
                schedule_data=schedule_data,
                hours_per_week=constraints["hours_per_week"],
                total_weeks=constraints["total_weeks"],
            )
        return plan_text

    @staticmethod
    def _safe_json_loads(payload: str) -> dict:
        """Parse JSON safely and return a dict fallback when parsing fails."""
        try:
            parsed = json.loads(payload)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass
        return {"weekly_plan": [], "topics_summary": [], "notes": []}

    @staticmethod
    def _looks_like_json(text: str) -> bool:
        """Check whether the response appears to be raw JSON."""
        candidate = text.strip()
        return (candidate.startswith("{") and candidate.endswith("}")) or (
            candidate.startswith("[") and candidate.endswith("]")
        )

    @staticmethod
    def _derive_study_constraints(task: str, context: str) -> dict:
        """
        Derive study constraints from task/context text.

        Returns:
            dict: ``hours_per_week``, ``total_weeks``, ``prioritize_by_date``.
        """
        text = f"{task} {context}".lower()

        hours_per_week = 6.0
        match_week = re.search(r"(\d+(?:\.\d+)?)\s*hours?\s*(?:per|/)\s*week", text)
        match_day = re.search(r"(\d+(?:\.\d+)?)\s*hours?\s*(?:per|/)\s*day", text)
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
            match = re.search(r"(\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{4})", text)
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

        return {
            "hours_per_week": hours_per_week,
            "total_weeks": total_weeks,
            "prioritize_by_date": prioritize_by_date,
        }

    @staticmethod
    def _render_markdown_from_schedule(
        cert: str,
        schedule_data: dict,
        hours_per_week: float,
        total_weeks: int,
    ) -> str:
        """Render a deterministic Markdown study plan from schedule JSON."""
        lines: list[str] = []
        lines.append(f"# {cert} Study Plan")
        lines.append("")
        lines.append(f"- **Timeline:** {total_weeks} weeks")
        lines.append(f"- **Availability:** {hours_per_week:.1f} hours/week")
        coverage = schedule_data.get("coverage_pct", 0)
        lines.append(f"- **Coverage estimate:** {coverage}%")
        lines.append("")

        for week in schedule_data.get("weekly_plan", []):
            week_num = week.get("week", "?")
            week_hours = week.get("hours", 0)
            lines.append(f"## Week {week_num} ({week_hours}h)")
            for item in week.get("items", []):
                lp_name = item.get("learning_path", "Learning path")
                url = item.get("url", "")
                topic = item.get("topic", "Topic")
                item_hours = item.get("hours", 0)
                if url:
                    lines.append(f"- **{topic}**: [{lp_name}]({url}) ({item_hours}h)")
                else:
                    lines.append(f"- **{topic}**: {lp_name} ({item_hours}h)")
            lines.append("")

        lines.append("## Coverage Summary")
        lines.append("| Topic | Weight % | Hours | Skipped Paths |")
        lines.append("|---|---:|---:|---:|")
        for topic in schedule_data.get("topics_summary", []):
            lines.append(
                "| "
                f"{topic.get('topic', 'N/A')} | "
                f"{topic.get('exam_weight_pct', 0)} | "
                f"{topic.get('selected_hours', 0)} | "
                f"{topic.get('paths_skipped', 0)} |"
            )
        lines.append("")

        notes = schedule_data.get("notes", [])
        if notes:
            lines.append("## Notes")
            for note in notes:
                lines.append(f"- {note}")
            lines.append("")

        lines.append("## Exam Tips")
        lines.append("- Reserve one session each week for review and weak topics.")
        lines.append("- Retake Microsoft Learn checks after revising missed concepts.")
        lines.append("- In the final week, focus on breadth and timing practice.")

        return "\n".join(lines).strip()
