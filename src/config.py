"""
Certinator AI — Configuration

Centralised configuration loaded from environment variables.
Per-agent model assignments follow the model strategy defined
in ARCHITECTURE.md § 2 (Model Strategy).
"""

from __future__ import annotations

import os

# ── Azure AI Foundry ──────────────────────────────────────────────────────
FOUNDRY_PROJECT_ENDPOINT: str = os.getenv("FOUNDRY_PROJECT_ENDPOINT", "")

# ── Per-agent model deployments ───────────────────────────────────────────
# Lighter models for routing / verification; stronger models for generation.
COORDINATOR_MODEL: str = os.getenv("COORDINATOR_MODEL", "gpt-4.1-mini")
CERT_INFO_MODEL: str = os.getenv("CERT_INFO_MODEL", "gpt-4.1")
STUDY_PLAN_MODEL: str = os.getenv("STUDY_PLAN_MODEL", "gpt-4.1")
PRACTICE_MODEL: str = os.getenv("PRACTICE_MODEL", "gpt-4.1")
CRITIC_MODEL: str = os.getenv("CRITIC_MODEL", "gpt-4.1-mini")

# ── Feature Flags ─────────────────────────────────────────────────────────
# Default number of practice questions per quiz session.
DEFAULT_PRACTICE_QUESTIONS: int = int(os.getenv("DEFAULT_PRACTICE_QUESTIONS", "10"))
