"""
Certinator AI — Learning Path Fetcher Executor

New workflow node that sits between CoordinatorRouter and
StudyPlanSchedulerHandler.  Uses the LearningPathFetcher agent (which
has the MS Learn MCP tool) to retrieve exam topics, their percentage
weights, and the corresponding Microsoft Learn learning paths with
estimated durations.  Output is a structured LearningPathsData message
consumed by StudyPlanSchedulerHandler.

Graph position::

    CoordinatorRouter ──► LearningPathFetcherHandler ──► StudyPlanSchedulerHandler
"""

import logging
from typing import Any

from agent_framework import (
    ChatAgent,
    ChatMessage,
    Executor,
    Role,
    WorkflowContext,
    handler,
)

from executors import update_workflow_progress
from executors.models import (
    LearningPathFetcherResponse,
    LearningPathsData,
    RoutingDecision,
    StudyPlanFromQuizRequest,
)

logger = logging.getLogger(__name__)


class LearningPathFetcherHandler(Executor):
    """
    Fetch exam topics and learning paths from Microsoft Learn.

    Uses the LearningPathFetcher agent (equipped with the MS Learn MCP
    tool) to search for exam objectives, skill weights, and the
    corresponding official learning paths with their durations.

    The agent is called with a structured response format and this
    handler emits a ``LearningPathsData`` message to the
    ``StudyPlanSchedulerHandler``.
    """

    learning_path_agent: ChatAgent

    def __init__(
        self,
        learning_path_agent: ChatAgent,
        id: str = "learning-path-fetcher",
    ):
        """
        Initialise with the learning path fetcher agent.

        Parameters:
            learning_path_agent (ChatAgent): Agent with MS Learn MCP access.
            id (str): Executor identifier in the workflow graph.
        """
        self.learning_path_agent = learning_path_agent
        super().__init__(id=id)

    @handler
    async def handle(
        self,
        decision: RoutingDecision,
        ctx: WorkflowContext[LearningPathsData],
    ) -> None:
        """
        Fetch topics + learning paths and forward to StudyPlanScheduler.

        Parameters:
            decision (RoutingDecision): Routing decision from Coordinator.
            ctx (WorkflowContext): Workflow context for messaging.
        """
        cert = decision.certification or "the requested certification"
        await update_workflow_progress(
            ctx=ctx,
            route="study_plan",
            active_executor=self.id,
            message="Fetching official Microsoft Learn topics and paths...",
            current_step=2,
            total_steps=5,
        )
        logger.info("LearningPathFetcher: fetching paths for %s", cert)

        prompt = (
            f"Certification: {cert}\n\n"
            f"Student request context: {decision.task} — {decision.context}\n\n"
            "Fetch the exam objectives with percentage weights and all "
            "official Microsoft Learn learning paths (with duration in hours) "
            "for this certification. Return data that matches the configured "
            "structured response schema."
        )
        messages = [ChatMessage(role=Role.USER, text=prompt)]
        response = await self.learning_path_agent.run(
            messages,
            response_format=LearningPathFetcherResponse,
        )

        topics = self._extract_topics(response, cert)

        logger.info(
            "LearningPathFetcher: found %d topics for %s",
            len(topics),
            cert,
        )
        await ctx.send_message(
            LearningPathsData(
                certification=cert,
                topics=topics,
                original_decision=decision,
            )
        )

    @handler
    async def handle_quiz_study_plan(
        self,
        request: StudyPlanFromQuizRequest,
        ctx: WorkflowContext[LearningPathsData],
    ) -> None:
        """Fetch learning paths for a post-quiz study plan.

        Triggered when a student fails a practice quiz and wants
        a focused study plan.  Fetches full topic data and forwards
        to StudyPlanSchedulerHandler via LearningPathsData.

        Parameters:
            request (StudyPlanFromQuizRequest): Quiz failure data.
            ctx (WorkflowContext): Workflow context.
        """
        cert = request.certification
        await update_workflow_progress(
            ctx=ctx,
            route="study_plan",
            active_executor=self.id,
            message="Fetching focused learning paths for weak quiz topics...",
            current_step=2,
            total_steps=5,
        )
        logger.info(
            "LearningPathFetcher: fetching paths for "
            "post-quiz study plan (%s, weak: %s)",
            cert,
            request.weak_topics,
        )

        weak_str = ", ".join(request.weak_topics)
        prompt = (
            f"Certification: {cert}\n\n"
            f"The student needs help with these specific "
            f"topics: {weak_str}\n\n"
            "Fetch the exam objectives with percentage "
            "weights and all official Microsoft Learn "
            "learning paths (with duration in hours) for "
            "this certification. Return data that matches "
            "the configured structured response schema."
        )
        messages = [ChatMessage(role=Role.USER, text=prompt)]
        response = await self.learning_path_agent.run(
            messages,
            response_format=LearningPathFetcherResponse,
        )

        topics = self._extract_topics(response, cert)

        logger.info(
            "LearningPathFetcher: found %d topics for post-quiz study plan (%s)",
            len(topics),
            cert,
        )
        await ctx.send_message(
            LearningPathsData(
                certification=cert,
                topics=topics,
                original_decision=request.original_decision,
            )
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_topics(response: Any, cert: str) -> list[dict]:
        """
        Extract structured topics from an agent response object.

        Falls back to a minimal placeholder if the structured output is
        missing or invalid so downstream scheduling always receives data.

        Parameters:
            response (Any): Agent run response object.
            cert (str): Certification code for fallback data.

        Returns:
            list[dict]: List of topic objects with learning_paths.
        """
        structured = getattr(response, "value", None)
        if isinstance(structured, LearningPathFetcherResponse):
            topics = [topic.model_dump(mode="python") for topic in structured.topics]
            if topics:
                return topics

        if isinstance(structured, dict):
            try:
                validated = LearningPathFetcherResponse.model_validate(structured)
                topics = [topic.model_dump(mode="python") for topic in validated.topics]
                if topics:
                    return topics
            except Exception as exc:  # pragma: no cover - defensive fallback
                logger.warning(
                    "LearningPathFetcher: invalid structured response (%s) for %s.",
                    exc,
                    cert,
                )

        logger.warning(
            "LearningPathFetcher: structured output missing; "
            "returning fallback topics for %s",
            cert,
        )
        return [
            {
                "name": f"{cert} — topics unavailable",
                "exam_weight_pct": 100,
                "learning_paths": [
                    {
                        "name": f"Search Microsoft Learn for {cert}",
                        "url": (
                            f"https://learn.microsoft.com/en-us/certifications/"
                            f"exams/{cert.lower().replace(' ', '-')}"
                        ),
                        "duration_hours": 8.0,
                    }
                ],
            }
        ]
