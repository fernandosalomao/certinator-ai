"""
Certinator AI — Cross-Route Cycle Breaker Tests

Unit tests for G4: the shared-state cycle counter that prevents
infinite Practice ↔ StudyPlan loops.

Covers:
    - PostStudyPlanExecutor: practice offer suppressed at cap
    - PostStudyPlanExecutor: counter increment on acceptance
    - PracticeQuestionsExecutor: study plan offer suppressed at cap
    - Counter values below cap still allow normal flow
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure ``src/`` is on the import path.
_SRC = str(Path(__file__).resolve().parent.parent / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from executors.models import (
    ApprovedStudyPlanOutput,
    PracticeQuestion,
    QuizState,
    RoutingDecision,
)
from executors.post_study_plan_executor import (
    CROSS_ROUTE_CYCLE_KEY,
    MAX_CROSS_ROUTE_CYCLES,
    POST_STUDY_PLAN_CTX_KEY,
    PostStudyPlanExecutor,
)

# ── Helpers ───────────────────────────────────────────────────────────


class FakeSharedState:
    """Minimal dict-backed shared state for testing.

    Mirrors the Agent Framework behaviour: ``get()`` raises
    ``KeyError`` when the key is not found.
    """

    def __init__(self, initial: dict[str, Any] | None = None):
        self._data: dict[str, Any] = initial or {}

    async def get(self, key: str, default: Any = None) -> Any:
        """Return a stored value or raise KeyError."""
        if key not in self._data:
            raise KeyError(
                f"Key '{key}' not found in shared state.",
            )
        return self._data[key]

    async def set(self, key: str, value: Any) -> None:
        """Store a value."""
        self._data[key] = value


def _make_ctx(
    shared: dict[str, Any] | None = None,
) -> MagicMock:
    """Build a mock WorkflowContext with a FakeSharedState."""
    ctx = MagicMock()
    ctx.shared_state = FakeSharedState(shared)
    ctx.request_info = AsyncMock()
    ctx.send_message = AsyncMock()
    return ctx


def _make_approved(
    certification: str = "AZ-900",
    content: str = "Study plan content.",
) -> ApprovedStudyPlanOutput:
    """Build a minimal ApprovedStudyPlanOutput."""
    return ApprovedStudyPlanOutput(
        content=content,
        certification=certification,
        original_decision=RoutingDecision(
            route="study-plan-generator",
            task="Create a study plan",
            certification=certification,
            context="Focus on weak topics.",
        ),
    )


def _make_quiz_state(
    certification: str = "AZ-900",
    score_pct: int = 50,
) -> QuizState:
    """Build a completed QuizState with two questions.

    The student gets the first question right and the second wrong
    so ``score_quiz`` produces a predictable 50% result.
    """
    return QuizState(
        quiz_id="test-quiz-1",
        certification=certification,
        questions=[
            PracticeQuestion(
                question_number=1,
                question_text="Q1",
                options={"A": "a", "B": "b", "C": "c", "D": "d"},
                correct_answer="A",
                explanation="A is correct.",
                topic="Topic 1",
            ),
            PracticeQuestion(
                question_number=2,
                question_text="Q2",
                options={"A": "a", "B": "b", "C": "c", "D": "d"},
                correct_answer="B",
                explanation="B is correct.",
                topic="Topic 2",
            ),
        ],
        current_index=2,
        answers=["A", "C"],  # 1 correct, 1 wrong → 50%
        status="completed",
        topics=["Topic 1", "Topic 2"],
    )


# ── PostStudyPlanExecutor Tests ──────────────────────────────────────


class TestPostStudyPlanCycleBreaker:
    """PostStudyPlanExecutor cycle breaker behaviour."""

    def test_practice_offered_when_below_cap(self) -> None:
        """Counter < MAX → practice offer is shown (request_info called)."""
        executor = PostStudyPlanExecutor()
        ctx = _make_ctx({CROSS_ROUTE_CYCLE_KEY: 0})
        approved = _make_approved()

        with (
            patch(
                "executors.post_study_plan_executor.emit_response",
                new_callable=AsyncMock,
            ),
            patch(
                "executors.post_study_plan_executor.emit_response_streamed",
                new_callable=AsyncMock,
            ),
            patch(
                "executors.post_study_plan_executor.update_workflow_progress",
                new_callable=AsyncMock,
            ),
        ):
            asyncio.run(executor.handle(approved, ctx))

        # HITL request_info should have been called (practice offer).
        ctx.request_info.assert_awaited_once()
        req = ctx.request_info.call_args
        assert req[1]["request_data"]["type"] == "practice_offer"

    def test_practice_offered_when_counter_is_one(self) -> None:
        """Counter = 1 (below cap of 2) → practice offer shown."""
        executor = PostStudyPlanExecutor()
        ctx = _make_ctx({CROSS_ROUTE_CYCLE_KEY: 1})
        approved = _make_approved()

        with (
            patch(
                "executors.post_study_plan_executor.emit_response",
                new_callable=AsyncMock,
            ),
            patch(
                "executors.post_study_plan_executor.emit_response_streamed",
                new_callable=AsyncMock,
            ),
            patch(
                "executors.post_study_plan_executor.update_workflow_progress",
                new_callable=AsyncMock,
            ),
        ):
            asyncio.run(executor.handle(approved, ctx))

        ctx.request_info.assert_awaited_once()

    def test_practice_suppressed_at_cap(self) -> None:
        """Counter = MAX → practice offer suppressed, tips emitted."""
        executor = PostStudyPlanExecutor()
        ctx = _make_ctx(
            {CROSS_ROUTE_CYCLE_KEY: MAX_CROSS_ROUTE_CYCLES},
        )
        approved = _make_approved()

        with (
            patch(
                "executors.post_study_plan_executor.emit_response",
                new_callable=AsyncMock,
            ) as mock_emit,
            patch(
                "executors.post_study_plan_executor.emit_response_streamed",
                new_callable=AsyncMock,
            ),
            patch(
                "executors.post_study_plan_executor.update_workflow_progress",
                new_callable=AsyncMock,
            ),
        ):
            asyncio.run(executor.handle(approved, ctx))

        # HITL request_info should NOT have been called.
        ctx.request_info.assert_not_awaited()

        # Tips message emitted via emit_response (study plan content
        # goes through emit_response_streamed separately).
        calls = mock_emit.await_args_list
        assert len(calls) >= 1
        tips_text = calls[-1].args[2]
        assert "multiple study-and-practice rounds" in tips_text

    def test_practice_suppressed_above_cap(self) -> None:
        """Counter > MAX → also suppressed."""
        executor = PostStudyPlanExecutor()
        ctx = _make_ctx(
            {CROSS_ROUTE_CYCLE_KEY: MAX_CROSS_ROUTE_CYCLES + 5},
        )
        approved = _make_approved()

        with (
            patch(
                "executors.post_study_plan_executor.emit_response",
                new_callable=AsyncMock,
            ),
            patch(
                "executors.post_study_plan_executor.emit_response_streamed",
                new_callable=AsyncMock,
            ),
            patch(
                "executors.post_study_plan_executor.update_workflow_progress",
                new_callable=AsyncMock,
            ),
        ):
            asyncio.run(executor.handle(approved, ctx))

        ctx.request_info.assert_not_awaited()

    def test_counter_incremented_on_acceptance(self) -> None:
        """Accepting the practice offer increments the cycle counter."""
        executor = PostStudyPlanExecutor()
        initial_count = 1
        ctx = _make_ctx(
            {
                CROSS_ROUTE_CYCLE_KEY: initial_count,
                POST_STUDY_PLAN_CTX_KEY: {
                    "certification": "AZ-900",
                    "context": "some context",
                },
            },
        )

        with patch(
            "executors.post_study_plan_executor.emit_response",
            new_callable=AsyncMock,
        ):
            asyncio.run(
                executor.on_practice_offer(
                    {"type": "practice_offer"},
                    "yes",
                    ctx,
                )
            )

        # Counter should be incremented.
        new_count = asyncio.run(
            ctx.shared_state.get(CROSS_ROUTE_CYCLE_KEY),
        )
        assert new_count == initial_count + 1

        # RoutingDecision should have been sent.
        ctx.send_message.assert_awaited_once()

    def test_counter_not_incremented_on_decline(self) -> None:
        """Declining the practice offer does NOT increment the counter."""
        executor = PostStudyPlanExecutor()
        ctx = _make_ctx(
            {
                CROSS_ROUTE_CYCLE_KEY: 1,
                POST_STUDY_PLAN_CTX_KEY: {
                    "certification": "AZ-900",
                    "context": "",
                },
            },
        )

        with patch(
            "executors.post_study_plan_executor.emit_response",
            new_callable=AsyncMock,
        ):
            asyncio.run(
                executor.on_practice_offer(
                    {"type": "practice_offer"},
                    "no",
                    ctx,
                )
            )

        count = asyncio.run(
            ctx.shared_state.get(CROSS_ROUTE_CYCLE_KEY),
        )
        assert count == 1  # unchanged

    def test_counter_defaults_to_zero(self) -> None:
        """When no counter exists in shared state, default is 0."""
        executor = PostStudyPlanExecutor()
        ctx = _make_ctx({})  # no cycle key
        approved = _make_approved()

        with (
            patch(
                "executors.post_study_plan_executor.emit_response",
                new_callable=AsyncMock,
            ),
            patch(
                "executors.post_study_plan_executor.emit_response_streamed",
                new_callable=AsyncMock,
            ),
            patch(
                "executors.post_study_plan_executor.update_workflow_progress",
                new_callable=AsyncMock,
            ),
        ):
            asyncio.run(executor.handle(approved, ctx))

        # Should still offer practice (0 < 2).
        ctx.request_info.assert_awaited_once()


# ── PracticeQuestionsExecutor Tests ──────────────────────────────────


class TestPracticeQuestionsCycleBreaker:
    """PracticeQuestionsExecutor cycle breaker on quiz failure."""

    def test_study_plan_offered_when_below_cap(self) -> None:
        """Counter < MAX → study plan offer shown on quiz failure."""
        from executors.practice_questions_executor import (
            QUIZ_STATE_KEY,
            PracticeQuestionsExecutor,
        )

        practice_agent = MagicMock()
        learning_path_agent = MagicMock()
        executor = PracticeQuestionsExecutor(
            practice_agent=practice_agent,
            learning_path_agent=learning_path_agent,
        )

        state = _make_quiz_state()
        ctx = _make_ctx(
            {
                QUIZ_STATE_KEY: state.model_dump(),
                CROSS_ROUTE_CYCLE_KEY: 0,
            },
        )

        with (
            patch.object(
                executor,
                "_generate_feedback_report",
                new_callable=AsyncMock,
                return_value="Feedback report",
            ),
            patch(
                "executors.practice_questions_executor.emit_response",
                new_callable=AsyncMock,
            ),
            patch(
                "executors.practice_questions_executor.emit_state_snapshot",
                new_callable=AsyncMock,
            ),
        ):
            asyncio.run(executor._score_and_report(state, ctx))

        # Study plan HITL offer should be shown.
        ctx.request_info.assert_awaited_once()
        req = ctx.request_info.call_args
        assert req[1]["request_data"]["type"] == "study_plan_offer"

    def test_study_plan_suppressed_at_cap(self) -> None:
        """Counter = MAX → study plan offer suppressed on quiz failure."""
        from executors.practice_questions_executor import (
            QUIZ_STATE_KEY,
            PracticeQuestionsExecutor,
        )

        practice_agent = MagicMock()
        learning_path_agent = MagicMock()
        executor = PracticeQuestionsExecutor(
            practice_agent=practice_agent,
            learning_path_agent=learning_path_agent,
        )

        state = _make_quiz_state()
        ctx = _make_ctx(
            {
                QUIZ_STATE_KEY: state.model_dump(),
                CROSS_ROUTE_CYCLE_KEY: MAX_CROSS_ROUTE_CYCLES,
            },
        )

        with (
            patch.object(
                executor,
                "_generate_feedback_report",
                new_callable=AsyncMock,
                return_value="Feedback report",
            ),
            patch(
                "executors.practice_questions_executor.emit_response",
                new_callable=AsyncMock,
            ) as mock_emit,
            patch(
                "executors.practice_questions_executor.emit_state_snapshot",
                new_callable=AsyncMock,
            ),
        ):
            asyncio.run(executor._score_and_report(state, ctx))

        # HITL should NOT have been called.
        ctx.request_info.assert_not_awaited()

        # Tips message should have been emitted.
        tips_calls = [
            c
            for c in mock_emit.await_args_list
            if "multiple study-and-practice rounds" in str(c)
        ]
        assert len(tips_calls) == 1


# ── Constants Tests ──────────────────────────────────────────────────


class TestCycleBreakerConstants:
    """Verify shared constants are consistent."""

    def test_max_cycles_is_two(self) -> None:
        """Default cap should be 2."""
        assert MAX_CROSS_ROUTE_CYCLES == 2

    def test_shared_state_key_name(self) -> None:
        """Key name should be descriptive and stable."""
        assert CROSS_ROUTE_CYCLE_KEY == "cross_route_cycle_count"

    def test_same_key_used_in_practice_executor(self) -> None:
        """Both executors must use the same shared-state key."""
        from executors.practice_questions_executor import (
            CROSS_ROUTE_CYCLE_KEY as PQ_KEY,
        )

        assert PQ_KEY == CROSS_ROUTE_CYCLE_KEY

    def test_same_cap_used_in_practice_executor(self) -> None:
        """Both executors must use the same cap value."""
        from executors.practice_questions_executor import (
            MAX_CROSS_ROUTE_CYCLES as PQ_CAP,
        )

        assert PQ_CAP == MAX_CROSS_ROUTE_CYCLES
