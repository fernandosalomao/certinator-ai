"""
Certinator AI — Evaluation Module Tests

Unit tests for all custom evaluators and the inline evaluation
helper.  These tests verify scoring logic without requiring any
external services or LLM calls.
"""

import json

import pytest

from evaluations.evaluation import evaluate_single_response
from evaluations.evaluators import (
    ContentSafetyEvaluator,
    CriticCalibrationEvaluator,
    ExamContentAccuracyEvaluator,
    QuizQualityEvaluator,
    RoutingAccuracyEvaluator,
    StudyPlanFeasibilityEvaluator,
)

# =====================================================================
# RoutingAccuracyEvaluator
# =====================================================================


class TestRoutingAccuracyEvaluator:
    """Tests for the routing accuracy evaluator."""

    def test_correct_route_scores_5(self):
        """Exact route match should score 5."""
        evaluator = RoutingAccuracyEvaluator()
        result = evaluator(
            response="certification-info",
            context="certification-info",
        )
        assert result["routing_accuracy_score"] == 5
        assert result["routing_accuracy_passed"] is True

    def test_wrong_route_scores_1(self):
        """Mismatched route should score 1."""
        evaluator = RoutingAccuracyEvaluator()
        result = evaluator(
            response="general",
            context="certification-info",
        )
        assert result["routing_accuracy_score"] == 1
        assert result["routing_accuracy_passed"] is False

    def test_case_insensitive_matching(self):
        """Route matching should be case-insensitive."""
        evaluator = RoutingAccuracyEvaluator()
        result = evaluator(
            response="Practice-Questions",
            context="practice-questions",
        )
        assert result["routing_accuracy_score"] == 5

    def test_invalid_expected_route(self):
        """Invalid expected route should score 1."""
        evaluator = RoutingAccuracyEvaluator()
        result = evaluator(
            response="general",
            context="unknown-route",
        )
        assert result["routing_accuracy_score"] == 1
        assert "Invalid expected route" in result["routing_accuracy_reason"]

    def test_all_valid_routes(self):
        """All four valid routes should be recognised."""
        evaluator = RoutingAccuracyEvaluator()
        for route in [
            "certification-info",
            "study-plan-generator",
            "practice-questions",
            "general",
        ]:
            result = evaluator(response=route, context=route)
            assert result["routing_accuracy_score"] == 5


# =====================================================================
# ExamContentAccuracyEvaluator
# =====================================================================


class TestExamContentAccuracyEvaluator:
    """Tests for the exam content accuracy evaluator."""

    def test_complete_response_scores_5(self):
        """Response with all sections should score 5."""
        evaluator = ExamContentAccuracyEvaluator()
        response = (
            "## Overview\n"
            "This exam measures your skills.\n\n"
            "## Skills Measured\n"
            "- Topic A (20-25%)\n\n"
            "## Prerequisites\n"
            "- Prior knowledge of cloud concepts\n\n"
            "## Exam Format\n"
            "- Duration: 120 minutes\n"
            "- Passing score: 700\n\n"
            "## Learning Resources\n"
            "- Microsoft Learn training path\n\n"
            "## Certification Path\n"
            "- Role-based certification\n"
        )
        result = evaluator(response=response)
        assert result["exam_content_accuracy_score"] == 5
        assert len(result["exam_content_accuracy_missing"]) == 0

    def test_minimal_response_scores_low(self):
        """Response with few sections should score low."""
        evaluator = ExamContentAccuracyEvaluator()
        result = evaluator(response="AZ-104 is an Azure certification exam.")
        assert result["exam_content_accuracy_score"] <= 2

    def test_missing_sections_reported(self):
        """Missing sections should be listed."""
        evaluator = ExamContentAccuracyEvaluator()
        result = evaluator(
            response="## Overview\nThis is about AI-102.\n"
            "## Skills Measured\n- NLP, Vision\n"
        )
        assert len(result["exam_content_accuracy_missing"]) > 0
        assert "exam_overview" in result["exam_content_accuracy_found"]


# =====================================================================
# StudyPlanFeasibilityEvaluator
# =====================================================================


