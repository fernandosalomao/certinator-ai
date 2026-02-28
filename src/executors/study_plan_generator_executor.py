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

from executors import (
    emit_response,
    extract_response_text,
    safe_agent_run,
    update_workflow_progress,
)
from executors.models import LearningPathsData, RevisionRequest, SpecialistOutput
from tools.schedule import schedule_study_plan

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
                "I encountered an issue generating the study plan. Please try again.",
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
                "I encountered an issue refining the study plan. Please try again.",
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
        learning_paths_json = json.dumps(data.learning_paths, ensure_ascii=False)

        logger.info(
            "StudyPlanGenerator: invoking schedule_study_plan "
            "(hours_per_week=%s, total_weeks=%s, prioritize_by_date=%s)",
            constraints["hours_per_week"],
            constraints["total_weeks"],
            constraints["prioritize_by_date"],
        )

        schedule_json_text = schedule_study_plan(
            learning_paths=learning_paths_json,
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
            f"Computed schedule JSON (already calculated — do NOT recalculate):\n"
            f"```json\n{schedule_pretty}\n```\n\n"
            "Convert this schedule to a student-friendly Markdown response. "
            "Do NOT return JSON. "
            "Include: summary, week-by-week plan grouped by learning path, "
            "learning path coverage table, skipped modules (if any), "
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
        return {
            "weekly_plan": [],
            "learning_path_summary": [],
            "skipped_modules": [],
            "notes": [],
        }

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
        lines.append(f"- **Coverage:** {coverage}% of modules included")
        total_planned = schedule_data.get("total_hours_planned", 0)
        total_available = schedule_data.get("total_hours_available", 0)
        lines.append(
            f"- **Study time:** {total_planned}h planned / {total_available}h available"
        )
        lines.append("")

        for week in schedule_data.get("weekly_plan", []):
            week_num = week.get("week", "?")
            week_hours = week.get("hours", 0)
            lines.append(f"## Week {week_num} ({week_hours}h)")

            # Group items by learning path
            current_lp = None
            for item in week.get("items", []):
                lp_name = item.get("learning_path", "")
                mod_name = item.get("module", "Module")
                url = item.get("url", "")
                item_hours = item.get("hours", 0)

                if lp_name != current_lp:
                    lines.append(f"\n**{lp_name}**")
                    current_lp = lp_name

                if url:
                    lines.append(f"- [{mod_name}]({url}) — {item_hours}h")
                else:
                    lines.append(f"- {mod_name} — {item_hours}h")
            lines.append("")

        # Learning path coverage summary
        lp_summary = schedule_data.get("learning_path_summary", [])
        if lp_summary:
            lines.append("## Learning Path Coverage")
            lines.append(
                "| Exam Topic | Weight | Learning Path | Total Time | "
                "Modules Included | Modules Skipped |"
            )
            lines.append("|---|---:|---|---:|---:|---:|")
            for lp in lp_summary:
                total_min = lp.get("total_minutes", 0)
                hours_str = f"{round(total_min / 60, 1)}h"
                exam_topic = lp.get("exam_topic", "")
                weight = lp.get("exam_weight_pct", 0)
                weight_str = f"{weight}%" if weight else "—"
                lines.append(
                    f"| {exam_topic or '—'} | "
                    f"{weight_str} | "
                    f"{lp.get('learning_path', 'N/A')} | "
                    f"{hours_str} | "
                    f"{lp.get('modules_included', 0)} | "
                    f"{lp.get('modules_skipped', 0)} |"
                )
            lines.append("")

        # Skipped modules
        skipped = schedule_data.get("skipped_modules", [])
        if skipped:
            lines.append("## Skipped Modules")
            lines.append("*These modules are recommended if time allows.*\n")
            for mod in skipped:
                url = mod.get("url", "")
                name = mod.get("module", "Module")
                lp = mod.get("learning_path", "")
                dur = round(mod.get("duration_minutes", 0) / 60, 2)
                if url:
                    lines.append(f"- **{lp}**: [{name}]({url}) — {dur}h")
                else:
                    lines.append(f"- **{lp}**: {name} — {dur}h")
            lines.append("")

        notes = schedule_data.get("notes", [])
        if notes:
            lines.append("## Notes")
            for note in notes:
                lines.append(f"> {note}")
            lines.append("")

        lines.append("## Exam Tips")
        lines.append("- Reserve one session each week for review and weak areas.")
        lines.append("- Complete the knowledge checks in each Microsoft Learn module.")
        lines.append("- In the final week, focus on breadth and timing practice.")

        return "\n".join(lines).strip()
