"""
Certinator AI — Schedule output data models.

Typed data-transfer objects for study plan scheduling:
weekly plans, skill summaries, and student constraints.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ScheduleWeekItem(BaseModel):
    """A single module scheduled within a specific week."""

    module: str = Field(description="Module title.")
    url: str = Field(description="MS Learn URL for the module.")
    duration_minutes: float = Field(
        description="Duration of the module in minutes.",
    )
    hours: float = Field(
        description="Duration of the module in hours (rounded).",
    )
    exam_skill: str = Field(
        description="Exam skill area this module covers.",
    )
    exam_weight_pct: float = Field(
        description="Exam weight percentage for this skill area.",
    )
    learning_path: str = Field(
        description="Learning path this module belongs to.",
    )


class ScheduleWeek(BaseModel):
    """A single week in the study plan schedule."""

    week: int = Field(description="Week number (1-based).")
    hours: float = Field(
        description="Total study hours for this week.",
    )
    items: list[ScheduleWeekItem] = Field(
        description="Modules scheduled for this week.",
    )


class SkillSummaryItem(BaseModel):
    """Coverage summary for a single exam skill area."""

    exam_skill: str = Field(description="Exam skill area name.")
    exam_weight_pct: float = Field(
        description="Exam weight percentage for this skill.",
    )
    total_minutes: float = Field(
        description="Total minutes across all modules for this skill.",
    )
    modules_included: int = Field(
        default=0,
        description="Number of modules included in the schedule.",
    )
    modules_skipped: int = Field(
        default=0,
        description="Number of modules skipped due to time constraints.",
    )
    selected_minutes: float = Field(
        default=0.0,
        description="Total minutes for included modules only.",
    )


class SkippedModule(BaseModel):
    """A module excluded from the schedule due to time."""

    module: str = Field(description="Module title.")
    url: str = Field(description="MS Learn URL for the module.")
    duration_minutes: float = Field(
        description="Duration of the module in minutes.",
    )
    exam_skill: str = Field(
        description="Exam skill area this module covers.",
    )
    exam_weight_pct: float = Field(
        description="Exam weight percentage for this skill area.",
    )
    learning_path: str = Field(
        description="Learning path this module belongs to.",
    )


class ScheduleResult(BaseModel):
    """Complete output from the study schedule calculator.

    Represents the full computed study plan with weekly
    breakdown, exam skill coverage summary, and notes.
    """

    total_hours_available: float = Field(
        description="Total hours the student has available.",
    )
    total_hours_planned: float = Field(
        description="Total hours of content selected.",
    )
    total_weeks_needed: int = Field(
        description="Number of weeks the schedule spans.",
    )
    coverage_pct: int = Field(
        description="Percentage of total modules included in the plan.",
    )
    skill_summary: list[SkillSummaryItem] = Field(
        description="Coverage summary grouped by exam skill area.",
    )
    weekly_plan: list[ScheduleWeek] = Field(
        description="Week-by-week schedule with module assignments.",
    )
    skipped_modules: list[SkippedModule] = Field(
        default_factory=list,
        description="Modules excluded to fit the time budget.",
    )
    notes: list[str] = Field(
        default_factory=list,
        description="Scheduler warnings and summary messages.",
    )


class StudyConstraints(BaseModel):
    """Study constraints derived from user request text."""

    hours_per_week: float = Field(
        default=6.0,
        description="Study hours available per week.",
    )
    total_weeks: int = Field(
        default=8,
        description="Total weeks until the exam.",
    )
    prioritize_by_date: bool = Field(
        default=False,
        description="Whether to cap content to fit deadline.",
    )
