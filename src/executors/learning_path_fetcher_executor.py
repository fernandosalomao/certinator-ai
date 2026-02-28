"""
Certinator AI — Learning Path Fetcher Executor

Workflow node that sits between CoordinatorExecutor and
StudyPlanGeneratorExecutor.  Uses the LearningPathFetcherAgent (which
has the MS Learn MCP tool + Catalog API tool) to retrieve the official
Microsoft Learn training hierarchy (Learning Paths → Modules) for a
certification.  Output is a structured LearningPathsData message
consumed by StudyPlanGeneratorExecutor.

Graph position::

    CoordinatorExecutor ──► LearningPathFetcherExecutor ──► StudyPlanGeneratorExecutor
"""

import json
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

import metrics
from executors import (
    emit_response,
    extract_response_text,
    get_user_friendly_error,
    safe_agent_run,
    update_workflow_progress,
)
from executors.models import (
    LearningPathFetcherResponse,
    LearningPathsData,
    RoutingDecision,
    StudyPlanFromQuizRequest,
)

logger = logging.getLogger(__name__)


class LearningPathFetcherExecutor(Executor):
    """
    Fetch official Microsoft Learn learning paths and modules.

    Uses the LearningPathFetcherAgent (equipped with the MS Learn MCP
    tool and the Catalog API tool) to retrieve the training hierarchy
    for a certification: Learning Paths → Modules.

    The agent is called without response_format so it can invoke tools
    freely; this executor parses the JSON response from the agent's
    text output and emits a ``LearningPathsData`` message to the
    ``StudyPlanGeneratorExecutor``.
    """

    learning_path_agent: ChatAgent

    def __init__(
        self,
        learning_path_agent: ChatAgent,
        id: str = "learning-path-fetcher-executor",
    ):
        """
        Initialise with the learning path fetcher agent.

        Parameters:
            learning_path_agent (ChatAgent): Agent with MCP + Catalog
                API tool access.
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
        Fetch learning paths + modules and forward to StudyPlanGenerator.

        Parameters:
            decision (RoutingDecision): Routing decision from Coordinator.
            ctx (WorkflowContext): Workflow context for messaging.
        """
        cert = decision.certification or "the requested certification"
        await update_workflow_progress(
            ctx=ctx,
            route="study-plan-generator",
            active_executor=self.id,
            message="Learning Path Fetcher Agent: Fetching official Microsoft Learn learning paths and modules...",
            current_step=2,
            total_steps=5,
        )
        logger.info("LearningPathFetcher: fetching paths for %s", cert)

        prompt = (
            f"Certification: {cert}\n\n"
            f"Student request context: {decision.task} — {decision.context}\n\n"
            "After gathering all data via tool calls, return a single "
            "JSON object matching the LearningPathFetcherResponse schema."
        )
        response = await self._run_agent(prompt, cert, ctx)
        if response is None:
            return

        learning_paths, skills_at_a_glance = self._extract_learning_paths(
            response, cert
        )

        logger.info(
            "LearningPathFetcher: found %d learning paths for %s",
            len(learning_paths),
            cert,
        )

        await ctx.send_message(
            LearningPathsData(
                certification=cert,
                skills_at_a_glance=skills_at_a_glance,
                learning_paths=learning_paths,
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
        a focused study plan.  Fetches full training data and forwards
        to StudyPlanGeneratorExecutor via LearningPathsData.

        Parameters:
            request (StudyPlanFromQuizRequest): Quiz failure data.
            ctx (WorkflowContext): Workflow context.
        """
        cert = request.certification
        await update_workflow_progress(
            ctx=ctx,
            route="study-plan-generator",
            active_executor=self.id,
            message="Learning Path Fetcher Agent: Fetching focused learning paths for weak quiz topics...",
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
            "Fetch the official Microsoft Learn training content for "
            "this certification. Use the tools described in your "
            "instructions to get all learning paths and their "
            "modules.\n\n"
            "After gathering all data via tool calls, return a single "
            "JSON object matching the LearningPathFetcherResponse schema."
        )
        response = await self._run_agent(prompt, cert, ctx)
        if response is None:
            return

        learning_paths, skills_at_a_glance = self._extract_learning_paths(
            response, cert
        )

        logger.info(
            "LearningPathFetcher: found %d learning paths for post-quiz study plan (%s)",
            len(learning_paths),
            cert,
        )
        await ctx.send_message(
            LearningPathsData(
                certification=cert,
                skills_at_a_glance=skills_at_a_glance,
                learning_paths=learning_paths,
                original_decision=request.original_decision,
            )
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _run_agent(
        self,
        prompt: str,
        cert: str,
        ctx: WorkflowContext,
    ) -> Any | None:
        """
        Run the learning path agent and handle errors.

        Parameters:
            prompt (str): The prompt to send to the agent.
            cert (str): Certification code for logging/metrics.
            ctx (WorkflowContext): Workflow context for error messages.

        Returns:
            Any | None: Agent response, or None if the call failed.
        """
        messages = [ChatMessage(role=Role.USER, text=prompt)]
        try:
            # NOTE: Do NOT pass response_format here.
            # When response_format is set, the model short-circuits to
            # structured JSON output and skips tool calls entirely — the
            # MCP/catalog tools never fire.  Instead, let the agent call
            # tools freely and return unstructured text; we parse the
            # JSON response in _extract_learning_paths().
            response = await safe_agent_run(
                self.learning_path_agent,
                messages,
            )
            metrics.mcp_calls.add(
                1,
                {"executor": "learning-path-fetcher", "status": "success"},
            )
            return response
        except Exception as exc:
            metrics.mcp_calls.add(
                1,
                {"executor": "learning-path-fetcher", "status": "error"},
            )
            logger.error(
                "LearningPathFetcher agent call failed for %s: %s",
                cert,
                exc,
                exc_info=True,
            )
            await emit_response(
                ctx,
                self.id,
                get_user_friendly_error(
                    exc,
                    "I encountered an issue retrieving that information. Please try again.",
                ),
            )
            return None

    @staticmethod
    def _normalize_llm_keys(data: dict) -> dict:
        """Normalise common LLM key variations to the canonical schema.

        The LLM sometimes uses shorter or different key names than the
        Pydantic model expects.  This method maps common variants so
        ``model_validate`` succeeds.

        Known variations handled:
        - ``skills`` → ``skillsAtAGlance`` (top-level skills list)
        - ``name`` → ``skill_name`` inside skill items
        """
        # Top-level: "skills" → "skillsAtAGlance"
        if (
            "skills" in data
            and "skillsAtAGlance" not in data
            and "skills_at_a_glance" not in data
        ):
            data["skillsAtAGlance"] = data.pop("skills")

        # Skill items: "name" → "skill_name"
        for key in ("skillsAtAGlance", "skills_at_a_glance"):
            if key in data and isinstance(data[key], list):
                for item in data[key]:
                    if (
                        isinstance(item, dict)
                        and "name" in item
                        and "skill_name" not in item
                    ):
                        item["skill_name"] = item.pop("name")

        return data

    @staticmethod
    def _parse_response_value(response: Any) -> LearningPathFetcherResponse | None:
        """Parse the agent response into a LearningPathFetcherResponse.

        Handles three formats:
        1. Already a LearningPathFetcherResponse (from response_format)
        2. A dict (partial structured output)
        3. A string containing JSON (from tool-use flow without
           response_format)

        Returns:
            LearningPathFetcherResponse | None: Parsed response, or
                None if parsing fails.
        """
        structured = getattr(response, "value", None)

        # Case 1: already validated
        if isinstance(structured, LearningPathFetcherResponse):
            return structured

        # Case 2: dict
        if isinstance(structured, dict):
            try:
                normalised = LearningPathFetcherExecutor._normalize_llm_keys(
                    structured)
                return LearningPathFetcherResponse.model_validate(normalised)
            except Exception:
                pass

        # Case 3: string — extract JSON from text (may be wrapped in
        # markdown code fences or surrounded by prose)
        text = None
        if isinstance(structured, str):
            text = structured
        elif hasattr(response, "value") and isinstance(response.value, str):
            text = response.value

        # Case 4: response.value is None (agent ran without
        # response_format) — the actual text lives in
        # response.messages.  Use extract_response_text() to pull
        # the latest assistant text from the message chain.
        if text is None:
            text = extract_response_text(response) or None

        if text:
            # Try to find a JSON object in the text
            # First try: raw JSON parse
            try:
                data = json.loads(text)
                if isinstance(data, dict):
                    normalised = LearningPathFetcherExecutor._normalize_llm_keys(
                        data)
                    return LearningPathFetcherResponse.model_validate(normalised)
            except (json.JSONDecodeError, Exception):
                pass

            # Second try: extract from markdown code fences
            json_match = re.search(
                r"```(?:json)?\s*\n?(.*?)\n?\s*```",
                text,
                re.DOTALL,
            )
            if json_match:
                try:
                    data = json.loads(json_match.group(1))
                    if isinstance(data, dict):
                        normalised = LearningPathFetcherExecutor._normalize_llm_keys(
                            data
                        )
                        return LearningPathFetcherResponse.model_validate(normalised)
                except (json.JSONDecodeError, Exception):
                    pass

            # Third try: find the first { ... } block
            brace_match = re.search(r"\{.*\}", text, re.DOTALL)
            if brace_match:
                try:
                    data = json.loads(brace_match.group(0))
                    if isinstance(data, dict):
                        normalised = LearningPathFetcherExecutor._normalize_llm_keys(
                            data
                        )
                        return LearningPathFetcherResponse.model_validate(normalised)
                except (json.JSONDecodeError, Exception):
                    pass

        return None

    @staticmethod
    def _extract_learning_paths(
        response: Any, cert: str
    ) -> tuple[list[dict], list[dict]]:
        """
        Extract structured learning paths from an agent response object.

        Falls back to a minimal placeholder if the structured output is
        missing or invalid so downstream scheduling always receives data.

        Parameters:
            response (Any): Agent run response object.
            cert (str): Certification code for fallback data.

        Returns:
            tuple[list[dict], list[dict]]: (learning_paths, skills_at_a_glance).
        """
        parsed = LearningPathFetcherExecutor._parse_response_value(response)
        if parsed and parsed.learning_paths:
            lps = [lp.model_dump(mode="python")
                   for lp in parsed.learning_paths]
            skills = [sk.model_dump(mode="python")
                      for sk in parsed.skills_at_a_glance]
            return lps, skills

        logger.warning(
            "LearningPathFetcher: structured output missing; "
            "returning fallback learning paths for %s",
            cert,
        )
        return [
            {
                "title": f"Search Microsoft Learn for {cert}",
                "url": (
                    f"https://learn.microsoft.com/en-us/certifications/"
                    f"exams/{cert.lower().replace(' ', '-')}"
                ),
                "duration_minutes": 480.0,
                "module_count": 0,
                "modules": [],
            }
        ], []
