"""
Certinator AI — Practice Questions Executor

HITL-driven executor that sends all practice questions to the UI
in a single ``request_info`` call, collects the full set of answers
back in one payload, scores the quiz, emits a feedback report, and
optionally routes to the study plan pipeline for weak topics.

Uses ``ctx.request_info()`` / ``@response_handler`` for human-in-the-
loop interaction following the MAF HITL pattern.  The quiz itself uses
only **two** HITL round-trips:

1. ``quiz_session``   — all questions sent to the frontend at once.
2. ``study_plan_offer`` — post-quiz offer (only when the student fails).

Graph position::

    CoordinatorExecutor ──► PracticeQuestionsExecutor (HITL)
                              ├── PASS  → congratulations (terminal)
                              └── FAIL  → HITL study plan offer
                                    ├── YES → StudyPlanFromQuizRequest
                                    │         → LearningPathFetcher pipeline
                                    └── NO  → end
"""

import json
import logging
import re
from typing import Any
from uuid import uuid4

from agent_framework import (
    ChatAgent,
    ChatMessage,
    Executor,
    Role,
    WorkflowContext,
    handler,
    response_handler,
)

import metrics
from config import DEFAULT_PRACTICE_QUESTIONS
from executors import (
    emit_response,
    emit_state_snapshot,
    extract_response_text,
    safe_agent_run,
    update_workflow_progress,
)
from executors.models import (
    LearningPathFetcherResponse,
    PracticeQuestion,
    QuizState,
    RoutingDecision,
    StudyPlanFromQuizRequest,
)
from executors.post_study_plan_executor import (
    CROSS_ROUTE_CYCLE_KEY,
    MAX_CROSS_ROUTE_CYCLES,
)
from tools.practice import score_quiz, validate_questions

logger = logging.getLogger(__name__)

# Maximum regeneration attempts when structural validation fails.
MAX_VALIDATION_RETRIES = 2

# Shared-state key for persisting quiz state across HITL turns.
QUIZ_STATE_KEY = "active_quiz_state"


