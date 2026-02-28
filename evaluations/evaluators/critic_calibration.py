"""
Certinator AI — Critic Calibration Evaluator

Measures whether the Critic agent's PASS/FAIL verdicts align with
human-annotated GOOD/BAD labels on specialist outputs.  Designed
to surface the Critic's false-positive rate (PASSes bad content)
and false-negative rate (FAILs good content).

Dataset columns required:
    - ``response``: Critic verdict as JSON with ``verdict`` (PASS/FAIL)
      and ``confidence`` (0-100) fields.
    - ``context``: Human-annotated label — ``"GOOD"`` or ``"BAD"``.

Per-row scoring (1-5 scale):
    5 — Verdict matches human label
    1 — Verdict contradicts human label

Aggregate metrics (computed by the orchestrator across all rows):
    - precision: TP / (TP + FP) — reliability of PASS verdicts
    - recall:    TP / (TP + FN) — fraction of GOOD content approved
    - f1:        harmonic mean of precision and recall
    - accuracy:  (TP + TN) / total
    - confidence_mae: mean |confidence/100 − correctness|, where
      correctness is 1 if the verdict is correct, else 0
"""

from __future__ import annotations

import json


class CriticCalibrationEvaluator:
    """Evaluate Critic agent accuracy against human-annotated labels.

    Each row compares the Critic's ``verdict`` (PASS → predicts GOOD,
    FAIL → predicts BAD) against the expected ``context`` label.

    Dataset columns required:
        - ``response``: Critic verdict JSON (``verdict``, ``confidence``).
        - ``context``: Expected human label (``"GOOD"`` or ``"BAD"``).
    """

    def __call__(
        self,
        *,
        response: str,
        context: str = "",
        **kwargs: object,
    ) -> dict:
        """Evaluate a single Critic verdict against its human label.

        Parameters:
            response (str): Critic verdict as JSON string containing
                ``verdict`` and ``confidence`` fields.
            context (str): Human-annotated label — ``"GOOD"`` or ``"BAD"``.

        Returns:
            dict: Per-row score, match status, confusion-matrix category,
                and parsed verdict details.
        """
        expected_label = context.strip().upper()
        if expected_label not in ("GOOD", "BAD"):
            return self._error_result(
                reason=(
                    f"Invalid expected label '{context}'. Must be 'GOOD' or 'BAD'."
                ),
                expected=expected_label,
                category="invalid",
            )

        # ── Parse critic verdict ─────────────────────────────────
        try:
            verdict_data = json.loads(response)
        except (json.JSONDecodeError, TypeError):
            return self._error_result(
                reason="Could not parse critic verdict JSON.",
                expected=expected_label,
                category="parse_error",
            )

        verdict = str(verdict_data.get("verdict", "")).strip().upper()
        confidence = int(verdict_data.get("confidence", 0))

        if verdict not in ("PASS", "FAIL"):
            return self._error_result(
                reason=(f"Invalid verdict '{verdict}'. Must be 'PASS' or 'FAIL'."),
                expected=expected_label,
                category="invalid_verdict",
                verdict=verdict,
                confidence=confidence,
            )

        # ── Compare against human label ──────────────────────────
        # Mapping: PASS → predicts GOOD, FAIL → predicts BAD
        predicted_label = "GOOD" if verdict == "PASS" else "BAD"
        is_match = predicted_label == expected_label

        # Confusion-matrix quadrant
        if verdict == "PASS" and expected_label == "GOOD":
            category = "true_positive"
        elif verdict == "FAIL" and expected_label == "BAD":
            category = "true_negative"
        elif verdict == "PASS" and expected_label == "BAD":
            category = "false_positive"
        else:  # FAIL + GOOD
            category = "false_negative"

        score = 5 if is_match else 1
        reason = (
            f"Critic {verdict} matches expected {expected_label} ({category})."
            if is_match
            else (
                f"Critic {verdict} contradicts expected {expected_label} ({category})."
            )
        )

        return {
            "critic_calibration_score": score,
            "critic_calibration_match": is_match,
            "critic_calibration_reason": reason,
            "critic_calibration_verdict": verdict,
            "critic_calibration_confidence": confidence,
            "critic_calibration_expected": expected_label,
            "critic_calibration_category": category,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _error_result(
        *,
        reason: str,
        expected: str,
        category: str,
        verdict: str = "",
        confidence: int = 0,
    ) -> dict:
        """Build a standardised error/invalid result dict."""
        return {
            "critic_calibration_score": 1,
            "critic_calibration_match": False,
            "critic_calibration_reason": reason,
            "critic_calibration_verdict": verdict,
            "critic_calibration_confidence": confidence,
            "critic_calibration_expected": expected,
            "critic_calibration_category": category,
        }
