"""
Certinator AI — Custom Evaluators

Domain-specific evaluators for the multi-agent workflow.

Each evaluator follows the ``__call__(*, response, **kwargs)``
protocol expected by the Azure AI Evaluation SDK ``evaluate()``
function, returning a dict with ``<name>_score`` (1-5) and a
``<name>_reason`` string.
"""

from .content_safety import ContentSafetyEvaluator
from .critic_calibration import CriticCalibrationEvaluator
from .exam_content_accuracy import ExamContentAccuracyEvaluator
from .groundedness import GroundednessEvaluator
from .quiz_quality import QuizQualityEvaluator
from .routing_accuracy import RoutingAccuracyEvaluator
from .study_plan_feasibility import StudyPlanFeasibilityEvaluator

__all__ = [
    "ContentSafetyEvaluator",
    "CriticCalibrationEvaluator",
    "ExamContentAccuracyEvaluator",
    "GroundednessEvaluator",
    "QuizQualityEvaluator",
    "RoutingAccuracyEvaluator",
    "StudyPlanFeasibilityEvaluator",
]
