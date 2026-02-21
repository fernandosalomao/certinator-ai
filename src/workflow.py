"""
Certinator AI — Workflow Graph Builder

Constructs the MAF graph-based workflow that wires the Coordinator
router to specialist handlers, with a shared CriticExecutor node
that validates output and can loop back for revision.

Graph topology::

    CoordinatorRouter (start)
        │
        └── switch-case on RoutingDecision.route:
              ├── "cert_info"  → CertInfoHandler  ──► CriticExecutor
              │                                         ├── PASS → emit
              │                                         └── FAIL → revision
              │
              ├── "study_plan" → LearningPathFetcherHandler
              │                        │ (LearningPathsData)
              │                        ▼
              │                  StudyPlanSchedulerHandler ──► CriticExecutor
              │                                                  ├── PASS → PostStudyPlanHandler
              │                                                  │             ├── HITL YES → PracticeQuizOrchestrator
              │                                                  │             └── HITL NO  → end
              │                                                  └── FAIL → revision
              │
              ├── "practice"   → PracticeQuizOrchestrator (HITL quiz loop)
              │                        ├── PASS  → congratulations (terminal)
              │                        └── FAIL  → HITL study plan offer
              │                              ├── YES → LearningPathFetcher pipeline
              │                              └── NO  → end
              │
              └── default      → GeneralHandler
"""

import logging
from typing import Any

from agent_framework import (
    AgentRunResponseUpdate,
    AgentRunUpdateEvent,
    Case,
    Default,
    Role,
    TextContent,
    WorkflowBuilder,
    WorkflowContext,
    WorkflowViz,
    executor,
)
from azure.identity.aio import DefaultAzureCredential

from agents import (
    create_cert_info_agent,
    create_coordinator_agent,
    create_critic_agent,
    create_learning_path_fetcher_agent,
    create_practice_agent,
    create_study_plan_agent,
)
from config import (
    FOUNDRY_PROJECT_ENDPOINT,
)
from executors.cert_info import CertInfoHandler
from executors.coordinator import CoordinatorRouter
from executors.critic import CriticExecutor
from executors.learning_path_fetcher import LearningPathFetcherHandler
from executors.models import (
    ApprovedStudyPlanOutput,
    RevisionRequest,
    RoutingDecision,
    StudyPlanFromQuizRequest,
)
from executors.post_study_plan import PostStudyPlanHandler
from executors.practice import PracticeQuizOrchestrator
from executors.study_plan import StudyPlanSchedulerHandler
from tools.mcp import create_ms_learn_mcp_tool
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


def _is_approved_study_plan(msg: Any) -> bool:
    """Match an ApprovedStudyPlanOutput from the CriticExecutor.

    Used on the conditional edge from CriticExecutor to
    PostStudyPlanHandler so that only approved study plans
    are forwarded for the HITL practice-question offer.

    Parameters:
        msg (Any): Message emitted by CriticExecutor.

    Returns:
        bool: True if the message is an ApprovedStudyPlanOutput.
    """
    return isinstance(msg, ApprovedStudyPlanOutput)


def _is_study_plan_from_quiz(msg: Any) -> bool:
    """Match a StudyPlanFromQuizRequest from PracticeQuizOrchestrator.

    Routes the post-quiz study plan request to
    LearningPathFetcherHandler.

    Parameters:
        msg (Any): Message from PracticeQuizOrchestrator.

    Returns:
        bool: True if the message is a StudyPlanFromQuizRequest.
    """
    return isinstance(msg, StudyPlanFromQuizRequest)


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

    # ── Create agents ─────────────────────────────────────────────────
    coordinator_agent = create_coordinator_agent(
        FOUNDRY_PROJECT_ENDPOINT,
        credential,
    )

    # CertInfo agent with MS Learn MCP tool (client-side for Inspector visibility)
    mcp_tool = create_ms_learn_mcp_tool()
    cert_info_agent = create_cert_info_agent(
        FOUNDRY_PROJECT_ENDPOINT,
        credential,
        mcp_tool,
    )

    # LearningPathFetcher agent: uses MCP to retrieve structured topic data
    learning_path_agent = create_learning_path_fetcher_agent(
        FOUNDRY_PROJECT_ENDPOINT,
        credential,
        mcp_tool,
    )

    # StudyPlan agent: uses math tool only — NO MCP (data comes from fetcher)
    study_plan_agent = create_study_plan_agent(
        FOUNDRY_PROJECT_ENDPOINT,
        credential,
        schedule_study_plan,
    )

    practice_agent = create_practice_agent(
        FOUNDRY_PROJECT_ENDPOINT,
        credential,
    )

    critic_agent = create_critic_agent(
        FOUNDRY_PROJECT_ENDPOINT,
        credential,
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
    practice_handler = PracticeQuizOrchestrator(
        practice_agent=practice_agent,
        learning_path_agent=learning_path_agent,
    )
    critic_executor = CriticExecutor(
        critic_agent=critic_agent,
    )
    post_study_plan_handler = PostStudyPlanHandler()

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
        # LearningPathFetcher → StudyPlanScheduler pipeline
        .add_edge(learning_path_fetcher, study_plan_scheduler)
        .add_edge(study_plan_scheduler, critic_executor)
        # Critic → PostStudyPlanHandler (approved study plans)
        .add_edge(
            critic_executor,
            post_study_plan_handler,
            condition=_is_approved_study_plan,
        )
        # PostStudyPlanHandler → Practice (student wants practice)
        .add_edge(
            post_study_plan_handler,
            practice_handler,
        )
        # Practice → LearningPathFetcher (post-quiz study plan)
        .add_edge(
            practice_handler,
            learning_path_fetcher,
            condition=_is_study_plan_from_quiz,
        )
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
        .build()
    )

    # Generate workflow visualization
    print("Generating workflow visualization...")
    viz = WorkflowViz(workflow)
    # Print out the mermaid string.
    print("Mermaid string: \n=======")
    print(viz.to_mermaid())
    print("=======")
    # Print out the DiGraph string with internal executors.
    print("DiGraph string: \n=======")
    print(viz.to_digraph(include_internal_executors=True))
    print("=======")

    # Export the DiGraph visualization as SVG.
    svg_file = viz.export(filename="workflow.svg", format="svg")
    print(f"SVG file saved to: {svg_file}")

    # Wrap as an agent for HTTP serving / CLI
    agent = workflow.as_agent()
    logger.info("Certinator AI workflow built successfully")
    return agent, credential
