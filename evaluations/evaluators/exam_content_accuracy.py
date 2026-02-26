"""
Certinator AI — Exam Content Accuracy Evaluator

Checks whether certification-info responses include the key
structural sections that a complete certification overview should
contain.  This is a deterministic evaluator (no LLM needed).

Scoring (1-5 scale):
    5 — All expected sections present
    4 — 5 out of 6 sections
    3 — 4 out of 6
    2 — 3 out of 6
    1 — Fewer than 3 sections
"""

from __future__ import annotations

# Sections that a complete certification info response should cover.
# Each tuple is (section_label, list_of_indicator_phrases).
_EXPECTED_SECTIONS: list[tuple[str, list[str]]] = [
    (
        "exam_overview",
        [
            "overview",
            "about this exam",
            "exam description",
            "certification overview",
            "what is",
        ],
    ),
    (
        "skills_measured",
        [
            "skills measured",
            "skills assessed",
            "exam objectives",
            "topics covered",
            "measured skills",
            "exam topics",
        ],
    ),
    (
        "prerequisites",
        [
            "prerequisite",
            "prior knowledge",
            "recommended experience",
            "before you begin",
            "requirements",
        ],
    ),
    (
        "exam_format",
        [
            "exam format",
            "question types",
            "passing score",
            "duration",
            "number of questions",
            "exam details",
        ],
    ),
    (
        "learning_resources",
        [
            "learning path",
            "microsoft learn",
            "study resources",
            "training",
            "preparation",
            "resources",
        ],
    ),
    (
        "certification_path",
        [
            "certification path",
            "career path",
            "role-based",
            "related certifications",
            "next steps",
            "renewal",
        ],
    ),
]


class ExamContentAccuracyEvaluator:
    """Verify that cert-info responses contain expected sections.

    Dataset columns required:
        - ``response``: The agent's certification info response.
    """

    def __call__(
        self,
        *,
        response: str,
        **kwargs: object,
    ) -> dict:
        """Evaluate completeness of a certification info response.

        Parameters:
            response (str): Agent-generated certification overview.

        Returns:
            dict: Score, found/missing sections, and explanation.
        """
        text_lower = response.lower()
        found_sections: list[str] = []
        missing_sections: list[str] = []

        for section_name, indicators in _EXPECTED_SECTIONS:
            matched = any(ind in text_lower for ind in indicators)
            if matched:
                found_sections.append(section_name)
            else:
                missing_sections.append(section_name)

        count = len(found_sections)
        total = len(_EXPECTED_SECTIONS)

        # Map count → score (1-5 scale)
        if count >= total:
            score = 5
        elif count >= total - 1:
            score = 4
        elif count >= total - 2:
            score = 3
        elif count >= total - 3:
            score = 2
        else:
            score = 1

        return {
            "exam_content_accuracy_score": score,
            "exam_content_accuracy_found": found_sections,
            "exam_content_accuracy_missing": missing_sections,
            "exam_content_accuracy_reason": (
                f"Found {count}/{total} expected sections: "
                f"{', '.join(found_sections) or 'none'}."
                + (
                    f" Missing: {', '.join(missing_sections)}."
                    if missing_sections
                    else ""
                )
            ),
        }
