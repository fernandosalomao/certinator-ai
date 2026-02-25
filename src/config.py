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
#   - azure:  Azure AI Foundry (requires AZ CLI login + LLM_ENDPOINT)
#   - github: GitHub Models (requires GITHUB_TOKEN)
#   - local:  FoundryLocal (runs locally, no endpoint required)
LLM_PROVIDER: Literal["azure", "github", "local"] = os.getenv(
    "LLM_PROVIDER", "azure"
).lower()  # type: ignore[assignment]

# ── Shared Endpoint ───────────────────────────────────────────────────────
# LLM_ENDPOINT is used by both Azure and GitHub providers.
#   - azure:  Azure AI Foundry project endpoint
#             e.g. https://<name>.services.ai.azure.com/api/projects/<id>
#   - github: GitHub Models inference endpoint
#             e.g. https://models.github.ai/inference (default)
#   - local:  not required (FoundryLocal manages its own endpoint)
LLM_ENDPOINT: str = os.getenv(
    "LLM_ENDPOINT",
    # Sensible defaults per provider
    "https://models.github.ai/inference" if LLM_PROVIDER == "github" else "",
)

# ── GitHub Models Configuration ───────────────────────────────────────────
# GitHub Models provides free/low-cost access to GPT-4o, GPT-4o-mini, etc.
# See: https://github.com/marketplace/models
GITHUB_TOKEN: str = os.getenv("GITHUB_TOKEN", "")

# ── Per-provider default model names ─────────────────────────────────────
_PROVIDER_DEFAULT_MODELS: dict[str, str] = {
    "azure": "gpt-4.1",
    "github": "openai/gpt-4o",
    "local": "qwen2.5-14b",
}

# ── Default model (used by all agents unless overridden) ─────────────────
# LLM_MODEL_DEFAULT falls back to a sensible per-provider default when unset.
LLM_MODEL_DEFAULT: str = os.getenv(
    "LLM_MODEL_DEFAULT",
    _PROVIDER_DEFAULT_MODELS.get(LLM_PROVIDER, "gpt-4.1"),
)

# ── Per-agent model overrides ─────────────────────────────────────────────
# Each agent reads its own env var; falls back to LLM_MODEL_DEFAULT.
LLM_MODEL_COORDINATOR: str = os.getenv("LLM_MODEL_COORDINATOR", LLM_MODEL_DEFAULT)
LLM_MODEL_CERTIFICATION_INFO: str = os.getenv(
    "LLM_MODEL_CERTIFICATION_INFO", LLM_MODEL_DEFAULT
)
LLM_MODEL_CRITIC: str = os.getenv("LLM_MODEL_CRITIC", LLM_MODEL_DEFAULT)
LLM_MODEL_LEARNING_PATH_FETCHER: str = os.getenv(
    "LLM_MODEL_LEARNING_PATH_FETCHER", LLM_MODEL_DEFAULT
)
LLM_MODEL_PRACTICE_QUESTIONS: str = os.getenv(
    "LLM_MODEL_PRACTICE_QUESTIONS", LLM_MODEL_DEFAULT
)
LLM_MODEL_STUDY_PLAN_GENERATOR: str = os.getenv(
    "LLM_MODEL_STUDY_PLAN_GENERATOR", LLM_MODEL_DEFAULT
)

# ── Feature Flags ─────────────────────────────────────────────────────────
# Default number of practice questions per quiz session.
DEFAULT_PRACTICE_QUESTIONS: int = int(os.getenv("DEFAULT_PRACTICE_QUESTIONS", "10"))


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
        LLM_MODEL_DEFAULT,
    )

    try:
        manager = FoundryLocalManager(LLM_MODEL_DEFAULT)
        model_info = manager.get_model_info(LLM_MODEL_DEFAULT)

        _foundry_local_conn = FoundryLocalConnection(
            endpoint=manager.endpoint,
            api_key=manager.api_key,
            model_id=model_info.id if model_info else LLM_MODEL_DEFAULT,
            model_alias=LLM_MODEL_DEFAULT,
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
        endpoint = LLM_ENDPOINT or "https://models.github.ai/inference"
        log.info(
            "Using GitHub Models → endpoint=%s  model=%s",
            endpoint,
            model_deployment_name,
        )
        return OpenAIChatClient(
            api_key=GITHUB_TOKEN,
            base_url=endpoint,
            model_id=model_deployment_name,
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

        endpoint = project_endpoint or LLM_ENDPOINT
        if not endpoint or not credential:
            raise ValueError(
                "LLM_ENDPOINT (or project_endpoint) and Azure credential are "
                "required when LLM_PROVIDER=azure. "
                "Ensure LLM_ENDPOINT is set in your .env and you are logged "
                "in via 'az login'."
            )
        return AzureAIClient(
            project_endpoint=endpoint,
            model_deployment_name=model_deployment_name,
            credential=credential,
        )
