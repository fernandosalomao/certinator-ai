"""
Certinator AI — Exam Topic Utilities

Helper functions for extracting exam topic names and weight
distributions from MS Learn learning-path data.
"""

from __future__ import annotations

from typing import Any

from executors.models import LearningPathFetcherResponse


def extract_topic_distribution(
    response: Any,
) -> list[dict]:
    """Extract topic names and exam weights from a structured response.

    Uses learning path names as topic areas. Prefers the
    ``exam_weight_pct`` field when available (set by the agent
    from official exam topic weights); falls back to deriving
    proportional weights from durations.

    Parameters:
        response (Any): Agent response (may have ``.value``).

    Returns:
        list[dict]: Topic dictionaries with ``name``
            and ``weight_pct`` keys.
    """
    structured = getattr(response, "value", None)

    # Import the robust parser that handles string/dict/validated responses
    from executors.learning_path_fetcher_executor import (
        LearningPathFetcherExecutor,
    )

    parsed = LearningPathFetcherExecutor._parse_response_value(response)
    if parsed is not None:
        structured = parsed

    if isinstance(structured, dict):
        try:
            structured = LearningPathFetcherResponse.model_validate(
                structured,
            )
        except Exception:
            return []

    if not isinstance(structured, LearningPathFetcherResponse):
        return []

    paths = structured.learning_paths
    if not paths:
        return []

    # Collect exam skills from modules (skill info is at module level).
    skill_weights: dict[str, float] = {}
    for lp in paths:
        for mod in lp.modules:
            skill = mod.exam_skill
            if skill and skill not in skill_weights:
                skill_weights[skill] = mod.exam_weight_pct

    has_exam_weights = any(w > 0 for w in skill_weights.values())

    if has_exam_weights and skill_weights:
        # Normalise so weights sum to 100
        total_weight = sum(skill_weights.values()) or 1
        return [
            {
                "name": skill,
                "weight_pct": max(round(weight / total_weight * 100), 1),
            }
            for skill, weight in skill_weights.items()
        ]

    # Fallback: derive weights from durations
    total_minutes = sum(lp.duration_minutes for lp in paths) or 1
    result: list[dict] = []
    cumulative = 0
    for i, lp in enumerate(paths):
        if i == len(paths) - 1:
            pct = 100 - cumulative
        else:
            pct = round(lp.duration_minutes / total_minutes * 100)
            cumulative += pct
        result.append({"name": lp.title, "weight_pct": max(pct, 1)})
    return result
