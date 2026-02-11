# Copyright (c) Certinator AI. All rights reserved.

"""Study Plan Workflow — Sequential orchestration.

Pipeline: Learning Path Curator → Study Plan Generator → Reminder.

A ``StudentProfile`` is fed as the initial user message.  Each
agent enriches the conversation context.  The final output is
a populated study plan with calendar data ready for student
review.
"""

from agent_framework.azure import AzureAIAgentsProvider
from agent_framework.orchestrations import SequentialBuilder

from src.agents.learning_path_curator_agent import (
    CURATOR_DESCRIPTION,
    CURATOR_INSTRUCTIONS,
)
from src.agents.reminder_agent import (
    REMINDER_DESCRIPTION,
    REMINDER_INSTRUCTIONS,
)
from src.agents.study_plan_generator_agent import (
    GENERATOR_DESCRIPTION,
    GENERATOR_INSTRUCTIONS,
)


async def build_study_plan_workflow(
    provider: AzureAIAgentsProvider,
):
    """Build the sequential study-plan workflow.

    Args:
        provider: An initialised ``AzureAIAgentsProvider``
            to create the participating agents.

    Returns:
        A ``Workflow`` that chains Curator → Generator →
        Reminder sequentially.
    """
    curator = await provider.create_agent(
        name="LearningPathCurator",
        description=CURATOR_DESCRIPTION,
        instructions=CURATOR_INSTRUCTIONS,
    )

    generator = await provider.create_agent(
        name="StudyPlanGenerator",
        description=GENERATOR_DESCRIPTION,
        instructions=GENERATOR_INSTRUCTIONS,
    )

    reminder = await provider.create_agent(
        name="ReminderAgent",
        description=REMINDER_DESCRIPTION,
        instructions=REMINDER_INSTRUCTIONS,
    )

    workflow = SequentialBuilder(
        participants=[curator, generator, reminder],
    ).build()

    return workflow
