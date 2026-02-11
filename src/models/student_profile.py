# Copyright (c) Certinator AI. All rights reserved.

"""Student profile data model for certification preparation."""

from datetime import date
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class LearningStyle(str, Enum):
    """Preferred learning style of a student."""

    VIDEOS = "videos"
    READING = "reading"
    HANDS_ON_LABS = "hands_on_labs"
    MIXED = "mixed"


class StudentProfile(BaseModel):
    """
    Represents a student's profile for certification preparation.

    Captures target certification, constraints, and preferences
    to guide personalised study plan generation.

    Attributes:
        name: The student's name (optional).
        target_certification: The certification the student aims
            to achieve (e.g. "AZ-900").
        exam_date: The target date for the certification exam.
        knowledge_level: Current knowledge level
            ("beginner", "intermediate", or "advanced").
        weekly_study_hours: Number of hours the student can
            dedicate to studying per week.
        preferred_learning_style: The student's preferred
            learning style.
        intent: What the student wants help with
            ("study_plan", "practice_questions",
            "certification_info", or "all").
        additional_notes: Any extra information provided
            by the student.
    """

    name: Optional[str] = Field(
        default=None,
        description="The student's name.",
    )
    target_certification: str = Field(
        ...,
        description=(
            "The certification the student aims to achieve"
            " (e.g. 'AZ-900', 'AZ-305')."
        ),
    )
    exam_date: Optional[date] = Field(
        default=None,
        description="The target date for the certification exam.",
    )
    knowledge_level: str = Field(
        default="beginner",
        description=(
            "Current knowledge level: 'beginner',"
            " 'intermediate', or 'advanced'."
        ),
    )
    weekly_study_hours: int = Field(
        default=10,
        ge=1,
        le=80,
        description=(
            "Number of hours the student can dedicate to"
            " studying per week."
        ),
    )
    preferred_learning_style: LearningStyle = Field(
        default=LearningStyle.MIXED,
        description="The student's preferred learning style.",
    )
    intent: str = Field(
        default="all",
        description=(
            "What the student wants help with: 'study_plan',"
            " 'practice_questions', 'certification_info',"
            " or 'all'."
        ),
    )
    additional_notes: Optional[str] = Field(
        default=None,
        description=(
            "Any extra information provided by the student."
        ),
    )
