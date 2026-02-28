"""
Certinator AI — Study Schedule Calculator Tool

AI function tool invoked by the study_plan_agent to compute a
week-by-week schedule from learning paths / modules and the
student's availability.  The LLM calls this tool with JSON; the
Python function does all the arithmetic and returns a structured plan
so the model never has to calculate hours itself.

Scheduling granularity is at the **module** level (modules are typically
20-60 min, ideal for weekly planning).  Modules from the same learning
path are kept together to preserve topic cohesion.
"""

from __future__ import annotations

import json
from typing import Annotated

from agent_framework import ai_function


@ai_function(
    name="schedule_study_plan",
    description=(
        "Compute a week-by-week study schedule given a list of learning "
        "paths (each with modules and their durations in minutes) and the "
        "student's available hours. Returns a JSON object with the full "
        "plan, coverage stats, and notes."
    ),
)
def schedule_study_plan(
    learning_paths: Annotated[
        str,
        (
            "JSON array of learning path objects. Each object must have: "
            "name (str), url (str), duration_minutes (number), "
            "module_count (int), modules (array of "
            "{name: str, url: str, duration_minutes: number, unit_count: int}). "
            "Example: "
            '[{"name":"AZ-104: Prerequisites","url":"https://...","duration_minutes":63,'
            '"module_count":2,"modules":[{"name":"Intro to Cloud Shell",'
            '"url":"https://...","duration_minutes":20,"unit_count":6}]}]'
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
            "When True, cap content to fit within total_weeks by skipping "
            "lower-priority modules. When False (no exam deadline), "
            "include all modules regardless of time."
        ),
    ],
) -> str:
    """
    Calculate a feasible study schedule from learning paths and modules.

    Scheduling logic:
    1. Flatten all modules from all learning paths, preserving learning
       path ordering (prerequisites first).
    2. If prioritize_by_date is True, drop trailing modules that exceed
       the total available hours.
    3. Distribute modules into weekly buckets based on hours_per_week.

    Parameters:
        learning_paths (str): JSON array of learning path objects.
        hours_per_week (float): Weekly study hours available.
        total_weeks (int): Total weeks until exam (or default 8).
        prioritize_by_date (bool): Trim content to fit deadline if True.

    Returns:
        str: JSON-encoded schedule with weekly plan, stats, and notes.
    """
    try:
        paths_list: list[dict] = json.loads(learning_paths)
    except json.JSONDecodeError as exc:
        return json.dumps({"error": f"Invalid learning_paths JSON: {exc}"})

    total_hours = hours_per_week * total_weeks

    # ── Step 1: flatten modules with learning path context ───────────
    all_modules: list[dict] = []
    path_summaries: list[dict] = []

    for lp in paths_list:
        lp_name = lp.get("name", "")
        lp_url = lp.get("url", "")
        modules = lp.get("modules", [])
        lp_duration_minutes = lp.get("duration_minutes", 0)
        lp_exam_topic = lp.get("exam_topic", "")
        lp_exam_weight_pct = lp.get("exam_weight_pct", 0)

        if modules:
            for mod in modules:
                all_modules.append(
                    {
                        "learning_path": lp_name,
                        "learning_path_url": lp_url,
                        "exam_topic": lp_exam_topic,
                        "exam_weight_pct": lp_exam_weight_pct,
                        "module": mod.get("name", ""),
                        "url": mod.get("url", ""),
                        "duration_minutes": mod.get("duration_minutes", 30.0),
                        "unit_count": mod.get("unit_count", 0),
                    }
                )
        else:
            # Learning path with no module breakdown — treat the whole
            # path as a single schedulable item.
            all_modules.append(
                {
                    "learning_path": lp_name,
                    "learning_path_url": lp_url,
                    "exam_topic": lp_exam_topic,
                    "exam_weight_pct": lp_exam_weight_pct,
                    "module": lp_name,
                    "url": lp_url,
                    "duration_minutes": lp_duration_minutes or 60.0,
                    "unit_count": 0,
                }
            )

        path_summaries.append(
            {
                "learning_path": lp_name,
                "url": lp_url,
                "duration_minutes": lp_duration_minutes,
                "module_count": len(modules),
                "exam_topic": lp_exam_topic,
                "exam_weight_pct": lp_exam_weight_pct,
            }
        )

    # ── Step 2: select modules that fit the time budget ──────────────
    total_minutes_available = total_hours * 60
    selected: list[dict] = []
    skipped: list[dict] = []
    minutes_used = 0.0

    for mod in all_modules:
        mod_minutes = mod["duration_minutes"]
        if prioritize_by_date and minutes_used + mod_minutes > total_minutes_available:
            skipped.append(mod)
        else:
            selected.append(mod)
            minutes_used += mod_minutes

    # ── Step 3: build weekly calendar ────────────────────────────────
    weekly_plan: list[dict] = []
    week_num = 1
    week_minutes = 0.0
    week_items: list[dict] = []
    minutes_per_week = hours_per_week * 60

    for mod in selected:
        mod_minutes = mod["duration_minutes"]
        if week_minutes + mod_minutes > minutes_per_week and week_items:
            weekly_plan.append(
                {
                    "week": week_num,
                    "hours": round(week_minutes / 60, 1),
                    "items": week_items,
                }
            )
            week_num += 1
            week_minutes = 0.0
            week_items = []
        week_items.append(
            {
                "learning_path": mod["learning_path"],
                "exam_topic": mod["exam_topic"],
                "exam_weight_pct": mod["exam_weight_pct"],
                "module": mod["module"],
                "url": mod["url"],
                "duration_minutes": mod_minutes,
                "hours": round(mod_minutes / 60, 2),
            }
        )
        week_minutes += mod_minutes

    if week_items:
        weekly_plan.append(
            {
                "week": week_num,
                "hours": round(week_minutes / 60, 1),
                "items": week_items,
            }
        )

    total_planned_minutes = minutes_used
    total_planned_hours = round(total_planned_minutes / 60, 1)
    weeks_needed = len(weekly_plan)
    coverage_pct = min(
        100,
        round(
            (len(selected) / max(len(all_modules), 1)) * 100,
        ),
    )

    # ── Step 4: build learning path summary ──────────────────────────
    lp_stats: list[dict] = []
    for ps in path_summaries:
        lp_name = ps["learning_path"]
        selected_for_lp = [m for m in selected if m["learning_path"] == lp_name]
        skipped_for_lp = [m for m in skipped if m["learning_path"] == lp_name]
        lp_stats.append(
            {
                "learning_path": lp_name,
                "url": ps["url"],
                "total_minutes": ps["duration_minutes"],
                "exam_topic": ps.get("exam_topic", ""),
                "exam_weight_pct": ps.get("exam_weight_pct", 0),
                "modules_included": len(selected_for_lp),
                "modules_skipped": len(skipped_for_lp),
                "selected_minutes": round(
                    sum(m["duration_minutes"] for m in selected_for_lp), 1
                ),
            }
        )

    # ── Step 5: notes ────────────────────────────────────────────────
    notes: list[str] = []
    if total_planned_hours > total_hours:
        notes.append(
            f"⚠️ Content selected ({total_planned_hours}h) exceeds available "
            f"time ({round(total_hours, 1)}h). Some modules were excluded."
        )
    else:
        notes.append(
            f"✅ Selected content ({total_planned_hours}h) fits within "
            f"available time ({round(total_hours, 1)}h)."
        )

    if skipped:
        notes.append(
            f"⚠️ {len(skipped)} module(s) skipped to fit the timeline. "
            "Consider extending your study period to cover all content."
        )

    if prioritize_by_date and weeks_needed > total_weeks:
        notes.append(
            f"⚠️ Schedule spans {weeks_needed} weeks but exam is in "
            f"{total_weeks} weeks. Consider increasing daily study time."
        )

    return json.dumps(
        {
            "total_hours_available": round(total_hours, 1),
            "total_hours_planned": total_planned_hours,
            "total_weeks_needed": weeks_needed,
            "coverage_pct": coverage_pct,
            "learning_path_summary": lp_stats,
            "weekly_plan": weekly_plan,
            "skipped_modules": [
                {
                    "learning_path": m["learning_path"],
                    "module": m["module"],
                    "url": m["url"],
                    "duration_minutes": m["duration_minutes"],
                }
                for m in skipped
            ],
            "notes": notes,
        },
        indent=2,
    )
