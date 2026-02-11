# Copyright (c) Certinator AI. All rights reserved.

"""Certification Orchestration Workflow — Magentic orchestration.

Uses the ``MagenticBuilder`` pattern with the Orchestrator Agent
as the manager and the remaining agents / sub-workflows as
participants.  The manager dynamically plans, assigns tasks to
participants, tracks progress, and replans when needed.
"""

from agent_framework import Workflow
from agent_framework.azure import AzureAIAgentsProvider
from agent_framework.orchestrations import MagenticBuilder

from src.agents.assessment_agent import (
    ASSESSMENT_DESCRIPTION,
    ASSESSMENT_INSTRUCTIONS,
)
from src.agents.certification_agent import (
    CERTIFICATION_DESCRIPTION,
    CERTIFICATION_INSTRUCTIONS,
)
from src.agents.orchestrator_agent import (
    ORCHESTRATOR_DESCRIPTION,
    ORCHESTRATOR_INSTRUCTIONS,
)
from src.workflows.study_plan_workflow import (
    build_study_plan_workflow,
)


async def build_orchestration_workflow(
    provider: AzureAIAgentsProvider,
) -> Workflow:
    """Build the top-level certification orchestration workflow.

    The orchestrator (manager) coordinates:
    - A study-plan sub-workflow (wrapped as an agent).
    - An assessment agent.
    - A certification-info agent.

    Args:
        provider: An initialised ``AzureAIAgentsProvider``
            to create agents.

    Returns:
        A ``Workflow`` managed by the Magentic orchestrator.
    """
    # --- Manager (Orchestrator) agent ---
    orchestrator = await provider.create_agent(
        name="Orchestrator",
        description=ORCHESTRATOR_DESCRIPTION,
        instructions=ORCHESTRATOR_INSTRUCTIONS,
    )

    # --- Study Plan sub-workflow wrapped as an agent ---
    study_plan_wf = await build_study_plan_workflow(provider)
    study_plan_agent = study_plan_wf.as_agent(
        name="StudyPlanWorkflow",
    )

    # --- Assessment agent ---
    assessment = await provider.create_agent(
        name="AssessmentAgent",
        description=ASSESSMENT_DESCRIPTION,
        instructions=ASSESSMENT_INSTRUCTIONS,
    )

    # --- Certification Info agent ---
    certification = await provider.create_agent(
        name="CertificationAgent",
        description=CERTIFICATION_DESCRIPTION,
        instructions=CERTIFICATION_INSTRUCTIONS,
    )

    # --- Build Magentic workflow ---
    workflow = MagenticBuilder(
        participants=[
            study_plan_agent,
            assessment,
            certification,
        ],
        manager_agent=orchestrator,
        max_round_count=20,
        max_stall_count=3,
        max_reset_count=2,
    ).build()

    return workflow
