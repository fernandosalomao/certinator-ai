"""
Certinator AI — Practice Handler Executor

Non-HITL practice flow for current app runtime.
Generates a full question set in one response.
"""

import logging
import re
from typing import Any

from agent_framework import (
    ChatAgent,
    ChatMessage,
    Executor,
    Role,
    WorkflowContext,
    handler,
)

from config import DEFAULT_PRACTICE_QUESTIONS
from executors import emit_response, extract_response_text
from executors.models import (
    LearningPathFetcherResponse,
    RevisionRequest,
    RoutingDecision,
    SpecialistOutput,
)

logger = logging.getLogger(__name__)


class PracticeHandler(Executor):
    """Generate practice questions for certification exams."""

    practice_agent: ChatAgent
    learning_path_agent: ChatAgent

    def __init__(
        self,
        practice_agent: ChatAgent,
        learning_path_agent: ChatAgent,
        id: str = "practice-handler",
    ):
        """Initialize practice executor dependencies.

        Parameters:
            practice_agent (ChatAgent): Agent used to generate practice output.
            learning_path_agent (ChatAgent): Agent used to fetch topics.
            id (str): Executor identifier.
        """
        self.practice_agent = practice_agent
        self.learning_path_agent = learning_path_agent
        super().__init__(id=id)

    @handler
    async def handle(
        self,
        decision: RoutingDecision,
        ctx: WorkflowContext,
    ) -> None:
        """Generate questions and stream directly to the user.

        Parameters:
            decision (RoutingDecision): Coordinator decision.
            ctx (WorkflowContext): Workflow context.
        """
        cert = decision.certification or "the requested certification"
        topics = await self._fetch_exam_topics(cert)
        question_count = self._extract_question_count(decision)

        topic_list = "\n".join(
            f"- {topic.get('name', 'Unknown')} ({topic.get('exam_weight_pct', 0)}%)"
            for topic in topics
        )

        prompt = (
            f"Generate exactly {question_count} multiple-choice questions for {cert}.\n\n"
            f"Topics and weights:\n{topic_list}\n\n"
            "Rules:\n"
            "- At least one question per topic\n"
            "- Remaining questions proportional to topic weight\n"
            "- 4 options (A,B,C,D), exactly one correct\n"
            "- Include correct answer and explanation\n"
            "- Use clear markdown formatting\n"
        )

        if decision.context:
            prompt += f"- Focus area: {decision.context}\n"

        response = await self.practice_agent.run(
            [ChatMessage(role=Role.USER, text=prompt)]
        )
        result_text = extract_response_text(
            response,
            fallback="I could not generate practice questions at this time.",
        )

        await emit_response(ctx, self.id, result_text)

    @handler
    async def handle_revision(
        self,
        revision: RevisionRequest,
        ctx: WorkflowContext,
    ) -> None:
        """Revise practice output based on critic feedback.

        Parameters:
            revision (RevisionRequest): Critic revision payload.
            ctx (WorkflowContext): Workflow context.
        """
        cert = revision.original_decision.certification or "the certification"
        feedback_list = "\n".join(f"- {item}" for item in revision.feedback)
        prompt = (
            f"Revise and improve the following practice content for {cert}.\n\n"
            f"Previous content:\n---\n{revision.previous_content}\n---\n\n"
            f"Reviewer comments:\n{feedback_list}\n\n"
            "Address all reviewer comments and produce improved output."
        )

        response = await self.practice_agent.run(
            [ChatMessage(role=Role.USER, text=prompt)]
        )
        revised_text = extract_response_text(
            response,
            fallback="Practice content could not be revised.",
        )

        await ctx.send_message(
            SpecialistOutput(
                content=revised_text,
                content_type="practice_questions",
                source_executor_id=self.id,
                iteration=revision.iteration,
                original_decision=revision.original_decision,
            )
        )

    async def _fetch_exam_topics(self, cert: str) -> list[dict]:
        """Fetch exam topics and weights from Microsoft Learn.

        Parameters:
            cert (str): Certification code.

        Returns:
            list[dict]: Topic list.
        """
        prompt = (
            f"Certification: {cert}\n\n"
            "Fetch exam topic names and percentage weights. "
            "Return data matching the configured structured schema."
        )

        response = await self.learning_path_agent.run(
            [ChatMessage(role=Role.USER, text=prompt)],
            response_format=LearningPathFetcherResponse,
        )

        topics = self._extract_topic_weights(response)
        if topics:
            return topics

        logger.warning("Practice: failed to parse topics for %s", cert)

        return [{"name": f"{cert} General", "exam_weight_pct": 100}]

    @staticmethod
    def _extract_topic_weights(response: Any) -> list[dict]:
        """Extract topic names and weights from structured response output."""
        structured = getattr(response, "value", None)

        if isinstance(structured, LearningPathFetcherResponse):
            return [
                {
                    "name": topic.name,
                    "exam_weight_pct": topic.exam_weight_pct,
                }
                for topic in structured.topics
            ]

        if isinstance(structured, dict):
            validated = LearningPathFetcherResponse.model_validate(structured)
            return [
                {
                    "name": topic.name,
                    "exam_weight_pct": topic.exam_weight_pct,
                }
                for topic in validated.topics
            ]

        return []

    @staticmethod
    def _extract_question_count(decision: RoutingDecision) -> int:
        """Extract requested question count from user intent.

        Parameters:
            decision (RoutingDecision): Coordinator decision.

        Returns:
            int: Clamped question count.
        """
        text = f"{decision.task} {decision.context}".lower()
        match = re.search(r"(\d+)\s*questions?", text)
        if match:
            return max(1, min(int(match.group(1)), 50))
        return DEFAULT_PRACTICE_QUESTIONS
