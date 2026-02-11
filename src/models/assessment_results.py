# Copyright (c) Certinator AI. All rights reserved.

"""Assessment results data model."""

from typing import Optional

from pydantic import BaseModel, Field


class QuestionResult(BaseModel):
    """
    Result for a single practice question.

    Attributes:
        question_number: The question number.
        skill_area: The exam skill area tested.
        question_text: The text of the question.
        choices: List of answer choices.
        correct_answer: The correct answer.
        student_answer: The student's answer.
        is_correct: Whether the student's answer was correct.
        explanation: Explanation of the correct answer.
    """

    question_number: int = Field(
        ...,
        ge=1,
        description="The question number.",
    )
    skill_area: str = Field(
        ...,
        description="The exam skill area tested.",
    )
    question_text: str = Field(
        ...,
        description="The text of the question.",
    )
    choices: list[str] = Field(
        default_factory=list,
        description="List of answer choices.",
    )
    correct_answer: str = Field(
        ...,
        description="The correct answer.",
    )
    student_answer: Optional[str] = Field(
        default=None,
        description="The student's answer.",
    )
    is_correct: bool = Field(
        default=False,
        description=(
            "Whether the student's answer was correct."
        ),
    )
    explanation: str = Field(
        default="",
        description="Explanation of the correct answer.",
    )


class AssessmentResults(BaseModel):
    """
    Results of a practice assessment aligned to the exam
    blueprint.

    Attributes:
        certification: The target certification exam.
        total_questions: Total number of questions.
        correct_answers: Number of correct answers.
        score_percentage: Overall score as a percentage.
        passed: Whether the student achieved a passing
            score (>= 70%).
        per_topic_scores: Dictionary mapping skill areas
            to their scores.
        questions: Detailed results for each question.
        recommendations: Recommendations for improvement.
    """

    certification: str = Field(
        ...,
        description="The target certification exam.",
    )
    total_questions: int = Field(
        default=0,
        ge=0,
        description="Total number of questions.",
    )
    correct_answers: int = Field(
        default=0,
        ge=0,
        description="Number of correct answers.",
    )
    score_percentage: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0,
        description="Overall score as a percentage.",
    )
    passed: bool = Field(
        default=False,
        description=(
            "Whether the student achieved a passing score"
            " (>= 70%)."
        ),
    )
    per_topic_scores: dict[str, float] = Field(
        default_factory=dict,
        description=(
            "Dictionary mapping skill areas to their scores."
        ),
    )
    questions: list[QuestionResult] = Field(
        default_factory=list,
        description="Detailed results for each question.",
    )
    recommendations: list[str] = Field(
        default_factory=list,
        description="Recommendations for improvement.",
    )
