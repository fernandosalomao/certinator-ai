"""
Certinator AI — Learning path data models.

Typed schemas mirroring the Microsoft Learn content hierarchy:
Certification → Skills at a Glance + Learning Paths → Modules.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from .routing import RoutingDecision


class TrainingModule(BaseModel):
    """A single Microsoft Learn training module within a learning path."""

    model_config = ConfigDict(extra="ignore")

    title: str = Field(description="Title of the module.")
    url: str = Field(description="MS Learn URL for the module.")
    duration_minutes: float = Field(
        description="Estimated completion time in minutes.",
    )
    unit_count: int = Field(
        description="Number of units in the module.",
    )
    exam_skill: str = Field(
        description=(
            "Exam skill area this module maps to "
            "(e.g. 'Design infrastructure solutions')."
        ),
    )
    exam_weight_pct: float = Field(
        description=(
            "Exam weight percentage for the mapped skill area. "
            "Use the midpoint of the published range "
            "(e.g. 17.5 for '15-20%')."
        ),
    )


class SkillAtAGlance(BaseModel):
    """An exam skill area with its weight percentage."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    skill_name: str = Field(
        alias="name",
        description="Name of the exam skill area.",
    )
    exam_weight_pct: float = Field(
        description=(
            "Exam weight percentage (midpoint of published range, "
            "e.g. 17.5 for '15-20%')."
        ),
    )


class LearningPath(BaseModel):
    """An official Microsoft Learn learning path for a certification.

    Mirrors the MS Learn hierarchy: Learning Paths → Modules.
    Each module carries its own exam_skill / exam_weight_pct mapping.
    """

    model_config = ConfigDict(extra="ignore")

    title: str = Field(description="Title of the learning path.")
    url: str = Field(description="MS Learn URL for the learning path.")
    duration_minutes: float = Field(
        description="Total estimated completion time in minutes.",
    )
    module_count: int = Field(
        description="Number of modules in the learning path.",
    )
    modules: list[TrainingModule] = Field(
        description="Modules that compose this learning path.",
    )


class LearningPathFetcherResponse(BaseModel):
    """Structured response schema for LearningPathFetcher agent output.

    Mirrors the MS Learn content hierarchy:
    Certification → Skills at a glance + Learning Paths → Modules.
    Each module is mapped to an exam skill with its weight percentage.
    """

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    exam_code: str = Field(
        alias="examCode",
        description="Exam code such as AZ-900 or AZ-104.",
    )
    skills_at_a_glance: list[SkillAtAGlance] = Field(
        default_factory=list,
        alias="skillsAtAGlance",
        description="Exam skill areas with their weight percentages.",
    )
    learning_paths: list[LearningPath] = Field(
        alias="learningPaths",
        description="Official Microsoft Learn learning paths for this certification.",
    )


class LearningPathsData(BaseModel):
    """Structured output from LearningPathFetcherExecutor.

    Flows from LearningPathFetcherExecutor → StudyPlanGeneratorExecutor
    and carries the learning-path / module hierarchy the scheduler needs
    to compute a feasible study schedule.
    """

    certification: str = Field(description="Exam code such as AZ-900 or AZ-104.")
    skills_at_a_glance: list[dict] = Field(
        default_factory=list,
        description=(
            "Exam skill areas with weight percentages. "
            "Each element has: skill_name, exam_weight_pct."
        ),
    )
    learning_paths: list[dict] = Field(
        description=(
            "Full learning paths JSON array as returned by the fetcher "
            "agent. Each element has: title, url, duration_minutes, "
            "module_count, modules (list of {title, url, duration_minutes, "
            "unit_count, exam_skill, exam_weight_pct})."
        ),
    )
    original_decision: RoutingDecision = Field(
        description="Original routing decision preserved for downstream handlers.",
    )
