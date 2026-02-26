"""
Certinator AI — Study Plan Feasibility Evaluator

Deterministic evaluator that validates the JSON output of
``schedule_study_plan()`` for structural and logical correctness.

Assertions checked:
    1. Valid JSON with required top-level keys.
    2. ``total_hours_planned`` <= ``total_hours_available`` * 1.15
       (within the 15 % tolerance used by the scheduler).
    3. ``total_weeks_needed`` <= ``total_weeks`` (from context).
    4. All topics from the input appear in ``topics_summary``.
    5. Weekly plan hours sum to ``total_hours_planned``.

Scoring (1-5 scale):
    5 — All assertions pass
    4 — 1 assertion fails
    3 — 2 assertions fail
    2 — 3 assertions fail
    1 — 4+ assertions fail or invalid JSON
"""

from __future__ import annotations

import json


class StudyPlanFeasibilityEvaluator:
    """Validate study plan schedule output for logical feasibility.

    Dataset columns required:
        - ``response``: JSON string output from
          ``schedule_study_plan()``.
        - ``context``: JSON string with ``hours_per_week``,
          ``total_weeks``, and ``expected_topics`` (list[str]).
    """

    def __call__(
        self,
        *,
        response: str,
        context: str = "",
        **kwargs: object,
    ) -> dict:
        """Evaluate feasibility of a study plan schedule.

        Parameters:
            response (str): JSON output from schedule_study_plan().
            context (str): JSON with evaluation parameters.

        Returns:
            dict: Score, violations list, and explanation.
        """
        violations: list[str] = []

        # ── Parse response JSON ──────────────────────────────────
        try:
            plan = json.loads(response)
        except (json.JSONDecodeError, TypeError):
            return {
                "study_plan_feasibility_score": 1,
                "study_plan_feasibility_violations": ["Response is not valid JSON."],
                "study_plan_feasibility_reason": (
                    "Cannot evaluate: response is not valid JSON."
                ),
            }

        # ── Parse context parameters ─────────────────────────────
        try:
            ctx = json.loads(context) if context else {}
        except (json.JSONDecodeError, TypeError):
            ctx = {}

        hours_per_week = ctx.get("hours_per_week", 10)
        total_weeks = ctx.get("total_weeks", 8)
        expected_topics: list[str] = ctx.get("expected_topics", [])
        total_hours_available = hours_per_week * total_weeks

        # ── Required keys ────────────────────────────────────────
        required_keys = {
            "total_hours_available",
            "total_hours_planned",
            "total_weeks_needed",
            "topics_summary",
            "weekly_plan",
        }
        missing_keys = required_keys - set(plan.keys())
        if missing_keys:
            violations.append(f"Missing required keys: {sorted(missing_keys)}.")

        planned_hours = plan.get("total_hours_planned", 0)
        weeks_needed = plan.get("total_weeks_needed", 0)
        topics_summary = plan.get("topics_summary", [])
        weekly_plan = plan.get("weekly_plan", [])

        # ── 1. Hours within budget (15 % tolerance) ──────────────
        if planned_hours > total_hours_available * 1.15:
            violations.append(
                f"Planned hours ({planned_hours}) exceed "
                f"available hours ({total_hours_available}) "
                f"by more than 15%."
            )

        # ── 2. Weeks within deadline ─────────────────────────────
        if weeks_needed > total_weeks:
            violations.append(
                f"Schedule needs {weeks_needed} weeks but only "
                f"{total_weeks} are available."
            )

        # ── 3. Topic coverage ────────────────────────────────────
        summary_topics = {t.get("topic", "").lower() for t in topics_summary}
        for expected in expected_topics:
            matched = any(
                expected.lower() in st or st in expected.lower()
                for st in summary_topics
            )
            if not matched:
                violations.append(
                    f"Expected topic '{expected}' not found in plan summary."
                )

        # ── 4. Weekly hours consistency ──────────────────────────
        weekly_total = sum(w.get("hours", 0) for w in weekly_plan)
        if weekly_plan and abs(weekly_total - planned_hours) > 0.5:
            violations.append(
                f"Weekly plan hours ({weekly_total}) do not sum "
                f"to total_hours_planned ({planned_hours})."
            )

        # ── Score ────────────────────────────────────────────────
        num_violations = len(violations)
        if num_violations == 0:
            score = 5
        elif num_violations == 1:
            score = 4
        elif num_violations == 2:
            score = 3
        elif num_violations == 3:
            score = 2
        else:
            score = 1

        return {
            "study_plan_feasibility_score": score,
            "study_plan_feasibility_violations": violations,
            "study_plan_feasibility_reason": (
                "All feasibility checks passed."
                if not violations
                else f"{num_violations} violation(s): " + "; ".join(violations)
            ),
        }
