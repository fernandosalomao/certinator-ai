"""
Certinator AI — Custom OpenTelemetry Metrics

Defines all custom OTel metric instruments for quality signals.
Instruments are module-level singletons so they are created once and
reused across the process lifetime.

**Important**: this module must be imported *after* ``configure_otel_providers``
is called in ``app.py``, which registers the global MeterProvider that
backs these instruments.  All executors import this module at the top
of their files; because Python defers module execution until first
import, the provider is always ready by the time any executor runs.

Instruments
-----------
critic_verdicts
    Counter — PASS/FAIL verdicts from the Critic agent, labelled by
    ``verdict``, ``content_type``, and ``auto_approved``.

routing_decisions
    Counter — Coordinator routing decisions, labelled by ``route``.

quiz_scores
    Histogram — Overall quiz score percentage (0–100), labelled by
    ``certification``.

quiz_topic_scores
    Histogram — Per-topic quiz score percentage (0–100), labelled by
    ``topic`` and ``certification``.

hitl_study_plan_offers
    Counter — Student responses to the post-quiz study plan offer,
    labelled by ``accepted`` (true/false).

hitl_practice_offers
    Counter — Student responses to the post-study-plan practice offer,
    labelled by ``accepted`` (true/false).

mcp_calls
    Counter — MCP-backed agent call outcomes (cert info and learning
    path fetcher), labelled by ``executor`` and ``status``
    (success/error).
"""

from __future__ import annotations

from opentelemetry import metrics

_meter = metrics.get_meter("certinator_ai", "1.0.0")

# ---------------------------------------------------------------------------
# Critic quality signals
# ---------------------------------------------------------------------------

critic_verdicts = _meter.create_counter(
    name="certinator.critic.verdicts",
    description=(
        "Critic PASS/FAIL verdicts by content type. "
        "Attributes: verdict, content_type, auto_approved."
    ),
    unit="1",
)

# ---------------------------------------------------------------------------
# Coordinator routing
# ---------------------------------------------------------------------------

routing_decisions = _meter.create_counter(
    name="certinator.coordinator.routing_decisions",
    description=("Coordinator routing decisions by route. Attributes: route."),
    unit="1",
)

# ---------------------------------------------------------------------------
# Quiz scoring
# ---------------------------------------------------------------------------

quiz_scores = _meter.create_histogram(
    name="certinator.quiz.score_pct",
    description=("Overall quiz score percentage (0–100). Attributes: certification."),
    unit="%",
)

quiz_topic_scores = _meter.create_histogram(
    name="certinator.quiz.topic_score_pct",
    description=(
        "Per-topic quiz score percentage (0–100). Attributes: topic, certification."
    ),
    unit="%",
)

# ---------------------------------------------------------------------------
# HITL acceptance rates
# ---------------------------------------------------------------------------

hitl_study_plan_offers = _meter.create_counter(
    name="certinator.hitl.study_plan_offers",
    description=(
        "Post-quiz study plan offer responses. Attributes: accepted (true/false)."
    ),
    unit="1",
)

hitl_practice_offers = _meter.create_counter(
    name="certinator.hitl.practice_offers",
    description=(
        "Post-study-plan practice offer responses. Attributes: accepted (true/false)."
    ),
    unit="1",
)

# ---------------------------------------------------------------------------
# MCP call success / failure rates
# ---------------------------------------------------------------------------

mcp_calls = _meter.create_counter(
    name="certinator.mcp.calls",
    description=(
        "MCP-backed agent call outcomes. Attributes: executor, status (success/error)."
    ),
    unit="1",
)

mcp_unavailable_events = _meter.create_counter(
    name="certinator.mcp.unavailable_events",
    description=(
        "MCP unavailability events that triggered graceful degradation. "
        "Attributes: executor, degraded (true/false)."
    ),
    unit="1",
)

# ---------------------------------------------------------------------------
# Safety — input guard blocks
# ---------------------------------------------------------------------------

safety_blocks = _meter.create_counter(
    name="certinator.safety.blocks",
    description=(
        "User messages blocked by the InputGuardExecutor. "
        "Attributes: reason (prompt_injection/content_safety/"
        "exam_policy), category."
    ),
    unit="1",
)

output_safety_blocks = _meter.create_counter(
    name="certinator.safety.output_blocks",
    description=(
        "Agent outputs blocked or sanitized by the output content "
        "safety gate in CriticExecutor. "
        "Attributes: content_type, source_executor."
    ),
    unit="1",
)
