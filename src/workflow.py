"""
Certinator AI — Workflow Graph Builder

Constructs the MAF graph-based workflow that wires the Coordinator
router to specialist handlers, with a shared CriticExecutor node
that validates output and can loop back for revision.

Graph topology::

    CoordinatorRouter (start)
        │
        └── switch-case on RoutingDecision.route:
              ├── "cert_info"  → CertInfoHandler               ──┐
              ├── "study_plan" → LearningPathFetcherHandler        │
              │                        │ (LearningPathsData)       │
              │                        ▼                           │
              │                  StudyPlanSchedulerHandler ────────┤
              ├── "practice"   → PracticeHandler ─────────────────┤
              └── default      → GeneralHandler                   │
                                                                  │
    CriticExecutor  ◄─────────────────────────────────────────────┘
        ├── PASS → emit response (terminal)
        └── FAIL → RevisionRequest → source handler (loop)

    PracticeHandler also emits directly (in-quiz questions) and only
    sends the final evaluation through CriticExecutor.
"""

import logging
from typing import Any

from agent_framework import (
    AgentRunResponseUpdate,
    AgentRunUpdateEvent,
    Case,
    Default,
    MCPStreamableHTTPTool,
    Role,
    TextContent,
    WorkflowBuilder,
    WorkflowContext,
    executor,
)
from agent_framework.azure import AzureAIClient
from azure.identity.aio import DefaultAzureCredential

from agents.instructions import (
    CERT_INFO_INSTRUCTIONS,
    COORDINATOR_INSTRUCTIONS,
    CRITIC_INSTRUCTIONS,
    LEARNING_PATH_FETCHER_INSTRUCTIONS,
    PRACTICE_INSTRUCTIONS,
    STUDY_PLAN_INSTRUCTIONS,
)
from config import (
    CERT_INFO_MODEL,
    COORDINATOR_MODEL,
    CRITIC_MODEL,
    FOUNDRY_PROJECT_ENDPOINT,
    PRACTICE_MODEL,
    STUDY_PLAN_MODEL,
)
from executors.cert_info import CertInfoHandler
from executors.coordinator import CoordinatorRouter
from executors.critic import CriticExecutor
from executors.learning_path_fetcher import LearningPathFetcherHandler
from executors.models import RevisionRequest, RoutingDecision
from executors.practice import PracticeHandler
from executors.study_plan import StudyPlanSchedulerHandler
from tools.schedule import schedule_study_plan

logger = logging.getLogger(__name__)


# ── Routing condition helpers ─────────────────────────────────────────────


def _is_route(expected: str):
    """
    Return a predicate that matches a RoutingDecision with the given route.

    Parameters:
        expected (str): The route value to match (e.g. "cert_info").

    Returns:
        Callable[[Any], bool]: Predicate for switch-case edges.
    """

    def condition(msg: Any) -> bool:
        """Check if the message is a RoutingDecision with the expected route."""
        return isinstance(msg, RoutingDecision) and msg.route == expected

    return condition


def _revision_for(executor_id: str):
    """
    Return a predicate that matches a RevisionRequest targeting *executor_id*.

    Used on the conditional edges from CriticExecutor back to specialist
    handlers so each handler only receives its own revision requests.

    Parameters:
        executor_id (str): Target handler ID (e.g. "cert-info-handler").

    Returns:
        Callable[[Any], bool]: Predicate for conditional edges.
    """

    def condition(msg: Any) -> bool:
        """Check if the message is a RevisionRequest for the target handler."""
        return (
            isinstance(msg, RevisionRequest) and msg.source_executor_id == executor_id
        )

    return condition


# ── General-response handler (function-based executor) ────────────────────


@executor(id="general-handler")
async def general_handler(
    decision: RoutingDecision,
    ctx: WorkflowContext,
) -> None:
    """
    Emit the Coordinator's direct response for general queries.

    The Coordinator already generated the text; this executor simply
    streams it to the HTTP client.

    Parameters:
        decision (RoutingDecision): Contains the pre-generated response.
        ctx (WorkflowContext): Workflow context for emitting events.
    """
    from uuid import uuid4

    text = decision.response or "How can I help you today?"
    await ctx.add_event(
        AgentRunUpdateEvent(
            "general-handler",
            data=AgentRunResponseUpdate(
                contents=[TextContent(text=text)],
                role=Role.ASSISTANT,
                response_id=str(uuid4()),
            ),
        )
    )


# ── Workflow factory ──────────────────────────────────────────────────────