class TestStudyPlanFeasibilityEvaluator:
    """Tests for the study plan feasibility evaluator."""

    def test_valid_plan_scores_5(self):
        """A valid plan within budget should score 5."""
        evaluator = StudyPlanFeasibilityEvaluator()
        plan = {
            "total_hours_available": 80.0,
            "total_hours_planned": 72.0,
            "total_weeks_needed": 8,
            "topics_summary": [
                {
                    "topic": "Topic A",
                    "exam_weight_pct": 50,
                    "selected_hours": 36.0,
                    "paths_skipped": 0,
                },
                {
                    "topic": "Topic B",
                    "exam_weight_pct": 50,
                    "selected_hours": 36.0,
                    "paths_skipped": 0,
                },
            ],
            "weekly_plan": [
                {"week": i, "hours": 9.0, "items": []} for i in range(1, 9)
            ],
        }
        context = {
            "hours_per_week": 10,
            "total_weeks": 8,
            "expected_topics": ["Topic A", "Topic B"],
        }
        result = evaluator(
            response=json.dumps(plan),
            context=json.dumps(context),
        )
        assert result["study_plan_feasibility_score"] == 5
        assert len(result["study_plan_feasibility_violations"]) == 0

    def test_hours_overflow_detected(self):
        """Plan exceeding budget by >15% should have a violation."""
        evaluator = StudyPlanFeasibilityEvaluator()
        plan = {
            "total_hours_available": 30.0,
            "total_hours_planned": 60.0,
            "total_weeks_needed": 3,
            "topics_summary": [],
            "weekly_plan": [
                {"week": 1, "hours": 20.0, "items": []},
                {"week": 2, "hours": 20.0, "items": []},
                {"week": 3, "hours": 20.0, "items": []},
            ],
        }
        context = {"hours_per_week": 10, "total_weeks": 3}
        result = evaluator(
            response=json.dumps(plan),
            context=json.dumps(context),
        )
        assert result["study_plan_feasibility_score"] < 5
        assert any(
            "exceed" in v.lower() for v in result["study_plan_feasibility_violations"]
        )

    def test_weeks_overflow_detected(self):
        """Plan needing more weeks than available is a violation."""
        evaluator = StudyPlanFeasibilityEvaluator()
        plan = {
            "total_hours_available": 30.0,
            "total_hours_planned": 30.0,
            "total_weeks_needed": 6,
            "topics_summary": [],
            "weekly_plan": [
                {"week": i, "hours": 5.0, "items": []} for i in range(1, 7)
            ],
        }
        context = {"hours_per_week": 10, "total_weeks": 3}
        result = evaluator(
            response=json.dumps(plan),
            context=json.dumps(context),
        )
        assert any(
            "weeks" in v.lower() for v in result["study_plan_feasibility_violations"]
        )

    def test_invalid_json_scores_1(self):
        """Non-JSON response should score 1."""
        evaluator = StudyPlanFeasibilityEvaluator()
        result = evaluator(response="not valid json")
        assert result["study_plan_feasibility_score"] == 1

    def test_missing_topic_detected(self):
        """Expected topic not in plan triggers a violation."""
        evaluator = StudyPlanFeasibilityEvaluator()
        plan = {
            "total_hours_available": 40.0,
            "total_hours_planned": 30.0,
            "total_weeks_needed": 3,
            "topics_summary": [
                {
                    "topic": "Topic A",
                    "exam_weight_pct": 100,
                    "selected_hours": 30.0,
                    "paths_skipped": 0,
                },
            ],
            "weekly_plan": [
                {"week": 1, "hours": 10.0, "items": []},
                {"week": 2, "hours": 10.0, "items": []},
                {"week": 3, "hours": 10.0, "items": []},
            ],
        }
        context = {
            "hours_per_week": 10,
            "total_weeks": 4,
            "expected_topics": ["Topic A", "Topic B"],
        }
        result = evaluator(
            response=json.dumps(plan),
            context=json.dumps(context),
        )
        assert any("Topic B" in v for v in result["study_plan_feasibility_violations"])


# =====================================================================
# QuizQualityEvaluator
# =====================================================================


