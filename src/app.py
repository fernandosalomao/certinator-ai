"""
Certinator AI — Main Entrypoint

Multi-agent system for Microsoft certification exam preparation.
Runs as an HTTP server for use with AI Toolkit Agent Inspector,
or in CLI mode for quick testing.

Usage:
    # HTTP server mode (default, used by agentdev / Agent Inspector)
    python src/app.py

    # CLI mode (interactive terminal)
    python src/app.py --cli
"""

import asyncio
import logging

from agent_framework.observability import configure_otel_providers
from agent_framework_ag_ui import AgentFrameworkAgent
from agent_framework_ag_ui._orchestrators import HumanInTheLoopOrchestrator
from dotenv import load_dotenv

from health import register_health_endpoints
from orchestrators import PersistentDefaultOrchestrator, RequestInfoOrchestrator
from state_schema import build_predict_state_config, build_state_schema

# Configure logging so our debug output is visible
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

# Load environment variables (override=True for deployed environments)
load_dotenv(override=True)

# ---------------------------------------------------------------------------
# OpenTelemetry Tracing
# ---------------------------------------------------------------------------
configure_otel_providers()


# ---------------------------------------------------------------------------
# AG-UI Server
# ---------------------------------------------------------------------------
async def run_agui() -> None:
    """Start the AG-UI FastAPI server.

    Builds the MAF workflow, wraps it in an ``AgentFrameworkAgent``
    with the custom orchestrator chain, and serves it on port 8000
    via Uvicorn.
    """
    import uvicorn
    from agent_framework.ag_ui import add_agent_framework_fastapi_endpoint
    from fastapi import FastAPI

    from workflow import build_workflow

    # Build workflow asynchronously because it returns coroutine-based resources.
    agent, credential = await build_workflow()

    # Use a custom orchestrator chain:
    #   1. RequestInfoOrchestrator — filters messages when
    #      the workflow has pending request_info HITL calls.
    #   2. HumanInTheLoopOrchestrator — handles tool approval
    #      responses (accept / reject).
    #   3. PersistentDefaultOrchestrator — standard agent execution
    #      with in-memory thread persistence.
    ag_agent = AgentFrameworkAgent(
        agent=agent,
        name="Certinator AI",
        description=(
            "Multi-agent system for Microsoft certification exam preparation."
        ),
        state_schema=build_state_schema(),
        predict_state_config=build_predict_state_config(),
        require_confirmation=False,
        orchestrators=[
            RequestInfoOrchestrator(),
            HumanInTheLoopOrchestrator(),
            PersistentDefaultOrchestrator(),
        ],
    )

    from config import AGUI_HOST, AGUI_PORT

    app = FastAPI(title="Microsoft Agent Framework (Python) - Quickstart")
    add_agent_framework_fastapi_endpoint(app=app, agent=ag_agent, path="/")

    # ------------------------------------------------------------------
    # Rate Limiting middleware (G12)
    # ------------------------------------------------------------------
    from rate_limiter import RateLimiterMiddleware

    app.add_middleware(RateLimiterMiddleware)

    # ------------------------------------------------------------------
    # Health check endpoints (G9)
    # ------------------------------------------------------------------
    register_health_endpoints(app)

    config = uvicorn.Config(app=app, host=AGUI_HOST, port=AGUI_PORT)
    server = uvicorn.Server(config=config)

    try:
        await server.serve()
    finally:
        # Close async credential resource on shutdown.
        await credential.close()


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------


def main():
    """Launch the AG-UI server."""
    asyncio.run(run_agui())


if __name__ == "__main__":
    main()
