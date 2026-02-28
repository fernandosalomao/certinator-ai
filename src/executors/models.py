"""
Certinator AI — Executor data models

Typed data-transfer objects that flow between workflow nodes.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Re-exports for convenience
# ---------------------------------------------------------------------------


class RoutingDecision(BaseModel):
    """Structured routing decision produced by the Coordinator agent."""

    reasoning: str = Field(
        default="",
        description="Chain-of-thought explanation of the routing decision.",
    )
    route: Literal[
        "certification-info", "study-plan-generator", "practice-questions", "general"
    ] = Field(
        description="Target specialist route.",
    )
    task: str = Field(
        description="Clear task description for the specialist agent.",
    )
    certification: str = Field(
        default="",
        description="Exam code such as AZ-104 or AZ-305.",
    )
    context: str = Field(
        default="",
        description="Additional user context (schedule, preferences).",
    )
    response: str = Field(
        default="",
        description="Direct response — only populated for the 'general' route.",
    )


class CoordinatorResponse(BaseModel):
    """Strict response schema used with response_format for Coordinator."""

    model_config = ConfigDict(extra="forbid")

    reasoning: str = Field(
        description=(
            "Chain-of-thought explanation of the routing decision. "
            "Think step-by-step: identify the user's primary intent, "
            "note any ambiguity or multiple intents, then justify the "
            "chosen route. Fill this BEFORE selecting the route."
        ),
    )
    route: Literal[
        "certification-info", "study-plan-generator", "practice-questions", "general"
    ] = Field(
        description="Target specialist route.",
    )
    task: str = Field(description="Clear task description for the specialist.")
    certification: str = Field(description="Exam code such as AZ-104 or AZ-305.")
    context: str = Field(description="Additional user context.")
    response: str = Field(
        description="Direct response text; used for general route.",
    )


class CriticVerdict(BaseModel):
    """Structured validation result from the Critic agent."""

    verdict: Literal["PASS", "FAIL"] = Field(default="PASS")
    confidence: int = Field(default=80, ge=0, le=100)
    issues: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)


class CriticVerdictResponse(BaseModel):
    """Strict response schema used with response_format for Critic."""

    model_config = ConfigDict(extra="forbid")

    verdict: Literal["PASS", "FAIL"] = Field()
    confidence: int = Field(ge=0, le=100)
    issues: list[str] = Field()
    suggestions: list[str] = Field()


class SpecialistOutput(BaseModel):
    """Content produced by a specialist handler, routed to the Critic.

    Flows from CertificationInfoExecutor / StudyPlanGeneratorExecutor → CriticExecutor as
    the typed message that the workflow graph routes via edges.
    """

    content: str = Field(
        description="Generated text from the specialist agent.",
    )
    content_type: str = Field(
        description=("Label such as 'certification_info' or 'study_plan'."),
    )
    source_executor_id: str = Field(
        description="ID of the executor that produced this content.",
    )
    iteration: int = Field(
        default=1,
        description="Current critic-review iteration (1-based).",
    )
    original_decision: RoutingDecision = Field(
        description=("Original routing decision for re-generation context."),
    )


class TrainingModule(BaseModel):
    """A single Microsoft Learn training module within a learning path."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(description="Title of the module.")
    url: str = Field(description="MS Learn URL for the module.")
    duration_minutes: float = Field(
        description="Estimated completion time in minutes.",
    )
    unit_count: int = Field(
        description="Number of units in the module.",
    )


class LearningPath(BaseModel):
    """An official Microsoft Learn learning path for a certification.

    Mirrors the MS Learn hierarchy: Learning Paths → Modules.
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(description="Title of the learning path.")
    url: str = Field(description="MS Learn URL for the learning path.")
    duration_minutes: float = Field(
        description="Total estimated completion time in minutes.",
    )
    module_count: int = Field(
        description="Number of modules in the learning path.",
    )
    exam_topic: str = Field(
        description=(
            "Exam topic area this learning path covers "
            "(e.g. 'Manage Azure identities and governance')."
        ),
    )
    exam_weight_pct: float = Field(
        description=(
            "Exam weight percentage for the mapped topic area. "
            "Use the midpoint of the published range "
            "(e.g. 17.5 for '15-20%')."
        ),
    )
    modules: list[TrainingModule] = Field(
        description="Modules that compose this learning path.",
    )


class LearningPathFetcherResponse(BaseModel):
    """Structured response schema for LearningPathFetcher agent output.

    Mirrors the MS Learn content hierarchy:
    Certification → Learning Paths → Modules (→ Units, not captured).
    """

    model_config = ConfigDict(extra="forbid")

    certification: str = Field(description="Exam code such as AZ-900 or AZ-104.")
    learning_paths: list[LearningPath] = Field(
        description="Official Microsoft Learn learning paths for this certification.",
    )


class LearningPathsData(BaseModel):
    """Structured output from LearningPathFetcherExecutor.

    Flows from LearningPathFetcherExecutor → StudyPlanGeneratorExecutor
    and carries the learning-path / module hierarchy the scheduler needs
    to compute a feasible study schedule.
    """

    certification: str = Field(description="Exam code such as AZ-900 or AZ-104.")
    learning_paths: list[dict] = Field(
        description=(
            "Full learning paths JSON array as returned by the fetcher "
            "agent. Each element has: name, url, duration_minutes, "
            "module_count, modules (list of {name, url, duration_minutes, "
            "unit_count})."
        ),
    )
    original_decision: "RoutingDecision" = Field(
        description=("Original routing decision preserved for downstream handlers.")
    )


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


# ---------------------------------------------------------------------------
# Practice quiz models
# ---------------------------------------------------------------------------


class PracticeQuestion(BaseModel):
    """A single multiple-choice practice question."""

    question_number: int = Field(description="1-based question number.")
    question_text: str = Field(description="The question text.")
    options: dict[str, str] = Field(
        description="Answer options keyed by letter (A, B, C, D).",
    )
    correct_answer: str = Field(
        description="The correct option letter (A, B, C, or D).",
    )
    explanation: str = Field(
        description="Explanation of why the correct answer is right.",
    )
    topic: str = Field(description="Exam topic this question covers.")
    difficulty: str = Field(
        default="medium",
        description="Difficulty level: easy, medium, or hard.",
    )


class QuizState(BaseModel):
    """Tracks the state of an active practice quiz across turns.

    Serialised into an HTML comment in each assistant response so
    the PracticeHandler can resume state across workflow runs.
    """

    quiz_id: str = Field(description="Unique identifier for this quiz.")
    certification: str = Field(description="Exam code (e.g. AZ-104).")
    questions: list[PracticeQuestion] = Field(
        description="All generated questions for this quiz.",
    )
    current_index: int = Field(
        default=0,
        description="0-based index of the next question to present.",
    )
    answers: list[str] = Field(
        default_factory=list,
        description="Student answers collected so far (option letters).",
    )
    status: Literal["in_progress", "completed"] = Field(
        default="in_progress",
        description="Quiz lifecycle status.",
    )
    topics: list[str] = Field(
        default_factory=list,
        description="Distinct topic names covered by this quiz.",
    )


# ---------------------------------------------------------------------------
# Cross-workflow routing models
# ---------------------------------------------------------------------------


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
