"""
Certinator AI — Configuration

Centralised configuration loaded from environment variables.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from agent_framework.azure import AzureAIClient
    from agent_framework.openai import OpenAIChatClient

log = logging.getLogger(__name__)

# ── LLM Provider Selection ────────────────────────────────────────────────
# Supported providers: "azure" (default), "github", "local"
#   - azure:  Azure AI Foundry (requires FOUNDRY_PROJECT_ENDPOINT)
#   - github: GitHub Models (requires GITHUB_TOKEN)
#   - local:  FoundryLocal (requires local installation)
LLM_PROVIDER: Literal["azure", "github", "local"] = os.getenv(
    "LLM_PROVIDER", "azure"
).lower()  # type: ignore[assignment]

# Legacy flag for backward compatibility (USE_LOCAL_LLM=true → LLM_PROVIDER=local)
if os.getenv("USE_LOCAL_LLM", "false").lower() in ("true", "1", "yes"):
    LLM_PROVIDER = "local"

# ── Azure AI Foundry ──────────────────────────────────────────────────────
FOUNDRY_PROJECT_ENDPOINT: str = os.getenv("FOUNDRY_PROJECT_ENDPOINT", "")

# ── GitHub Models Configuration ───────────────────────────────────────────
# GitHub Models provides free/low-cost access to GPT-4o, GPT-4o-mini, etc.
# See: https://github.com/marketplace/models
GITHUB_ENDPOINT: str = os.getenv(
    "GITHUB_ENDPOINT", "https://models.github.ai/inference"
)
GITHUB_TOKEN: str = os.getenv("GITHUB_TOKEN", "")
GITHUB_MODEL_ID: str = os.getenv("GITHUB_MODEL_ID", "openai/gpt-4.1")

# ── FoundryLocal Configuration ────────────────────────────────────────────
# Model alias for FoundryLocal (e.g., "phi-4-mini", "qwen2.5-0.5b")
# See: https://learn.microsoft.com/foundry/foundry-local/
FOUNDRY_LOCAL_MODEL_ALIAS: str = os.getenv("FOUNDRY_LOCAL_MODEL_ALIAS", "phi-4-mini")

# ── Feature Flags ─────────────────────────────────────────────────────────
# Default number of practice questions per quiz session.
DEFAULT_PRACTICE_QUESTIONS: int = int(os.getenv("DEFAULT_PRACTICE_QUESTIONS", "10"))

# Legacy alias for backward compatibility
USE_LOCAL_LLM: bool = LLM_PROVIDER == "local"


# ── FoundryLocal Connection ───────────────────────────────────────────────
@dataclass
class FoundryLocalConnection:
    """Holds the endpoint, API key, and model ID from FoundryLocal bootstrap."""

    endpoint: str
    api_key: str
    model_id: str
    model_alias: str


# Cached connection (singleton)
_foundry_local_conn: FoundryLocalConnection | None = None


def get_foundry_local_connection() -> FoundryLocalConnection:
    """
    Bootstrap FoundryLocal and return connection info.

    Uses foundry-local-sdk to start the service and download/load the model.
    Connection is cached for reuse across agents.

    Returns:
        FoundryLocalConnection: Endpoint, API key, and model info.

    Raises:
        SystemExit: If foundry-local-sdk is not installed or bootstrap fails.
    """
    global _foundry_local_conn

    if _foundry_local_conn is not None:
        return _foundry_local_conn

    try:
        from foundry_local import FoundryLocalManager
    except ImportError as exc:
        raise SystemExit(
            "\n❌  foundry-local-sdk is not installed.\n"
            "   Run:  pip install foundry-local-sdk\n"
            "   Docs: https://pypi.org/project/foundry-local-sdk/\n"
        ) from exc

    log.info(
        "Bootstrapping FoundryLocal with model alias '%s' ...",
        FOUNDRY_LOCAL_MODEL_ALIAS,
    )

    try:
        manager = FoundryLocalManager(FOUNDRY_LOCAL_MODEL_ALIAS)
        model_info = manager.get_model_info(FOUNDRY_LOCAL_MODEL_ALIAS)

        _foundry_local_conn = FoundryLocalConnection(
            endpoint=manager.endpoint,
            api_key=manager.api_key,
            model_id=model_info.id if model_info else FOUNDRY_LOCAL_MODEL_ALIAS,
            model_alias=FOUNDRY_LOCAL_MODEL_ALIAS,
        )
        log.info(
            "✅ FoundryLocal ready → endpoint=%s  model=%s",
            _foundry_local_conn.endpoint,
            _foundry_local_conn.model_id,
        )
        return _foundry_local_conn

    except FileNotFoundError:
        raise SystemExit(
            "\n❌  Foundry Local CLI not found on PATH.\n"
            "   Install it from: https://github.com/microsoft/Foundry-Local\n"
            "   Then verify:     foundry --help\n"
        )
    except Exception as exc:
        raise SystemExit(
            f"\n❌  Foundry Local bootstrap failed: {exc}\n"
            "   • Is Foundry Local installed?  https://github.com/microsoft/Foundry-Local\n"
            "   • Run: foundry model list   — to see available models.\n"
        ) from exc


def get_ai_client(
    model_deployment_name: str,
    project_endpoint: str | None = None,
    credential: Any | None = None,
) -> "AzureAIClient | OpenAIChatClient":
    """
    Factory function to get the appropriate AI client based on LLM_PROVIDER.

    Supported providers:
        - "azure": AzureAIClient for Azure AI Foundry
        - "github": OpenAIChatClient pointing at GitHub Models
        - "local": OpenAIChatClient pointing at FoundryLocal

    Parameters:
        model_deployment_name (str): Model deployment name (used for Azure AI).
        project_endpoint (str | None): Azure AI Foundry project endpoint.
        credential (Any | None): Azure credential for authentication.

    Returns:
        AzureAIClient | OpenAIChatClient: Configured client instance.

    Raises:
        ValueError: If required configuration is missing for the selected provider.
    """
    if LLM_PROVIDER == "github":
        from agent_framework.openai import OpenAIChatClient

        if not GITHUB_TOKEN:
            raise ValueError(
                "GITHUB_TOKEN is required when LLM_PROVIDER=github.\n"
                "Get your token from: https://github.com/settings/tokens"
            )
        log.info(
            "Using GitHub Models → endpoint=%s  model=%s",
            GITHUB_ENDPOINT,
            GITHUB_MODEL_ID,
        )
        return OpenAIChatClient(
            api_key=GITHUB_TOKEN,
            base_url=GITHUB_ENDPOINT,
            model_id=GITHUB_MODEL_ID,
        )

    elif LLM_PROVIDER == "local":
        from agent_framework.openai import OpenAIChatClient

        conn = get_foundry_local_connection()
        return OpenAIChatClient(
            api_key=conn.api_key,
            base_url=conn.endpoint,
            model_id=conn.model_id,
        )

    else:  # azure (default)
        from agent_framework.azure import AzureAIClient

        if not project_endpoint or not credential:
            raise ValueError(
                "project_endpoint and credential are required when LLM_PROVIDER=azure"
            )
        return AzureAIClient(
            project_endpoint=project_endpoint,
            model_deployment_name=model_deployment_name,
            credential=credential,
        )
