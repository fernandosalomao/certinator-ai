"""
Certinator AI — Critic data models.

Typed schemas for critic validation verdicts and specialist output
that flows from specialist handlers to the CriticExecutor.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .routing import RoutingDecision


class CriticVerdict(BaseModel):
    """Structured validation result from the Critic agent."""

    verdict: Literal["PASS", "FAIL"] = Field(default="PASS")
    confidence: int = Field(default=80, ge=0, le=100)
    issues: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)


class CriticVerdictResponse(BaseModel):
    """Strict response schema used with response_format for Critic."""

    model_config = ConfigDict(extra="forbid")

    verdict: Literal["PASS", "FAIL"] = Field()
    confidence: int = Field(ge=0, le=100)
    issues: list[str] = Field()
    suggestions: list[str] = Field()


class SpecialistOutput(BaseModel):
    """Content produced by a specialist handler, routed to the Critic.

    Flows from CertificationInfoExecutor / StudyPlanGeneratorExecutor
    to CriticExecutor as the typed message that the workflow graph
    routes via edges.
    """

    content: str = Field(
        description="Generated text from the specialist agent.",
    )
    content_type: str = Field(
        description="Label such as 'certification_info' or 'study_plan'.",
    )
    source_executor_id: str = Field(
        description="ID of the executor that produced this content.",
    )
    iteration: int = Field(
        default=1,
        description="Current critic-review iteration (1-based).",
    )
    original_decision: RoutingDecision = Field(
        description="Original routing decision for re-generation context.",
    )