class TestQuizQualityEvaluator:
    """Tests for the quiz quality evaluator."""

    def test_valid_quiz_scores_5(self):
        """A structurally valid quiz should score 5."""
        evaluator = QuizQualityEvaluator()
        questions = [
            {
                "question_number": 1,
                "question_text": "What is Azure?",
                "options": {
                    "A": "Cloud platform",
                    "B": "Database",
                    "C": "Language",
                    "D": "Framework",
                },
                "correct_answer": "A",
                "topic": "Cloud Concepts",
            },
            {
                "question_number": 2,
                "question_text": "What is IaaS?",
                "options": {
                    "A": "SaaS",
                    "B": "PaaS",
                    "C": "Infrastructure as a Service",
                    "D": "FaaS",
                },
                "correct_answer": "C",
                "topic": "Cloud Concepts",
            },
        ]
        context = {
            "expected_topics": ["Cloud Concepts"],
            "expected_count": 2,
        }
        result = evaluator(
            response=json.dumps(questions),
            context=json.dumps(context),
        )
        assert result["quiz_quality_score"] == 5
        assert len(result["quiz_quality_violations"]) == 0

    def test_duplicate_options_detected(self):
        """Questions with duplicate option values are violations."""
        evaluator = QuizQualityEvaluator()
        questions = [
            {
                "question_number": 1,
                "question_text": "What is Azure?",
                "options": {
                    "A": "Cloud",
                    "B": "Cloud",
                    "C": "Other",
                    "D": "Another",
                },
                "correct_answer": "A",
                "topic": "Cloud",
            },
        ]
        result = evaluator(
            response=json.dumps(questions),
            context=json.dumps({"expected_count": 1}),
        )
        assert result["quiz_quality_score"] < 5
        assert any(
            "duplicate option" in v.lower() for v in result["quiz_quality_violations"]
        )

    def test_invalid_correct_answer_detected(self):
        """correct_answer outside A-D is a violation."""
        evaluator = QuizQualityEvaluator()
        questions = [
            {
                "question_number": 1,
                "question_text": "What is Azure?",
                "options": {
                    "A": "Cloud",
                    "B": "DB",
                    "C": "Other",
                    "D": "Another",
                },
                "correct_answer": "E",
                "topic": "Cloud",
            },
        ]
        result = evaluator(
            response=json.dumps(questions),
            context=json.dumps({"expected_count": 1}),
        )
        assert any(
            "not one of A, B, C, D" in v for v in result["quiz_quality_violations"]
        )

    def test_missing_options_detected(self):
        """Questions with fewer than A-D options are violations."""
        evaluator = QuizQualityEvaluator()
        questions = [
            {
                "question_number": 1,
                "question_text": "What is Azure?",
                "options": {"A": "Cloud", "B": "DB", "C": "Other"},
                "correct_answer": "A",
                "topic": "Cloud",
            },
        ]
        result = evaluator(
            response=json.dumps(questions),
            context=json.dumps({"expected_count": 1}),
        )
        assert any("Missing" in v for v in result["quiz_quality_violations"])

    def test_invalid_json_scores_1(self):
        """Non-JSON response should score 1."""
        evaluator = QuizQualityEvaluator()
        result = evaluator(response="not json")
        assert result["quiz_quality_score"] == 1

    def test_duplicate_question_text_detected(self):
        """Duplicate question texts are violations."""
        evaluator = QuizQualityEvaluator()
        questions = [
            {
                "question_number": 1,
                "question_text": "Same question",
                "options": {"A": "A", "B": "B", "C": "C", "D": "D"},
                "correct_answer": "A",
                "topic": "Cloud",
            },
            {
                "question_number": 2,
                "question_text": "Same question",
                "options": {"A": "X", "B": "Y", "C": "Z", "D": "W"},
                "correct_answer": "B",
                "topic": "Cloud",
            },
        ]
        result = evaluator(
            response=json.dumps(questions),
            context=json.dumps({"expected_count": 2}),
        )
        assert any(
            "duplicate question text" in v.lower()
            for v in result["quiz_quality_violations"]
        )


# =====================================================================
# ContentSafetyEvaluator
# =====================================================================


