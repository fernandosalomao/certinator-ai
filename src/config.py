"""
Certinator AI — Configuration

Centralised configuration loaded from environment variables.
"""

from __future__ import annotations

import os

# ── Azure AI Foundry ──────────────────────────────────────────────────────
FOUNDRY_PROJECT_ENDPOINT: str = os.getenv("FOUNDRY_PROJECT_ENDPOINT", "")

# ── Feature Flags ─────────────────────────────────────────────────────────
# Default number of practice questions per quiz session.
DEFAULT_PRACTICE_QUESTIONS: int = int(os.getenv("DEFAULT_PRACTICE_QUESTIONS", "10"))
