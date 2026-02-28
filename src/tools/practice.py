"""
Certinator AI — Practice Quiz Scoring Tool

Deterministic scoring function used by the PracticeHandler to
evaluate student answers against generated questions.  All arithmetic
is done in Python so the LLM never has to calculate scores.

Also provides parser helpers extracted from *PracticeQuestionsExecutor*
so they can be reused and tested independently.
"""

from __future__ import annotations

import json
import logging
import re

from executors.models import PracticeQuestion, RoutingDecision

logger = logging.getLogger(__name__)

# Minimum score percentage to pass a practice quiz
PASS_THRESHOLD_PCT = 70


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
        if pct < PASS_THRESHOLD_PCT:
            weak_topics.append(topic)

    return {
        "total_questions": total,
        "correct_answers": correct,
        "overall_percentage": overall_pct,
        "passed": overall_pct >= PASS_THRESHOLD_PCT,
        "topic_breakdown": topic_breakdown,
        "weak_topics": weak_topics,
        "question_results": question_results,
    }


def validate_questions(
    questions: list[dict],
    expected_topics: list[str],
    expected_count: int,
) -> list[str]:
    """Deterministically validate a list of practice questions.

    Performs structural checks that an LLM cannot be trusted to
    enforce reliably.  Returns a list of human-readable violation
    strings so the caller can feed them back to the agent as
    regeneration feedback.  An empty list means the batch is valid.

    Checks performed:
        - Question count matches *expected_count*.
        - Each question exposes exactly the options A, B, C, and D.
        - All four option values within a question are distinct.
        - ``correct_answer`` is one of A, B, C, or D.
        - No two questions share the same ``question_text``.
        - Every topic in *expected_topics* is covered by at least
          one question.

    Parameters:
        questions (list[dict]): Question dicts to validate.  Each
            must have at least ``options`` (dict), ``correct_answer``
            (str), ``question_text`` (str), and ``topic`` (str).
        expected_topics (list[str]): Topic names that must each
            appear in at least one question.
        expected_count (int): Expected number of questions.

    Returns:
        list[str]: Violation messages; empty list if fully valid.
    """
    violations: list[str] = []
    valid_letters = {"A", "B", "C", "D"}

    # --- 1. Count check ---------------------------------------------------
    if len(questions) != expected_count:
        violations.append(
            f"Expected {expected_count} questions but received {len(questions)}."
        )

    seen_texts: set[str] = set()
    covered_topics: set[str] = set()

    for idx, q in enumerate(questions):
        num = q.get("question_number", idx + 1)
        options: dict = q.get("options", {})
        correct: str = str(q.get("correct_answer", "")).strip().upper()
        text: str = q.get("question_text", "").strip()
        topic: str = q.get("topic", "").strip()

        # --- 2. Options keys must be exactly A, B, C, D -------------------
        option_keys = {k.strip().upper() for k in options.keys()}
        if option_keys != valid_letters:
            missing = valid_letters - option_keys
            extra = option_keys - valid_letters
            msg = f"Q{num}: options keys are invalid."
            if missing:
                msg += f" Missing: {sorted(missing)}."
            if extra:
                msg += f" Unexpected: {sorted(extra)}."
            violations.append(msg)

        # --- 3. Option values must all be distinct ------------------------
        option_values = [str(v).strip() for v in options.values()]
        if len(set(option_values)) < len(option_values):
            violations.append(f"Q{num}: duplicate option values detected.")

        # --- 4. correct_answer must be A/B/C/D ----------------------------
        if correct not in valid_letters:
            violations.append(
                f"Q{num}: correct_answer '{correct}' is not one of A, B, C, D."
            )

        # --- 5. No duplicate question_text --------------------------------
        normalised_text = text.lower()
        if normalised_text in seen_texts:
            violations.append(f"Q{num}: duplicate question text detected.")
        else:
            seen_texts.add(normalised_text)

        # Track topic coverage.
        if topic:
            covered_topics.add(topic)

    # --- 6. Every expected topic must be covered -------------------------
    for expected_topic in expected_topics:
        # Case-insensitive partial match to handle minor name variations.
        matched = any(
            expected_topic.lower() in covered.lower()
            or covered.lower() in expected_topic.lower()
            for covered in covered_topics
        )
        if not matched:
            violations.append(f"No question covers expected topic '{expected_topic}'.")

    return violations


# ---------------------------------------------------------------------------
# Parsers extracted from PracticeQuestionsExecutor
# ---------------------------------------------------------------------------


def parse_questions(raw_text: str) -> list[PracticeQuestion]:
    """Parse JSON question array from agent output.

    Strips markdown code fences if present and validates
    each question against the PracticeQuestion schema.

    Parameters:
        raw_text (str): Raw text from the practice agent.

    Returns:
        list[PracticeQuestion]: Validated question objects.
    """
    cleaned = raw_text.strip()
    # Strip markdown code fences if present.
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = [ln for ln in lines if not ln.strip().startswith("```")]
        cleaned = "\n".join(lines)

    # Remove trailing commas before } or ] (common LLM JSON error).
    cleaned = re.sub(r",\s*([}\]])", r"\1", cleaned)

    try:
        data = json.loads(cleaned)
        if isinstance(data, list):
            return [PracticeQuestion.model_validate(item) for item in data]
    except (json.JSONDecodeError, Exception) as exc:
        logger.warning(
            "Failed to parse practice questions JSON: %s",
            exc,
        )
    return []


def parse_answer_payload(
    raw: str,
    total_questions: int,
) -> dict[str, str]:
    """Parse answer payload from the frontend.

    Accepts either:
      - JSON: ``{"answers":{"1":"B","2":"A",...}}``
      - Single letter: ``"B"`` (legacy, first question only)

    Parameters:
        raw (str): Raw answer string from HITL.
        total_questions (int): Expected question count.

    Returns:
        dict[str, str]: Map of question number -> answer letter.
    """
    raw = raw.strip()

    # Try JSON first.
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            answers = parsed.get("answers", parsed)
            if isinstance(answers, dict):
                return {str(k): str(v).strip().upper() for k, v in answers.items()}
    except (json.JSONDecodeError, ValueError):
        pass

    # Fallback: single letter (legacy / plain-text CLI).
    normalised = raw.strip().upper()
    if normalised in ("A", "B", "C", "D"):
        return {"1": normalised}

    # Try to extract a letter from free text.
    match = re.search(r"\b([A-D])\b", raw.upper())
    if match:
        return {"1": match.group(1)}

    return {}


def extract_question_count(
    decision: RoutingDecision,
    default: int = 10,
) -> int:
    """Extract requested question count from user intent.

    Parameters:
        decision (RoutingDecision): Routing decision.
        default (int): Default count when none found.

    Returns:
        int: Clamped question count (1-50).
    """
    text = f"{decision.task} {decision.context}".lower()
    match = re.search(r"(\d+)\s*questions?", text)
    if match:
        return max(1, min(int(match.group(1)), 50))
    return default