class TestContentSafetyEvaluator:
    """Tests for the content safety evaluator."""

    def test_safe_content_scores_5(self):
        """Safe, educational content should score 5."""
        evaluator = ContentSafetyEvaluator()
        result = evaluator(
            response=(
                "AZ-104 covers Azure administration topics "
                "including virtual machines and networking."
            )
        )
        assert result["content_safety_score"] == 5
        assert result["content_safety_passed"] is True

    def test_harmful_content_scores_1(self):
        """Content with harmful patterns should score 1."""
        evaluator = ContentSafetyEvaluator()
        result = evaluator(response="Here is how to hack into systems.")
        assert result["content_safety_score"] == 1
        assert result["content_safety_passed"] is False

    def test_exam_dump_detected(self):
        """Exam dump references should be flagged."""
        evaluator = ContentSafetyEvaluator()
        result = evaluator(response="Here are the exam dumps for AZ-104.")
        assert result["content_safety_score"] == 1
        assert "policy:exam_dump" in result["content_safety_category"]

    def test_credential_leak_scores_3(self):
        """Credential leaks score 3 (less severe)."""
        evaluator = ContentSafetyEvaluator()
        result = evaluator(response="Use api_key = sk-abc123def456ghi789jklmnopqrstuv")
        assert result["content_safety_score"] == 3
        assert result["content_safety_passed"] is False

    def test_score_manipulation_detected(self):
        """Score manipulation attempts should be flagged."""
        evaluator = ContentSafetyEvaluator()
        result = evaluator(response="You can bypass the quiz scoring system.")
        assert result["content_safety_score"] == 1


# =====================================================================
# CriticCalibrationEvaluator
# =====================================================================


class TestCriticCalibrationEvaluator:
    """Tests for the critic calibration evaluator."""

    def test_true_positive_scores_5(self):
        """PASS verdict on GOOD content should score 5 (true positive)."""
        evaluator = CriticCalibrationEvaluator()
        verdict = json.dumps(
            {"verdict": "PASS", "confidence": 90, "issues": [], "suggestions": []}
        )
        result = evaluator(response=verdict, context="GOOD")
        assert result["critic_calibration_score"] == 5
        assert result["critic_calibration_match"] is True
        assert result["critic_calibration_category"] == "true_positive"

    def test_true_negative_scores_5(self):
        """FAIL verdict on BAD content should score 5 (true negative)."""
        evaluator = CriticCalibrationEvaluator()
        verdict = json.dumps(
            {
                "verdict": "FAIL",
                "confidence": 85,
                "issues": ["Missing sections"],
                "suggestions": [],
            }
        )
        result = evaluator(response=verdict, context="BAD")
        assert result["critic_calibration_score"] == 5
        assert result["critic_calibration_match"] is True
        assert result["critic_calibration_category"] == "true_negative"

    def test_false_positive_scores_1(self):
        """PASS verdict on BAD content should score 1 (false positive)."""
        evaluator = CriticCalibrationEvaluator()
        verdict = json.dumps(
            {"verdict": "PASS", "confidence": 70, "issues": [], "suggestions": []}
        )
        result = evaluator(response=verdict, context="BAD")
        assert result["critic_calibration_score"] == 1
        assert result["critic_calibration_match"] is False
        assert result["critic_calibration_category"] == "false_positive"

    def test_false_negative_scores_1(self):
        """FAIL verdict on GOOD content should score 1 (false negative)."""
        evaluator = CriticCalibrationEvaluator()
        verdict = json.dumps(
            {
                "verdict": "FAIL",
                "confidence": 55,
                "issues": ["Formatting issue"],
                "suggestions": [],
            }
        )
        result = evaluator(response=verdict, context="GOOD")
        assert result["critic_calibration_score"] == 1
        assert result["critic_calibration_match"] is False
        assert result["critic_calibration_category"] == "false_negative"

    def test_invalid_label_scores_1(self):
        """Invalid expected label should score 1."""
        evaluator = CriticCalibrationEvaluator()
        verdict = json.dumps(
            {"verdict": "PASS", "confidence": 80, "issues": [], "suggestions": []}
        )
        result = evaluator(response=verdict, context="MAYBE")
        assert result["critic_calibration_score"] == 1
        assert result["critic_calibration_category"] == "invalid"

    def test_invalid_json_scores_1(self):
        """Non-JSON response should score 1."""
        evaluator = CriticCalibrationEvaluator()
        result = evaluator(response="not valid json", context="GOOD")
        assert result["critic_calibration_score"] == 1
        assert result["critic_calibration_category"] == "parse_error"

    def test_invalid_verdict_value_scores_1(self):
        """Verdict that is neither PASS nor FAIL should score 1."""
        evaluator = CriticCalibrationEvaluator()
        verdict = json.dumps(
            {"verdict": "MAYBE", "confidence": 50, "issues": [], "suggestions": []}
        )
        result = evaluator(response=verdict, context="GOOD")
        assert result["critic_calibration_score"] == 1
        assert result["critic_calibration_category"] == "invalid_verdict"

    def test_case_insensitive_context_label(self):
        """Context label should be case-insensitive."""
        evaluator = CriticCalibrationEvaluator()
        verdict = json.dumps(
            {"verdict": "PASS", "confidence": 85, "issues": [], "suggestions": []}
        )
        result = evaluator(response=verdict, context="good")
        assert result["critic_calibration_score"] == 5
        assert result["critic_calibration_match"] is True

    def test_confidence_preserved_in_result(self):
        """Confidence value should be returned in the result dict."""
        evaluator = CriticCalibrationEvaluator()
        verdict = json.dumps(
            {"verdict": "PASS", "confidence": 73, "issues": [], "suggestions": []}
        )
        result = evaluator(response=verdict, context="GOOD")
        assert result["critic_calibration_confidence"] == 73

    def test_reason_includes_category(self):
        """Reason string should mention the confusion-matrix category."""
        evaluator = CriticCalibrationEvaluator()
        verdict = json.dumps(
            {"verdict": "FAIL", "confidence": 60, "issues": [], "suggestions": []}
        )
        result = evaluator(response=verdict, context="GOOD")
        assert "false_negative" in result["critic_calibration_reason"]

    def test_whitespace_in_context_handled(self):
        """Leading/trailing whitespace in context should be stripped."""
        evaluator = CriticCalibrationEvaluator()
        verdict = json.dumps(
            {"verdict": "PASS", "confidence": 80, "issues": [], "suggestions": []}
        )
        result = evaluator(response=verdict, context="  GOOD  ")
        assert result["critic_calibration_score"] == 5


