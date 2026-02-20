"""
Certinator AI — Practice Quiz Scoring Tool

Deterministic scoring function used by the PracticeHandler to
evaluate student answers against generated questions.  All arithmetic
is done in Python so the LLM never has to calculate scores.
"""

from __future__ import annotations


def score_quiz(
    questions: list[dict],
    answers: list[str],
) -> dict:
    """
    Score student answers against practice questions.

    Computes an overall percentage, per-topic breakdown, and a list
    of weak topics (below 70 %).

    Parameters:
        questions (list[dict]): Question objects, each with at least
            ``correct_answer`` (str) and ``topic`` (str).
        answers (list[str]): Student answers in the same order as
            *questions* (option letters like "A", "B", …).

    Returns:
        dict: Scoring result with keys ``total_questions``,
            ``correct_answers``, ``overall_percentage``, ``passed``,
            ``topic_breakdown``, ``weak_topics``, ``question_results``.
    """
    total = len(questions)
    correct = 0
    topic_scores: dict[str, dict[str, int]] = {}
    question_results: list[dict] = []

    for i, question in enumerate(questions):
        user_answer = answers[i].strip().upper() if i < len(answers) else ""
        correct_answer = question.get("correct_answer", "").strip().upper()
        topic = question.get("topic", "Unknown")

        if topic not in topic_scores:
            topic_scores[topic] = {"correct": 0, "total": 0}
        topic_scores[topic]["total"] += 1

        is_correct = user_answer == correct_answer
        if is_correct:
            correct += 1
            topic_scores[topic]["correct"] += 1

        question_results.append(
            {
                "question_number": question.get("question_number", i + 1),
                "is_correct": is_correct,
                "user_answer": user_answer,
                "correct_answer": correct_answer,
                "topic": topic,
            }
        )

    overall_pct = round((correct / total) * 100) if total > 0 else 0

    topic_breakdown: list[dict] = []
    weak_topics: list[str] = []

    for topic, scores in topic_scores.items():
        pct = (
            round((scores["correct"] / scores["total"]) * 100)
            if scores["total"] > 0
            else 0
        )
        topic_breakdown.append(
            {
                "topic": topic,
                "correct": scores["correct"],
                "total": scores["total"],
                "percentage": pct,
            }
        )
        if pct < 70:
            weak_topics.append(topic)

    return {
        "total_questions": total,
        "correct_answers": correct,
        "overall_percentage": overall_pct,
        "passed": overall_pct >= 70,
        "topic_breakdown": topic_breakdown,
        "weak_topics": weak_topics,
        "question_results": question_results,
    }
