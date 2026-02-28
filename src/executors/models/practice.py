"""
Certinator AI — Practice quiz data models.

Typed schemas for practice questions and quiz state
used by the PracticeQuestionsExecutor.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


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