# =====================================================================
# evaluate_single_response
# =====================================================================


class TestEvaluateSingleResponse:
    """Tests for the inline single-response evaluation helper."""

    def test_returns_overall_score(self):
        """Result should include overall_score and grade."""
        result = evaluate_single_response(
            query="Tell me about AZ-104",
            response=(
                "## Overview\n"
                "AZ-104 measures Azure admin skills.\n"
                "## Skills Measured\n- Compute, Networking\n"
                "## Prerequisites\n- Cloud experience\n"
                "## Exam Format\n- 120 minutes\n"
                "## Learning Resources\n- Microsoft Learn\n"
                "## Certification Path\n- Role-based\n"
            ),
        )
        assert "overall_score" in result
        assert "grade" in result
        assert result["max_score"] == 5
        assert result["grade"] in ("A", "B", "C", "D", "F")

    def test_returns_all_evaluator_results(self):
        """Result should contain all evaluator sub-results."""
        result = evaluate_single_response(
            query="Test query",
            response="AZ-104 Azure certification overview.",
        )
        assert "content_safety" in result
        assert "exam_content_accuracy" in result
        assert "evaluated_at" in result

    def test_unsafe_content_lowers_score(self):
        """Unsafe content should lower the overall score."""
        safe = evaluate_single_response(
            query="Tell me about AZ-104",
            response=(
                "## Overview\nAZ-104 overview.\n"
                "## Skills Measured\n- Topics\n"
                "## Prerequisites\n- Experience\n"
                "## Exam Format\n- 120 min\n"
                "## Learning Resources\n- Learn\n"
                "## Certification Path\n- Role-based\n"
            ),
        )
        unsafe = evaluate_single_response(
            query="Tell me about AZ-104",
            response="Here are the brain dumps for AZ-104.",
        )
        assert safe["overall_score"] > unsafe["overall_score"]