async def build_workflow():
    """
    Create all agents and assemble the Certinator AI workflow graph.

    Returns:
        tuple: ``(workflow_agent, credential)`` — the workflow wrapped
        as an agent for HTTP serving, plus the credential for cleanup.
    """
    credential = DefaultAzureCredential()

    # ── Create per-model AzureAI clients ──────────────────────────────
    mini_client = AzureAIClient(
        project_endpoint=FOUNDRY_PROJECT_ENDPOINT,
        model_deployment_name=COORDINATOR_MODEL,
        credential=credential,
    )
    main_client = AzureAIClient(
        project_endpoint=FOUNDRY_PROJECT_ENDPOINT,
        model_deployment_name=CERT_INFO_MODEL,
        credential=credential,
    )

    # Create separate clients only when model differs from main_client.
    study_client = (
        main_client
        if STUDY_PLAN_MODEL == CERT_INFO_MODEL
        else AzureAIClient(
            project_endpoint=FOUNDRY_PROJECT_ENDPOINT,
            model_deployment_name=STUDY_PLAN_MODEL,
            credential=credential,
        )
    )
    practice_client = (
        main_client
        if PRACTICE_MODEL == CERT_INFO_MODEL
        else AzureAIClient(
            project_endpoint=FOUNDRY_PROJECT_ENDPOINT,
            model_deployment_name=PRACTICE_MODEL,
            credential=credential,
        )
    )
    critic_client = (
        mini_client
        if CRITIC_MODEL == COORDINATOR_MODEL
        else AzureAIClient(
            project_endpoint=FOUNDRY_PROJECT_ENDPOINT,
            model_deployment_name=CRITIC_MODEL,
            credential=credential,
        )
    )

    # ── Create agents ─────────────────────────────────────────────────
    coordinator_agent = mini_client.create_agent(
        name="coordinator-agent",
        instructions=COORDINATOR_INSTRUCTIONS,
    )

    # CertInfo agent with MS Learn MCP tool (client-side for Inspector visibility)
    mcp_tool = MCPStreamableHTTPTool(
        name="Microsoft Learn MCP",
        url="https://learn.microsoft.com/api/mcp",
        approval_mode="never_require",
    )
    cert_info_agent = main_client.create_agent(
        name="cert-info-agent",
        instructions=CERT_INFO_INSTRUCTIONS,
        tools=[mcp_tool],
    )

    # LearningPathFetcher agent: uses MCP to retrieve structured topic data
    learning_path_agent = main_client.create_agent(
        name="learning-path-fetcher-agent",
        instructions=LEARNING_PATH_FETCHER_INSTRUCTIONS,
        tools=[mcp_tool],
    )

    # StudyPlan agent: uses math tool only — NO MCP (data comes from fetcher)
    study_plan_agent = study_client.create_agent(
        name="study-plan-agent",
        instructions=STUDY_PLAN_INSTRUCTIONS,
        tools=[schedule_study_plan],
    )

    practice_agent = practice_client.create_agent(
        name="practice-question-agent",
        instructions=PRACTICE_INSTRUCTIONS,
    )

    critic_agent = critic_client.create_agent(
        name="critic-agent",
        instructions=CRITIC_INSTRUCTIONS,
    )

    # ── Instantiate executors ─────────────────────────────────────────
    coordinator_router = CoordinatorRouter(coordinator_agent)

    cert_info_handler = CertInfoHandler(
        cert_info_agent=cert_info_agent,
    )
    learning_path_fetcher = LearningPathFetcherHandler(
        learning_path_agent=learning_path_agent,
    )
    study_plan_scheduler = StudyPlanSchedulerHandler(
        study_plan_agent=study_plan_agent,
    )
    practice_handler = PracticeHandler(
        practice_agent=practice_agent,
        learning_path_agent=learning_path_agent,
    )
    critic_executor = CriticExecutor(
        critic_agent=critic_agent,
    )

    # ── Build the workflow graph ──────────────────────────────────────
    workflow = (
        WorkflowBuilder()
        .set_start_executor(coordinator_router)
        .add_switch_case_edge_group(
            coordinator_router,
            [
                Case(
                    condition=_is_route("cert_info"),
                    target=cert_info_handler,
                ),
                Case(
                    condition=_is_route("study_plan"),
                    target=learning_path_fetcher,
                ),
                Case(
                    condition=_is_route("practice"),
                    target=practice_handler,
                ),
                Default(target=general_handler),
            ],
        )
        # Specialist → Critic validation edges
        .add_edge(cert_info_handler, critic_executor)
        # LearningPathFetcher → StudyPlanScheduler (study plan pipeline)
        .add_edge(learning_path_fetcher, study_plan_scheduler)
        .add_edge(study_plan_scheduler, critic_executor)
        # Practice → Critic (final quiz evaluation only)
        .add_edge(practice_handler, critic_executor)
        # Critic → Specialist revision loops (conditional)
        .add_edge(
            critic_executor,
            cert_info_handler,
            condition=_revision_for("cert-info-handler"),
        )
        .add_edge(
            critic_executor,
            study_plan_scheduler,
            condition=_revision_for("study-plan-scheduler"),
        )
        .add_edge(
            critic_executor,
            practice_handler,
            condition=_revision_for("practice-handler"),
        )
        .build()
    )

    # Wrap as an agent for HTTP serving / CLI
    agent = workflow.as_agent()
    logger.info("Certinator AI workflow built successfully")
    return agent, credential
