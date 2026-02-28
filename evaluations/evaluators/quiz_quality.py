"""
Certinator AI — Quiz Quality Evaluator

Deterministic evaluator that validates practice questions for
structural correctness.  Reuses the same validation logic as
``tools.practice.validate_questions()`` but wraps it in the
evaluator scoring protocol.

Checks:
    1. Response is valid JSON array of question objects.
    2. Each question has exactly options A, B, C, D.
    3. Option values are all distinct within each question.
    4. ``correct_answer`` is one of A, B, C, D.
    5. No duplicate ``question_text`` across questions.
    6. All expected topics (from context) are covered.

Scoring (1-5 scale):
    5 — All checks pass
    4 — 1 violation
    3 — 2 violations
    2 — 3 violations
    1 — 4+ violations or invalid JSON
"""

from __future__ import annotations

import json


class QuizQualityEvaluator:
    """Validate practice question batches for structural integrity.

    Dataset columns required:
        - ``response``: JSON array of question objects.
        - ``context``: JSON with ``expected_topics`` (list[str])
          and ``expected_count`` (int).
    """

    def __call__(
        self,
        *,
        response: str,
        context: str = "",
        **kwargs: object,
    ) -> dict:
        """Evaluate quality of a practice question batch.

        Parameters:
            response (str): JSON array of question dicts.
            context (str): JSON with expected_topics / count.

        Returns:
            dict: Score, violations list, and explanation.
        """
        # ── Parse response ───────────────────────────────────────
        try:
            questions = json.loads(response)
            if not isinstance(questions, list):
                raise ValueError("Expected a JSON array.")
        except (json.JSONDecodeError, TypeError, ValueError):
            return {
                "quiz_quality_score": 1,
                "quiz_quality_violations": [
                    "Response is not a valid JSON array of questions."
                ],
                "quiz_quality_reason": (
                    "Cannot evaluate: response is not a valid JSON array."
                ),
            }

        # ── Parse context ────────────────────────────────────────
        try:
            ctx = json.loads(context) if context else {}
        except (json.JSONDecodeError, TypeError):
            ctx = {}

        expected_topics: list[str] = ctx.get("expected_topics", [])
        expected_count: int = ctx.get("expected_count", len(questions))

        violations: list[str] = []
        valid_letters = {"A", "B", "C", "D"}
        seen_texts: set[str] = set()
        covered_topics: set[str] = set()

        # ── Count check ─────────────────────────────────────────
        if len(questions) != expected_count:
            violations.append(
                f"Expected {expected_count} questions but received {len(questions)}."
            )

        for idx, q in enumerate(questions):
            num = q.get("question_number", idx + 1)
            options: dict = q.get("options", {})
            correct: str = str(q.get("correct_answer", "")).strip().upper()
            text: str = q.get("question_text", "").strip()
            topic: str = q.get("topic", "").strip()

            # Options keys must be exactly A, B, C, D
            option_keys = {k.strip().upper() for k in options.keys()}
            if option_keys != valid_letters:
                missing = valid_letters - option_keys
                extra = option_keys - valid_letters
                msg = f"Q{num}: invalid option keys."
                if missing:
                    msg += f" Missing: {sorted(missing)}."
                if extra:
                    msg += f" Unexpected: {sorted(extra)}."
                violations.append(msg)

            # Option values must all be distinct
            option_values = [str(v).strip() for v in options.values()]
            if len(set(option_values)) < len(option_values):
                violations.append(f"Q{num}: duplicate option values.")

            # correct_answer must be A/B/C/D
            if correct not in valid_letters:
                violations.append(
                    f"Q{num}: correct_answer '{correct}' is not one of A, B, C, D."
                )

            # No duplicate question_text
            normalised = text.lower()
            if normalised in seen_texts:
                violations.append(f"Q{num}: duplicate question text.")
            else:
                seen_texts.add(normalised)

            if topic:
                covered_topics.add(topic)

        # ── Topic coverage ───────────────────────────────────────
        for expected in expected_topics:
            matched = any(
                expected.lower() in t.lower() or t.lower() in expected.lower()
                for t in covered_topics
            )
            if not matched:
                violations.append(f"No question covers topic '{expected}'.")

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
            "quiz_quality_score": score,
            "quiz_quality_violations": violations,
            "quiz_quality_reason": (
                "All structural checks passed."
                if not violations
                else f"{num_violations} violation(s): " + "; ".join(violations)
            ),
        }
