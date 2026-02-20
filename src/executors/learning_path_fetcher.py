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

import json
import logging
import re

from agent_framework import (
    ChatAgent,
    ChatMessage,
    Executor,
    Role,
    WorkflowContext,
    handler,
)

from executors import extract_response_text
from executors.models import LearningPathsData, RoutingDecision

logger = logging.getLogger(__name__)

# Regex to strip optional markdown code-fence around a JSON block.
_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)


def _strip_fences(text: str) -> str:
    """Remove markdown code fences from a string, if present."""
    match = _JSON_FENCE_RE.search(text)
    return match.group(1).strip() if match else text.strip()


class LearningPathFetcherHandler(Executor):
    """
    Fetch exam topics and learning paths from Microsoft Learn.

    Uses the LearningPathFetcher agent (equipped with the MS Learn MCP
    tool) to search for exam objectives, skill weights, and the
    corresponding official learning paths with their durations.

    The agent is instructed to return a JSON object.  This handler
    parses it and emits a ``LearningPathsData`` message to the
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
        ctx: WorkflowContext,
    ) -> None:
        """
        Fetch topics + learning paths and forward to StudyPlanScheduler.

        Parameters:
            decision (RoutingDecision): Routing decision from Coordinator.
            ctx (WorkflowContext): Workflow context for messaging.
        """
        cert = decision.certification or "the requested certification"
        logger.info("LearningPathFetcher: fetching paths for %s", cert)

        prompt = (
            f"Certification: {cert}\n\n"
            f"Student request context: {decision.task} — {decision.context}\n\n"
            "Fetch the exam objectives with percentage weights and all "
            "official Microsoft Learn learning paths (with duration in hours) "
            "for this certification. Return ONLY the required JSON object."
        )
        messages = [ChatMessage(role=Role.USER, text=prompt)]
        response = await self.learning_path_agent.run(messages)

        raw_text = extract_response_text(response)
        topics = self._parse_topics(raw_text, cert)

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

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_topics(text: str, cert: str) -> list[dict]:
        """
        Parse the agent's JSON output into a list of topic dicts.

        Falls back to a minimal placeholder on any parse error so the
        downstream scheduler always receives valid data.

        Parameters:
            text (str): Raw text from the fetcher agent.
            cert (str): Certification code for fallback data.

        Returns:
            list[dict]: List of topic objects with learning_paths.
        """
        cleaned = _strip_fences(text)
        try:
            data = json.loads(cleaned)
            topics = data.get("topics", [])
            if isinstance(topics, list) and topics:
                return topics
        except (json.JSONDecodeError, AttributeError) as exc:
            logger.warning(
                "LearningPathFetcher: could not parse JSON (%s). "
                "Using empty fallback for %s.",
                exc,
                cert,
            )

        # Minimal fallback — scheduler will handle gracefully
        logger.warning("LearningPathFetcher: returning empty topics for %s", cert)
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
