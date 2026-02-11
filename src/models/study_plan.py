# Copyright (c) Certinator AI. All rights reserved.

"""Study plan and learning resource data models."""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ResourceType(str, Enum):
    """Type of learning resource."""

    MODULE = "module"
    LEARNING_PATH = "learning_path"
    LAB = "lab"
    DOCUMENTATION = "documentation"
    VIDEO = "video"
    PRACTICE_ASSESSMENT = "practice_assessment"


class LearningResource(BaseModel):
    """
    A single learning resource tied to the exam blueprint.

    Attributes:
        title: Title of the resource.
        url: URL to the resource on Microsoft Learn or other
            platforms.
        resource_type: The type of learning resource.
        duration_minutes: Estimated duration in minutes.
        skill_area: The exam skill area this resource covers.
        prerequisites: List of prerequisite resource titles.
    """

    title: str = Field(
        ...,
        description="Title of the resource.",
    )
    url: Optional[str] = Field(
        default=None,
        description=(
            "URL to the resource on Microsoft Learn or"
            " other platforms."
        ),
    )
    resource_type: ResourceType = Field(
        default=ResourceType.MODULE,
        description="The type of learning resource.",
    )
    duration_minutes: int = Field(
        default=30,
        ge=1,
        description="Estimated duration in minutes.",
    )
    skill_area: str = Field(
        default="",
        description=(
            "The exam skill area this resource covers."
        ),
    )
    prerequisites: list[str] = Field(
        default_factory=list,
        description="List of prerequisite resource titles.",
    )


class StudyMilestone(BaseModel):
    """
    A milestone in the study plan, typically representing
    one week of study.

    Attributes:
        week_number: The week number in the study plan.
        title: Title of the milestone.
        description: Description of what to accomplish.
        resources: Learning resources assigned to this
            milestone.
        estimated_hours: Total estimated study hours for
            this milestone.
        success_criteria: How to measure completion of this
            milestone.
    """

    week_number: int = Field(
        ...,
        ge=1,
        description="The week number in the study plan.",
    )
    title: str = Field(
        ...,
        description="Title of the milestone.",
    )
    description: str = Field(
        default="",
        description="Description of what to accomplish.",
    )
    resources: list[LearningResource] = Field(
        default_factory=list,
        description=(
            "Learning resources assigned to this milestone."
        ),
    )
    estimated_hours: float = Field(
        default=0.0,
        ge=0.0,
        description=(
            "Total estimated study hours for this milestone."
        ),
    )
    success_criteria: str = Field(
        default="",
        description=(
            "How to measure completion of this milestone."
        ),
    )


class StudyPlanMilestones(BaseModel):
    """
    A complete study plan with milestones for certification
    preparation.

    Attributes:
        certification: The target certification
            (e.g. "AZ-900").
        milestones: Ordered list of study milestones.
        total_weeks: Total number of weeks in the plan.
        total_estimated_hours: Total estimated study hours.
        notes: Additional notes about the study plan.
    """

    certification: str = Field(
        ...,
        description="The target certification (e.g. 'AZ-900').",
    )
    milestones: list[StudyMilestone] = Field(
        default_factory=list,
        description="Ordered list of study milestones.",
    )
    total_weeks: int = Field(
        default=0,
        ge=0,
        description="Total number of weeks in the plan.",
    )
    total_estimated_hours: float = Field(
        default=0.0,
        ge=0.0,
        description="Total estimated study hours.",
    )
    notes: str = Field(
        default="",
        description="Additional notes about the study plan.",
    )
