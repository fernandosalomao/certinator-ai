"""
Certinator AI — Routing Accuracy Evaluator

Measures whether the Coordinator agent routes user queries to
the correct specialist.  Uses exact-match against a labeled
``expected_route`` field in the evaluation dataset.

Scoring (1-5 scale):
    5 — Exact route match
    1 — Wrong route
"""

from __future__ import annotations

VALID_ROUTES = {
    "certification-info",
    "study-plan-generator",
    "practice-questions",
    "general",
}


class RoutingAccuracyEvaluator:
    """Check if the predicted route matches the expected route.

    Dataset columns required:
        - ``response``: The predicted route string (e.g.
          ``"certification-info"``).
        - ``context``: The expected route string (e.g.
          ``"certification-info"``).
    """

    def __call__(
        self,
        *,
        response: str,
        context: str = "",
        **kwargs: object,
    ) -> dict:
        """Evaluate routing accuracy for a single query.

        Parameters:
            response (str): Predicted route from the Coordinator.
            context (str): Expected (ground-truth) route.

        Returns:
            dict: Score and explanation.
        """
        predicted = response.strip().lower()
        expected = context.strip().lower()

        # Validate that expected route is a known route.
        if expected not in VALID_ROUTES:
            return {
                "routing_accuracy_score": 1,
                "routing_accuracy_passed": False,
                "routing_accuracy_reason": (
                    f"Invalid expected route '{expected}'. "
                    f"Must be one of: {sorted(VALID_ROUTES)}."
                ),
            }

        is_correct = predicted == expected
        score = 5 if is_correct else 1

        return {
            "routing_accuracy_score": score,
            "routing_accuracy_passed": is_correct,
            "routing_accuracy_reason": (
                f"Predicted '{predicted}' matches expected '{expected}'."
                if is_correct
                else f"Predicted '{predicted}' but expected '{expected}'."
            ),
        }
