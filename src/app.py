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
import sys

from agent_framework import ChatMessage, Role
from agent_framework.observability import configure_otel_providers
from agent_framework_ag_ui import AgentFrameworkAgent
from dotenv import load_dotenv

from executors import extract_message_text

# Load environment variables (override=True for deployed environments)
load_dotenv(override=True)

# ---------------------------------------------------------------------------
# OpenTelemetry Tracing
# ---------------------------------------------------------------------------
# Sends traces to AI Toolkit trace viewer via gRPC on localhost:4317.
# Start the collector in VS Code: AI Toolkit > Tracing > Open.
configure_otel_providers(
    vs_code_extension_port=4317,  # AI Toolkit gRPC port
    enable_sensitive_data=True,  # Capture prompts and completions
)


# ---------------------------------------------------------------------------
# AG_UI
# ---------------------------------------------------------------------------
async def run_agui() -> None:
    """
    Run the AG_UI dashboard for visualizing agent interactions.

    This starts a FastAPI app with the Agent Framework endpoint and serves
    it with Uvicorn using the current asyncio event loop.
    """
    import uvicorn
    from agent_framework.ag_ui import add_agent_framework_fastapi_endpoint
    from fastapi import FastAPI

    from workflow import build_workflow

    # Build workflow asynchronously because it returns coroutine-based resources.
    agent, credential = await build_workflow()
    ag_agent = AgentFrameworkAgent(
        agent=agent,
        name="Certinator AI",
        description=(
            "Multi-agent system for Microsoft certification exam preparation."
        ),
    )

    app = FastAPI(title="Microsoft Agent Framework (Python) - Quickstart")
    add_agent_framework_fastapi_endpoint(app=app, agent=ag_agent, path="/")

    config = uvicorn.Config(app=app, host="0.0.0.0", port=8000)
    server = uvicorn.Server(config=config)

    try:
        await server.serve()
    finally:
        # Close async credential resource on shutdown.
        await credential.close()


# ---------------------------------------------------------------------------
# CLI Mode
# ---------------------------------------------------------------------------


async def run_cli():
    """
    Run the agent in interactive CLI mode.

    Starts a REPL loop that reads user input, sends it through the
    multi-agent workflow, and prints assistant responses to stdout.
    Type 'quit' or 'exit' to stop.
    """
    from workflow import build_workflow

    agent, credential = await build_workflow()
    print("Certinator AI — CLI Mode  (5 agents ready)")
    print("Type 'quit' or 'exit' to stop.\n")

    messages: list[ChatMessage] = []
    try:
        while True:
            user_input = input("You: ")
            if user_input.strip().lower() in ("quit", "exit"):
                break

            messages.append(ChatMessage(role=Role.USER, text=user_input))
            response = await agent.run(messages)
            for msg in response.messages:
                if msg.role == Role.ASSISTANT:
                    text = extract_message_text(msg)
                    print(f"Certinator: {text}\n")
                    messages.append(msg)
    finally:
        await credential.close()


# ---------------------------------------------------------------------------
# HTTP Server Mode (default)
# ---------------------------------------------------------------------------


async def run_server():
    """
    Run the agent as an HTTP server.

    Uses azure.ai.agentserver.agentframework to expose the workflow
    agent over HTTP, compatible with AI Toolkit Agent Inspector and
    agentdev CLI.
    """
    from azure.ai.agentserver.agentframework import from_agent_framework

    from workflow import build_workflow

    agent, credential = await build_workflow()
    try:
        await from_agent_framework(agent).run_async()
    finally:
        await credential.close()


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------


def main():
    """
    Parse CLI arguments and launch the appropriate mode.

    Defaults to HTTP server mode. Pass --cli for interactive terminal.
    """
    if "--cli" in sys.argv:
        asyncio.run(run_cli())
    elif "--agui" in sys.argv:
        asyncio.run(run_agui())
    else:
        asyncio.run(run_server())


if __name__ == "__main__":
    main()
