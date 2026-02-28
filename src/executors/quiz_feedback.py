"""
Certinator AI — Quiz Feedback Report Builders

Extracted from *PracticeQuestionsExecutor* so that the feedback
report generation and fallback builder can be tested and reused
independently.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from agent_framework import ChatMessage, Role

from executors.models import QuizState
from executors.retry import safe_agent_run

logger = logging.getLogger(__name__)


def fallback_feedback(
    state: QuizState,
    score_result: dict,
) -> str:
    """Build a minimal report when the LLM fails.

    Parameters:
        state (QuizState): Quiz state.
        score_result (dict): Scoring data.

    Returns:
        str: Basic Markdown report.
    """
    lines = [
        f"# {state.certification} Quiz Results\n",
        f"**Score:** {score_result['overall_percentage']}% "
        f"({score_result['correct_answers']}/"
        f"{score_result['total_questions']})\n",
        "| Topic | Correct | Total | % |",
        "|---|---:|---:|---:|",
    ]
    for tb in score_result.get("topic_breakdown", []):
        lines.append(
            f"| {tb['topic']} | {tb['correct']} | {tb['total']} | {tb['percentage']}% |"
        )
    return "\n".join(lines)


async def generate_feedback_report(
    practice_agent: Any,
    state: QuizState,
    score_result: dict,
) -> str:
    """Generate a detailed feedback report via the practice agent.

    Parameters:
        practice_agent: Agent with an async ``run()`` method.
        state (QuizState): Completed quiz state.
        score_result (dict): Output from ``score_quiz``.

    Returns:
        str: Markdown feedback report.
    """
    from executors import extract_response_text

    details = []
    for i, q in enumerate(state.questions):
        user_ans = state.answers[i] if i < len(state.answers) else "?"
        details.append(
            {
                "number": q.question_number,
                "question": q.question_text,
                "correct": q.correct_answer,
                "student": user_ans,
                "is_correct": user_ans == q.correct_answer,
                "explanation": q.explanation,
                "topic": q.topic,
            }
        )

    prompt = (
        f"Generate a feedback report for a "
        f"{state.certification} practice quiz.\n\n"
        f"Overall score: "
        f"{score_result['overall_percentage']}% "
        f"({score_result['correct_answers']}/"
        f"{score_result['total_questions']})\n"
        f"Passed: "
        f"{'Yes' if score_result['passed'] else 'No'}\n\n"
        "Topic breakdown:\n"
        f"{json.dumps(score_result['topic_breakdown'], indent=2)}"
        "\n\nQuestion details:\n"
        f"{json.dumps(details, indent=2)}\n\n"
        "Generate a clear Markdown feedback report with:\n"
        "1. Overall assessment\n"
        "2. Results summary table "
        "(topic | correct | total | %)\n"
        "3. Per-question review (question, student answer, "
        "correct answer, explanation)\n"
        "4. Study recommendations for weak topics\n"
    )

    try:
        response = await safe_agent_run(
            practice_agent,
            [ChatMessage(role=Role.USER, text=prompt)],
        )
        return extract_response_text(
            response,
            fallback=fallback_feedback(state, score_result),
        )
    except Exception as exc:
        logger.error(
            "PracticeQuestions: feedback report generation failed: %s",
            exc,
            exc_info=True,
        )
        return fallback_feedback(state, score_result)
