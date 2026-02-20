"""
Certinator AI — Study Schedule Calculator Tool

AI function tool invoked by the study_plan_agent to compute a
week-by-week schedule from exam topics / learning-path data and the
student's availability.  The LLM calls this tool with JSON; the
Python function does all the arithmetic and returns a structured plan
so the model never has to calculate hours itself.
"""

from __future__ import annotations

import json
import math
from typing import Annotated

from agent_framework import ai_function


@ai_function(
    name="schedule_study_plan",
    description=(
        "Compute a week-by-week study schedule given a list of certification "
        "topics (each with learning paths and their durations) and the "
        "student's available hours. Returns a JSON object with the full plan, "
        "coverage stats, and notes."
    ),
)
def schedule_study_plan(
    topics: Annotated[
        str,
        (
            "JSON array of topic objects. Each object must have: "
            "name (str), exam_weight_pct (number 0-100), "
            "learning_paths (array of {name: str, url: str, duration_hours: number}). "
            "Example: "
            '[{"name":"Cloud Concepts","exam_weight_pct":27,'
            '"learning_paths":[{"name":"LP1","url":"https://...","duration_hours":3.5}]}]'
        ),
    ],
    hours_per_week: Annotated[
        float,
        "Number of study hours the student has available per week.",
    ],
    total_weeks: Annotated[
        int,
        (
            "Number of weeks available before the exam. "
            "Use weeks until the exam date when provided, or 8 if no date was given."
        ),
    ],
    prioritize_by_date: Annotated[
        bool,
        (
            "When True, cap topic hours to the proportional allocation so the "
            "plan fits within total_weeks. When False (no exam deadline), "
            "include all available learning paths regardless of time."
        ),
    ],
) -> str:
    """
    Calculate a feasible study schedule from topics/learning-paths.

    Parameters:
        topics (str): JSON array of topic objects with learning paths.
        hours_per_week (float): Weekly study hours available.
        total_weeks (int): Total weeks until exam (or default 8).
        prioritize_by_date (bool): Trim content to fit deadline if True.

    Returns:
        str: JSON-encoded schedule with weekly plan, stats, and notes.
    """
    try:
        topics_list: list[dict] = json.loads(topics)
    except json.JSONDecodeError as exc:
        return json.dumps({"error": f"Invalid topics JSON: {exc}"})

    total_hours = hours_per_week * total_weeks
    total_weight = sum(t.get("exam_weight_pct", 0) for t in topics_list)
    if total_weight == 0:
        total_weight = len(topics_list) or 1  # avoid divide-by-zero

    # ── Step 1: select learning paths per topic ───────────────────────
    topics_allocated: list[dict] = []
    for topic in sorted(
        topics_list,
        key=lambda t: t.get("exam_weight_pct", 0),
        reverse=True,
    ):
        weight: float = topic.get("exam_weight_pct", 0)
        paths: list[dict] = topic.get("learning_paths", [])
        # Proportional hour budget for this topic
        allocated_hours: float = (weight / total_weight) * total_hours

        selected: list[dict] = []
        hours_used: float = 0.0
        # Sort paths shortest-first so we fit as many as possible
        for path in sorted(paths, key=lambda p: p.get("duration_hours", 0)):
            path_hours: float = path.get("duration_hours", 0.0)
            if prioritize_by_date and hours_used + path_hours > allocated_hours * 1.15:
                break
            selected.append(path)
            hours_used += path_hours

        topics_allocated.append(
            {
                "topic": topic.get("name", ""),
                "exam_weight_pct": weight,
                "allocated_hours": round(allocated_hours, 1),
                "selected_hours": round(hours_used, 1),
                "selected_paths": selected,
                "paths_skipped": len(paths) - len(selected),
            }
        )

    # ── Step 2: build weekly calendar ────────────────────────────────
    weekly_plan: list[dict] = []
    week_num = 1
    week_hours = 0.0
    week_items: list[dict] = []

    for topic_info in topics_allocated:
        for path in topic_info["selected_paths"]:
            hrs = path.get("duration_hours", 0.0)
            if week_hours + hrs > hours_per_week and week_items:
                weekly_plan.append(
                    {
                        "week": week_num,
                        "hours": round(week_hours, 1),
                        "items": week_items,
                    }
                )
                week_num += 1
                week_hours = 0.0
                week_items = []
            week_items.append(
                {
                    "topic": topic_info["topic"],
                    "learning_path": path.get("name", ""),
                    "url": path.get("url", ""),
                    "hours": hrs,
                }
            )
            week_hours += hrs

    if week_items:
        weekly_plan.append(
            {"week": week_num, "hours": round(week_hours, 1), "items": week_items}
        )

    total_planned = sum(w["hours"] for w in weekly_plan)
    coverage_pct = min(100, round((total_hours / max(total_planned, 0.01)) * 100))

    notes: list[str] = []
    if total_planned > total_hours:
        notes.append(
            f"⚠️ Content selected ({round(total_planned, 1)}h) exceeds available "
            f"time ({round(total_hours, 1)}h). Lower-weight paths were excluded."
        )
    else:
        notes.append(
            f"✅ Selected content ({round(total_planned, 1)}h) fits within "
            f"available time ({round(total_hours, 1)}h)."
        )

    weeks_needed = len(weekly_plan)
    if prioritize_by_date and weeks_needed > total_weeks:
        notes.append(
            f"⚠️ Schedule spans {weeks_needed} weeks but exam is in "
            f"{total_weeks} weeks. Consider increasing daily study time."
        )

    return json.dumps(
        {
            "total_hours_available": round(total_hours, 1),
            "total_hours_planned": round(total_planned, 1),
            "total_weeks_needed": weeks_needed,
            "coverage_pct": coverage_pct,
            "topics_summary": [
                {
                    "topic": t["topic"],
                    "exam_weight_pct": t["exam_weight_pct"],
                    "selected_hours": t["selected_hours"],
                    "paths_skipped": t["paths_skipped"],
                }
                for t in topics_allocated
            ],
            "weekly_plan": weekly_plan,
            "notes": notes,
        },
        indent=2,
    )
