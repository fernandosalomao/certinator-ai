"""
Certinator AI — Cross-workflow routing data models.

Typed messages that flow between major workflow routes:
revision requests, post-quiz study plan requests,
and approved study plan outputs.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from .routing import RoutingDecision


class RevisionRequest(BaseModel):
    """Feedback from the Critic, sent back to a specialist for revision.

    The CriticExecutor emits this when a verdict is FAIL and the
    iteration cap has not been reached.  Conditional edges route it
    to the correct specialist handler based on ``source_executor_id``.
    """

    original_decision: RoutingDecision = Field(
        description="Original routing decision for context.",
    )
    previous_content: str = Field(
        description="The content that failed validation.",
    )
    feedback: list[str] = Field(
        default_factory=list,
        description="Combined issues and suggestions from the Critic.",
    )
    iteration: int = Field(
        description="Current iteration number (already incremented).",
    )
    source_executor_id: str = Field(
        description="ID of the handler that should revise.",
    )


class StudyPlanFromQuizRequest(BaseModel):
    """Routes from a failed quiz to the study plan pipeline.

    Emitted by PracticeQuestionsExecutor when the student fails and
    wants a focused study plan.  Routed to LearningPathFetcherExecutor.
    """

    certification: str = Field(
        description="Exam code (e.g. AZ-900).",
    )
    weak_topics: list[str] = Field(
        description="Topics the student struggled with.",
    )
    quiz_score: int = Field(
        description="Overall quiz score percentage.",
    )
    original_decision: RoutingDecision = Field(
        description="Routing decision for the study plan pipeline.",
    )


class ApprovedStudyPlanOutput(BaseModel):
    """Critic-approved study plan forwarded to PostStudyPlanExecutor.

    Emitted by CriticExecutor on PASS for study_plan content so that
    PostStudyPlanExecutor can offer practice questions via HITL.
    """

    content: str = Field(
        description="The approved study plan text.",
    )
    certification: str = Field(
        description="Exam code (e.g. AZ-900).",
    )
    original_decision: RoutingDecision = Field(
        description="Original routing decision for context.",
    )