class PracticeQuestionsExecutor(Executor):
    """Orchestrate an interactive practice quiz with HITL flow.

    Responsibilities:
        1. Fetch exam topics via the learning path agent.
        2. Generate all questions upfront via the practice agent.
        3. Send all questions to the frontend in one HITL call.
        4. Receive the full answer set back in a single response.
        5. Score the quiz deterministically with ``score_quiz``.
        6. Generate a feedback report via the practice agent.
        7. Offer a study plan for weak topics on failure (HITL).
    """

    practice_agent: ChatAgent
    learning_path_agent: ChatAgent

    def __init__(
        self,
        practice_agent: ChatAgent,
        learning_path_agent: ChatAgent,
        id: str = "practice-questions-executor",
    ):
        """Initialise the practice questions executor.

        Parameters:
            practice_agent (ChatAgent): Agent for question generation
                and feedback reports.
            learning_path_agent (ChatAgent): Agent for topic fetching.
            id (str): Executor identifier.
        """
        self.practice_agent = practice_agent
        self.learning_path_agent = learning_path_agent
        super().__init__(id=id)

    # ------------------------------------------------------------------
    # Entry: generate questions and send the full quiz session
    # ------------------------------------------------------------------

    @handler
    async def handle(
        self,
        decision: RoutingDecision,
        ctx: WorkflowContext[StudyPlanFromQuizRequest],
    ) -> None:
        """Start the quiz: fetch topics, generate questions, present.

        All questions are sent to the frontend in a single
        ``request_info`` call with type ``quiz_session``.  The
        frontend renders them one-by-one and submits all answers
        back in one payload.

        Parameters:
            decision (RoutingDecision): Coordinator routing decision.
            ctx (WorkflowContext): Workflow context.
        """
        cert = decision.certification or "the requested certification"
        topics = await self._fetch_exam_topics(cert)
        question_count = self._extract_question_count(decision)

        # Generate and structurally validate all questions upfront.
        try:
            questions = await self._validate_and_regenerate(
                cert,
                topics,
                question_count,
                decision.context,
            )
        except Exception as exc:
            logger.error(
                "PracticeQuestions: question generation failed for %s: %s",
                cert,
                exc,
                exc_info=True,
            )
            await emit_response(
                ctx,
                self.id,
                "I encountered an issue generating practice questions. "
                "Please try again.",
            )
            return

        if not questions:
            await emit_response(
                ctx,
                self.id,
                "I could not generate practice questions at this "
                "time. Please try again.",
            )
            return

        # Build and persist quiz state.
        quiz_state = QuizState(
            quiz_id=str(uuid4()),
            certification=cert,
            questions=questions,
            current_index=0,
            answers=[],
            status="in_progress",
            topics=list({q.topic for q in questions}),
        )
        await ctx.shared_state.set(
            QUIZ_STATE_KEY,
            quiz_state.model_dump(),
        )
        await emit_state_snapshot(
            ctx=ctx,
            executor_id=self.id,
            tool_name="update_active_quiz_state",
            tool_argument="quiz_state",
            state_value=quiz_state.model_dump(),
        )

        # Emit intro message.
        intro = (
            f"**{cert} Practice Quiz** — "
            f"{len(questions)} questions\n\n"
            "Answer each question by selecting "
            "**A**, **B**, **C**, or **D**.\n"
            "You'll receive your score and detailed feedback "
            "at the end.\n\n---"
        )
        await emit_response(ctx, self.id, intro)

        # Send ALL questions in a single HITL call.
        serialised_questions = [
            {
                "question_number": q.question_number,
                "question_text": q.question_text,
                "options": q.options,
                "topic": q.topic,
                "difficulty": q.difficulty,
            }
            for q in questions
        ]

        await ctx.request_info(
            request_data={
                "type": "quiz_session",
                "certification": cert,
                "questions": serialised_questions,
                "total_questions": len(questions),
            },
            response_type=str,
        )

    # ------------------------------------------------------------------
    # HITL: unified response handler
    # ------------------------------------------------------------------

    @response_handler
    async def on_hitl_response(
        self,
        original_request: dict,
        answer: str,
        ctx: WorkflowContext[StudyPlanFromQuizRequest],
    ) -> None:
        """Route HITL responses based on quiz state.

        Two possible payloads:
          - Quiz answers: JSON ``{"answers":{"1":"B","2":"A",...}}``
          - Study plan offer: plain ``"yes"`` / ``"no"``

        Parameters:
            original_request (dict): Serialised HITL payload.
            answer (str): Student's response (JSON or plain text).
            ctx (WorkflowContext): Workflow context.
        """
        state_data = await ctx.shared_state.get(QUIZ_STATE_KEY)
        if not state_data:
            await emit_response(
                ctx,
                self.id,
                "Quiz session not found. Please start a new quiz.",
            )
            return

        state = QuizState.model_validate(state_data)

        # If quiz is still in progress, this is the bulk answer set.
        if state.status == "in_progress":
            await self._process_quiz_answers(state, answer, ctx)
        else:
            # Quiz is completed — this is a study plan offer.
            await self._process_study_plan_offer(
                state,
                answer,
                ctx,
            )

    # ------------------------------------------------------------------
    # Bulk quiz answer processing
    # ------------------------------------------------------------------

    async def _process_quiz_answers(
        self,
        state: QuizState,
        answer: str,
        ctx: WorkflowContext,
    ) -> None:
        """Process the full set of quiz answers in one go.

        Expects a JSON string like ``{"answers":{"1":"B","2":"A"}}``
        from the frontend.  Falls back to single-letter parsing for
        backwards compatibility with plain-text responses.

        Parameters:
            state (QuizState): Current quiz state.
            answer (str): JSON payload or single letter.
            ctx (WorkflowContext): Workflow context.
        """
        answers_map = self._parse_answer_payload(
            answer,
            len(state.questions),
        )

        # Build ordered answer list aligned to question indices.
        ordered: list[str] = []
        for i, q in enumerate(state.questions):
            q_num = str(q.question_number)
            letter = answers_map.get(q_num, "X")
            ordered.append(letter)

        state.answers = ordered
        state.current_index = len(state.questions)
        state.status = "completed"

        await ctx.shared_state.set(
            QUIZ_STATE_KEY,
            state.model_dump(),
        )
        await emit_state_snapshot(
            ctx=ctx,
            executor_id=self.id,
            tool_name="update_active_quiz_state",
            tool_argument="quiz_state",
            state_value=state.model_dump(),
        )
        await self._score_and_report(state, ctx)

    @staticmethod
    def _parse_answer_payload(
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
            dict[str, str]: Map of question number → answer letter.
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

    # ------------------------------------------------------------------
    # Study plan offer processing
    # ------------------------------------------------------------------

    async def _process_study_plan_offer(
        self,
        state: QuizState,
        answer: str,
        ctx: WorkflowContext,
    ) -> None:
        """Handle the student's response to the study plan offer.

        Parameters:
            state (QuizState): Completed quiz state.
            answer (str): Student's response (yes/no).
            ctx (WorkflowContext): Workflow context.
        """
        reply = answer.strip().lower()
        affirmative = (
            reply
            in (
                "yes",
                "y",
                "sure",
                "ok",
                "okay",
                "please",
                "yeah",
            )
            or "yes" in reply
        )

        metrics.hitl_study_plan_offers.add(
            1,
            {"accepted": str(affirmative).lower()},
        )

        if affirmative:
            # Compute weak topics from the quiz results.
            q_dicts = [q.model_dump() for q in state.questions]
            result = score_quiz(q_dicts, state.answers)
            weak = result.get("weak_topics", [])
            if not weak:
                weak = state.topics

            await emit_response(
                ctx,
                self.id,
                "Great! I'll create a focused study plan for "
                f"your weak areas: **{', '.join(weak)}**.\n\n"
                "Please wait while I prepare it...",
            )

            # Route to the study plan pipeline.
            await ctx.send_message(
                StudyPlanFromQuizRequest(
                    certification=state.certification,
                    weak_topics=weak,
                    quiz_score=result.get(
                        "overall_percentage",
                        0,
                    ),
                    original_decision=RoutingDecision(
                        route="study-plan-generator",
                        task=(
                            "Create a focused study plan for "
                            f"{state.certification} targeting "
                            "weak areas"
                        ),
                        certification=state.certification,
                        context=(
                            "Focus on weak topics from practice"
                            f" quiz (score: "
                            f"{result.get('overall_percentage', 0)}"
                            f"%): {', '.join(weak)}"
                        ),
                    ),
                )
            )
        else:
            await emit_response(
                ctx,
                self.id,
                "No problem! When you're ready to study or "
                "practice again, just let me know. Good luck "
                "with your certification preparation!",
            )

    # ------------------------------------------------------------------
    # Internal: validated question generation
    # ------------------------------------------------------------------

    async def _validate_and_regenerate(
        self,
        cert: str,
        topics: list[dict],
        count: int,
        focus_context: str = "",
    ) -> list[PracticeQuestion]:
        """Generate questions and retry until they pass structural validation.

        Calls ``_generate_questions()`` then ``validate_questions()``.
        On violations the feedback is appended to the prompt and
        generation is retried up to ``MAX_VALIDATION_RETRIES`` times.
        If the batch still has violations after all retries, the best
        available result is returned with a warning so students are
        never hard-blocked.

        Parameters:
            cert (str): Certification code.
            topics (list[dict]): Topics with weights.
            count (int): Number of questions to generate.
            focus_context (str): Optional focus area.

        Returns:
            list[PracticeQuestion]: Validated (or best-effort) questions.
        """
        expected_topic_names = [t.get("name", "") for t in topics]
        prior_violations: list[str] = []
        questions: list[PracticeQuestion] = []

        for attempt in range(1, MAX_VALIDATION_RETRIES + 2):
            questions = await self._generate_questions(
                cert,
                topics,
                count,
                focus_context,
                prior_violations=prior_violations if prior_violations else None,
            )

            q_dicts = [q.model_dump() for q in questions]
            violations = validate_questions(
                q_dicts,
                expected_topic_names,
                count,
            )

            if not violations:
                if attempt > 1:
                    logger.info(
                        "PracticeQuestions: validation passed on attempt %d for %s.",
                        attempt,
                        cert,
                    )
                return questions

            logger.warning(
                "PracticeQuestions: validation attempt %d/%d failed for %s: %s",
                attempt,
                MAX_VALIDATION_RETRIES + 1,
                cert,
                violations,
            )

            if attempt <= MAX_VALIDATION_RETRIES:
                prior_violations = violations
            else:
                # Cap reached — proceed with best-available questions.
                logger.warning(
                    "PracticeQuestions: delivering questions with %d "
                    "unresolved violation(s) after %d attempts for %s.",
                    len(violations),
                    MAX_VALIDATION_RETRIES + 1,
                    cert,
                )

        return questions

    # ------------------------------------------------------------------
    # Internal: question generation
    # ------------------------------------------------------------------

    async def _generate_questions(
        self,
        cert: str,
        topics: list[dict],
        count: int,
        focus_context: str = "",
        prior_violations: list[str] | None = None,
    ) -> list[PracticeQuestion]:
        """Generate practice questions via the practice agent.

        Parameters:
            cert (str): Certification code.
            topics (list[dict]): Topics with weights.
            count (int): Number of questions to generate.
            focus_context (str): Optional focus area.
            prior_violations (list[str] | None): Structural violations
                from a previous attempt, appended to the prompt so the
                agent can self-correct.

        Returns:
            list[PracticeQuestion]: Parsed questions or empty.
        """
        topic_list = "\n".join(
            f"- {t.get('name', 'Unknown')} ({t.get('weight_pct', 0)}%)" for t in topics
        )
        prompt = (
            f"Generate exactly {count} multiple-choice "
            f"questions for {cert}.\n\n"
            f"Topics and weights:\n{topic_list}\n\n"
            "Rules:\n"
            "- At least one question per topic\n"
            "- Remaining questions proportional to weight\n"
            "- 4 options (A,B,C,D), exactly one correct\n"
            "- Include correct answer and explanation\n"
            "- Return ONLY a valid JSON array\n"
        )
        if focus_context:
            prompt += f"- Focus area: {focus_context}\n"
        if prior_violations:
            violation_list = "\n".join(f"  - {v}" for v in prior_violations)
            prompt += (
                f"\nFix these issues from the previous attempt:\n{violation_list}\n"
            )

        response = await safe_agent_run(
            self.practice_agent,
            [ChatMessage(role=Role.USER, text=prompt)],
        )
        raw_text = extract_response_text(response, fallback="[]")
        return self._parse_questions(raw_text)

    @staticmethod
    def _parse_questions(
        raw_text: str,
    ) -> list[PracticeQuestion]:
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

    # ------------------------------------------------------------------
    # Internal: scoring and feedback
    # ------------------------------------------------------------------

    async def _score_and_report(
        self,
        state: QuizState,
        ctx: WorkflowContext,
    ) -> None:
        """Score the completed quiz and emit feedback.

        On pass (>=70%): congratulates and links to exam scheduling.
        On fail (<70%): offers a focused study plan via HITL.

        Parameters:
            state (QuizState): Completed quiz state.
            ctx (WorkflowContext): Workflow context.
        """
        # Deterministic scoring — no LLM needed for arithmetic.
        q_dicts = [q.model_dump() for q in state.questions]
        result = score_quiz(q_dicts, state.answers)

        overall_pct = result["overall_percentage"]
        passed = result["passed"]
        weak_topics = result.get("weak_topics", [])

        # Emit quiz score metrics.
        cert_label = state.certification or "unknown"
        metrics.quiz_scores.record(overall_pct, {"certification": cert_label})
        for tb in result.get("topic_breakdown", []):
            metrics.quiz_topic_scores.record(
                tb["percentage"],
                {"topic": tb.get("topic", "unknown"), "certification": cert_label},
            )

        # Generate feedback report via practice agent (Mode 2).
        feedback = await self._generate_feedback_report(
            state,
            result,
        )
        await emit_response(ctx, self.id, feedback)

        # Mark workflow progress as completed so all spinner icons
        # transition to the done (checkmark) state.
        await update_workflow_progress(
            ctx=ctx,
            route="practice",
            active_executor=self.id,
            message="Quiz scored — feedback ready.",
            current_step=1,
            total_steps=1,
            status="completed",
        )

        if passed:
            # Congratulations with exam scheduling link.
            cert_slug = state.certification.lower().replace(" ", "-")
            url = f"https://learn.microsoft.com/en-us/certifications/exams/{cert_slug}"
            congrats = (
                f"\n\nCongratulations! You scored "
                f"**{overall_pct}%** — that's a passing score!"
                f"\n\nYou're ready to schedule your "
                f"{state.certification} exam. Book it here: "
                f"[{state.certification} Exam Registration]"
                f"({url})\n\nGood luck!"
            )
            await emit_response(ctx, self.id, congrats)
        else:
            # ── Cross-route cycle breaker ─────────────────────
            try:
                cycle_count = await ctx.shared_state.get(
                    CROSS_ROUTE_CYCLE_KEY,
                )
            except KeyError:
                cycle_count = 0

            if cycle_count >= MAX_CROSS_ROUTE_CYCLES:
                # Cap reached — do NOT offer another study plan.
                logger.info(
                    "Cycle breaker: cap reached (%d >= %d) for "
                    "%s — skipping study plan offer.",
                    cycle_count,
                    MAX_CROSS_ROUTE_CYCLES,
                    cert_label,
                )
                metrics.cycle_breaker_cap_reached.add(
                    1,
                    {
                        "source_executor": self.id,
                        "certification": cert_label,
                    },
                )
                weak_str = ", ".join(weak_topics) if weak_topics else "all topics"
                await emit_response(
                    ctx,
                    self.id,
                    f"You scored **{overall_pct}%** — not "
                    "quite passing yet, but you've already "
                    "done multiple study-and-practice rounds "
                    "— great dedication!\n\n"
                    f"Focus on: **{weak_str}**\n\n"
                    "Here are some tips:\n"
                    "1. **Hands-on labs** in the Azure portal "
                    "or sandbox environments.\n"
                    "2. **Microsoft Learn modules** for your "
                    "weak areas.\n"
                    "3. **Schedule your exam** when you feel "
                    "ready — you're making progress!\n\n"
                    "Start a new conversation anytime for a "
                    "fresh practice session.",
                )
                return

            # Offer a focused study plan for weak topics.
            weak_str = ", ".join(weak_topics) if weak_topics else "all topics"
            offer = (
                f"You scored **{overall_pct}%** — not quite a "
                "passing score (70% required).\n\n"
                f"Your weak areas are: **{weak_str}**.\n\n"
                "Would you like me to create a **focused study "
                "plan** to help you improve on these topics?"
            )
            await ctx.request_info(
                request_data={
                    "type": "study_plan_offer",
                    "prompt": offer,
                    "certification": state.certification,
                },
                response_type=str,
            )

    async def _generate_feedback_report(
        self,
        state: QuizState,
        score_result: dict,
    ) -> str:
        """Generate a detailed feedback report via the practice agent.

        Parameters:
            state (QuizState): Completed quiz state.
            score_result (dict): Output from ``score_quiz``.

        Returns:
            str: Markdown feedback report.
        """
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
                self.practice_agent,
                [ChatMessage(role=Role.USER, text=prompt)],
            )
            return extract_response_text(
                response,
                fallback=self._fallback_feedback(state, score_result),
            )
        except Exception as exc:
            logger.error(
                "PracticeQuestions: feedback report generation failed: %s",
                exc,
                exc_info=True,
            )
            return self._fallback_feedback(state, score_result)

    @staticmethod
    def _fallback_feedback(
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
                f"| {tb['topic']} | {tb['correct']} | "
                f"{tb['total']} | {tb['percentage']}% |"
            )
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Internal: topic fetching and helpers
    # ------------------------------------------------------------------

    async def _fetch_exam_topics(
        self,
        cert: str,
    ) -> list[dict]:
        """Fetch exam topics and weights from Microsoft Learn.

        Parameters:
            cert (str): Certification code.

        Returns:
            list[dict]: Topic list with name and weight.
        """
        prompt = (
            f"Certification: {cert}\n\n"
            "Fetch exam topic names and percentage weights. "
            "You MUST use the microsoft_docs_search tool to retrieve "
            "real data \u2014 do NOT answer from memory.\n\n"
            "After gathering data via tool calls, return a single "
            "JSON object matching the LearningPathFetcherResponse schema."
        )
        try:
            # Do NOT pass response_format — it prevents tool calls.
            response = await safe_agent_run(
                self.learning_path_agent,
                [ChatMessage(role=Role.USER, text=prompt)],
            )
        except Exception as exc:
            logger.error(
                "PracticeQuestions: topic fetch failed for %s: %s",
                cert,
                exc,
                exc_info=True,
            )
            return [{"name": f"{cert} General", "weight_pct": 100}]
        topics = self._extract_topic_distribution(response)
        if topics:
            return topics

        logger.warning(
            "Practice: failed to parse topics for %s",
            cert,
        )
        return [
            {"name": f"{cert} General", "weight_pct": 100},
        ]

    @staticmethod
    def _extract_topic_distribution(
        response: Any,
    ) -> list[dict]:
        """Extract topic names and exam weights from structured response.

        Uses learning path names as topic areas. Prefers the
        ``exam_weight_pct`` field when available (set by the agent
        from official exam topic weights); falls back to deriving
        proportional weights from durations.

        Parameters:
            response (Any): Agent response.

        Returns:
            list[dict]: Topic dictionaries with ``name``
                and ``weight_pct``.
        """
        structured = getattr(response, "value", None)

        # Import the robust parser that handles string/dict/validated responses
        from executors.learning_path_fetcher_executor import (
            LearningPathFetcherExecutor,
        )

        parsed = LearningPathFetcherExecutor._parse_response_value(response)
        if parsed is not None:
            structured = parsed

        if isinstance(structured, dict):
            try:
                structured = LearningPathFetcherResponse.model_validate(
                    structured,
                )
            except Exception:
                return []

        if not isinstance(structured, LearningPathFetcherResponse):
            return []

        paths = structured.learning_paths
        if not paths:
            return []

        # Check if exam weights are available (any path has exam_weight_pct > 0)
        has_exam_weights = any(lp.exam_weight_pct > 0 for lp in paths)

        if has_exam_weights:
            # Group by exam_topic to avoid duplicates when multiple
            # learning paths share the same exam topic.
            topic_weights: dict[str, float] = {}
            for lp in paths:
                topic = lp.exam_topic or lp.name
                if topic not in topic_weights:
                    topic_weights[topic] = lp.exam_weight_pct
            # Normalise so weights sum to 100
            total_weight = sum(topic_weights.values()) or 1
            return [
                {
                    "name": topic,
                    "weight_pct": max(round(weight / total_weight * 100), 1),
                }
                for topic, weight in topic_weights.items()
            ]

        # Fallback: derive weights from durations
        total_minutes = sum(lp.duration_minutes for lp in paths) or 1
        result: list[dict] = []
        cumulative = 0
        for i, lp in enumerate(paths):
            if i == len(paths) - 1:
                pct = 100 - cumulative
            else:
                pct = round(lp.duration_minutes / total_minutes * 100)
                cumulative += pct
            result.append({"name": lp.name, "weight_pct": max(pct, 1)})
        return result

    @staticmethod
    def _extract_question_count(
        decision: RoutingDecision,
    ) -> int:
        """Extract requested question count from user intent.

        Parameters:
            decision (RoutingDecision): Routing decision.

        Returns:
            int: Clamped question count (1–50).
        """
        text = f"{decision.task} {decision.context}".lower()
        match = re.search(r"(\d+)\s*questions?", text)
        if match:
            return max(1, min(int(match.group(1)), 50))
        return DEFAULT_PRACTICE_QUESTIONS
