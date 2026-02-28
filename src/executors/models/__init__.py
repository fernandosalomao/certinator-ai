"""
Certinator AI — Executor data models.

Typed data-transfer objects that flow between workflow nodes.

Re-exports all model classes from domain-specific sub-modules
for backward-compatible ``from executors.models import X`` usage.
"""

from .critic import CriticVerdict, CriticVerdictResponse, SpecialistOutput
from .cross_workflow import (
    ApprovedStudyPlanOutput,
    RevisionRequest,
    StudyPlanFromQuizRequest,
)
from .learning_paths import (
    LearningPath,
    LearningPathFetcherResponse,
    LearningPathsData,
    SkillAtAGlance,
    TrainingModule,
)
from .practice import PracticeQuestion, QuizState
from .routing import CoordinatorResponse, RoutingDecision
from .scheduling import (
    ScheduleResult,
    ScheduleWeek,
    ScheduleWeekItem,
    SkillSummaryItem,
    SkippedModule,
    StudyConstraints,
)

__all__ = [
    # Routing
    "RoutingDecision",
    "CoordinatorResponse",
    # Scheduling
    "ScheduleWeekItem",
    "ScheduleWeek",
    "SkillSummaryItem",
    "SkippedModule",
    "ScheduleResult",
    "StudyConstraints",
    # Critic
    "CriticVerdict",
    "CriticVerdictResponse",
    "SpecialistOutput",
    # Learning paths
    "TrainingModule",
    "SkillAtAGlance",
    "LearningPath",
    "LearningPathFetcherResponse",
    "LearningPathsData",
    # Practice
    "PracticeQuestion",
    "QuizState",
    # Cross-workflow
    "RevisionRequest",
    "StudyPlanFromQuizRequest",
    "ApprovedStudyPlanOutput",
]
