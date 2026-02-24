"""
Certinator AI — Workflow Graph Builder

Constructs the MAF graph-based workflow that wires the Coordinator
executor to specialist executors, with a shared CriticExecutor node
that validates output and can loop back for revision.

Graph topology::

    CoordinatorExecutor (start)
        │
        └── switch-case on RoutingDecision.route:
              ├── "certification-info"  → CertificationInfoExecutor  ──► CriticExecutor
              │                                                             ├── PASS → emit
              │                                                             └── FAIL → revision
              │
              ├── "study-plan-generator" → LearningPathFetcherExecutor
              │                                 │ (LearningPathsData)
              │                                 ▼
              │                          StudyPlanGeneratorExecutor ──► CriticExecutor
              │                                                            ├── PASS → PostStudyPlanExecutor
              │                                                            │             ├── HITL YES → PracticeQuestionsExecutor
              │                                                            │             └── HITL NO  → end
              │                                                            └── FAIL → revision
              │
              ├── "practice-questions"   → PracticeQuestionsExecutor (HITL quiz loop)
              │                                 ├── PASS  → congratulations (terminal)
              │                                 └── FAIL  → HITL study plan offer
              │                                       ├── YES → LearningPathFetcher pipeline
              │                                       └── NO  → end
              │
              └── default      → GeneralExecutor
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
    create_cert_info_agent_no_mcp,
    create_coordinator_agent,
    create_critic_agent,
    create_learning_path_fetcher_agent,
    create_practice_agent,
    create_study_plan_agent,
)
from config import (
    FOUNDRY_PROJECT_ENDPOINT,
)
from executors.certification_info_executor import CertificationInfoExecutor
from executors.coordinator_executor import CoordinatorExecutor
from executors.critic_executor import CriticExecutor
from executors.learning_path_fetcher_executor import LearningPathFetcherExecutor
from executors.models import (
    ApprovedStudyPlanOutput,
    RevisionRequest,
    RoutingDecision,
    StudyPlanFromQuizRequest,
)
from executors.post_study_plan_executor import PostStudyPlanExecutor
from executors.practice_questions_executor import PracticeQuestionsExecutor
from executors.study_plan_generator_executor import StudyPlanGeneratorExecutor
from tools.mcp import create_ms_learn_mcp_tool
from tools.schedule import schedule_study_plan

logger = logging.getLogger(__name__)


# ── Routing condition helpers ─────────────────────────────────────────────


def _is_route(expected: str):
    """
    Return a predicate that matches a RoutingDecision with the given route.

    Parameters:
        expected (str): The route value to match (e.g. "certification-info").

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
        executor_id (str): Target executor ID (e.g. "certification-info-executor").

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
    PostStudyPlanExecutor so that only approved study plans
    are forwarded for the HITL practice-question offer.

    Parameters:
        msg (Any): Message emitted by CriticExecutor.

    Returns:
        bool: True if the message is an ApprovedStudyPlanOutput.
    """
    return isinstance(msg, ApprovedStudyPlanOutput)


def _is_study_plan_from_quiz(msg: Any) -> bool:
    """Match a StudyPlanFromQuizRequest from PracticeQuestionsExecutor.

    Routes the post-quiz study plan request to
    LearningPathFetcherExecutor.

    Parameters:
        msg (Any): Message from PracticeQuestionsExecutor.

    Returns:
        bool: True if the message is a StudyPlanFromQuizRequest.
    """
    return isinstance(msg, StudyPlanFromQuizRequest)


# ── General-response handler (function-based executor) ────────────────────


@executor(id="general-executor")
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
            "general-executor",
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

    # CertificationInfoAgent with MS Learn MCP tool (client-side for Inspector visibility)
    mcp_tool = create_ms_learn_mcp_tool()
    cert_info_agent = create_cert_info_agent(
        FOUNDRY_PROJECT_ENDPOINT,
        credential,
        mcp_tool,
    )

    # Fallback agent: no MCP — used when learn.microsoft.com/api/mcp is down
    cert_info_fallback_agent = create_cert_info_agent_no_mcp(
        FOUNDRY_PROJECT_ENDPOINT,
        credential,
    )

    # LearningPathFetcher agent: uses MCP to retrieve structured topic data
    learning_path_agent = create_learning_path_fetcher_agent(
        FOUNDRY_PROJECT_ENDPOINT,
        credential,
        mcp_tool,
    )

    # StudyPlanGeneratorAgent: uses math tool only — NO MCP (data comes from fetcher)
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
    coordinator_executor = CoordinatorExecutor(coordinator_agent)

    certification_info_executor = CertificationInfoExecutor(
        cert_info_agent=cert_info_agent,
        cert_info_fallback_agent=cert_info_fallback_agent,
    )
    learning_path_fetcher_executor = LearningPathFetcherExecutor(
        learning_path_agent=learning_path_agent,
    )
    study_plan_generator_executor = StudyPlanGeneratorExecutor(
        study_plan_agent=study_plan_agent,
    )
    practice_questions_executor = PracticeQuestionsExecutor(
        practice_agent=practice_agent,
        learning_path_agent=learning_path_agent,
    )
    critic_executor = CriticExecutor(
        critic_agent=critic_agent,
    )
    post_study_plan_executor = PostStudyPlanExecutor()

    # ── Build the workflow graph ──────────────────────────────────────
    workflow = (
        WorkflowBuilder()
        .set_start_executor(coordinator_executor)
        .add_switch_case_edge_group(
            coordinator_executor,
            [
                Case(
                    condition=_is_route("certification-info"),
                    target=certification_info_executor,
                ),
                Case(
                    condition=_is_route("study-plan-generator"),
                    target=learning_path_fetcher_executor,
                ),
                Case(
                    condition=_is_route("practice-questions"),
                    target=practice_questions_executor,
                ),
                Default(target=general_handler),
            ],
        )
        # Specialist → Critic validation edges
        .add_edge(certification_info_executor, critic_executor)
        # LearningPathFetcherExecutor → StudyPlanGeneratorExecutor pipeline
        .add_edge(learning_path_fetcher_executor, study_plan_generator_executor)
        .add_edge(study_plan_generator_executor, critic_executor)
        # Critic → PostStudyPlanExecutor (approved study plans)
        .add_edge(
            critic_executor,
            post_study_plan_executor,
            condition=_is_approved_study_plan,
        )
        # PostStudyPlanExecutor → Practice (student wants practice)
        .add_edge(
            post_study_plan_executor,
            practice_questions_executor,
        )
        # Practice → LearningPathFetcherExecutor (post-quiz study plan)
        .add_edge(
            practice_questions_executor,
            learning_path_fetcher_executor,
            condition=_is_study_plan_from_quiz,
        )
        # Critic → Specialist revision loops (conditional)
        .add_edge(
            critic_executor,
            certification_info_executor,
            condition=_revision_for("certification-info-executor"),
        )
        .add_edge(
            critic_executor,
            study_plan_generator_executor,
            condition=_revision_for("study-plan-generator-executor"),
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

    # Wrap as an agent for HTTP serving
    agent = workflow.as_agent()
    logger.info("Certinator AI workflow built successfully")
    return agent, credential
