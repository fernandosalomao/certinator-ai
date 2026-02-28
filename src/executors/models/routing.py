"""
Certinator AI — Routing data models.

Typed routing decision and coordinator response schemas that flow
from the CoordinatorExecutor to specialist handlers.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class RoutingDecision(BaseModel):
    """Structured routing decision produced by the Coordinator agent."""

    reasoning: str = Field(
        default="",
        description="Chain-of-thought explanation of the routing decision.",
    )
    route: Literal[
        "certification-info", "study-plan-generator", "practice-questions", "general"
    ] = Field(
        description="Target specialist route.",
    )
    task: str = Field(
        description="Clear task description for the specialist agent.",
    )
    certification: str = Field(
        default="",
        description="Exam code such as AZ-104 or AZ-305.",
    )
    context: str = Field(
        default="",
        description="Additional user context (schedule, preferences).",
    )
    response: str = Field(
        default="",
        description="Direct response — only populated for the 'general' route.",
    )


class CoordinatorResponse(BaseModel):
    """Strict response schema used with response_format for Coordinator."""

    model_config = ConfigDict(extra="forbid")

    reasoning: str = Field(
        description=(
            "Chain-of-thought explanation of the routing decision. "
            "Think step-by-step: identify the user's primary intent, "
            "note any ambiguity or multiple intents, then justify the "
            "chosen route. Fill this BEFORE selecting the route."
        ),
    )
    route: Literal[
        "certification-info", "study-plan-generator", "practice-questions", "general"
    ] = Field(
        description="Target specialist route.",
    )
    task: str = Field(description="Clear task description for the specialist.")
    certification: str = Field(description="Exam code such as AZ-104 or AZ-305.")
    context: str = Field(description="Additional user context.")
    response: str = Field(
        description="Direct response text; used for general route.",
    )
