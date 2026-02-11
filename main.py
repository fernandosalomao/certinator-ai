# Copyright (c) Certinator AI. All rights reserved.

"""Entry point for Certinator AI.

Constructs the Magentic orchestration workflow and launches
the DevUI for local testing.
"""

import asyncio
import logging
import os

from dotenv import load_dotenv

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger(__name__)


async def _build_workflow():
    """Build the orchestration workflow asynchronously."""
    from agent_framework.azure import AzureAIAgentsProvider
    from azure.identity.aio import AzureCliCredential

    from src.workflows.orchestration_workflow import (
        build_orchestration_workflow,
    )

    credential = AzureCliCredential()
    provider = AzureAIAgentsProvider(credential=credential)

    # Initialise the provider (enters async context)
    await credential.__aenter__()
    await provider.__aenter__()

    workflow = await build_orchestration_workflow(provider)
    return workflow, credential, provider


def main() -> None:
    """Launch Certinator AI with the DevUI."""
    load_dotenv()

    # Validate required environment variables
    required_vars = [
        "AZURE_AI_PROJECT_ENDPOINT",
        "AZURE_AI_MODEL_DEPLOYMENT_NAME",
    ]
    missing = [v for v in required_vars if not os.getenv(v)]
    if missing:
        logger.error(
            "Missing required environment variables: %s",
            ", ".join(missing),
        )
        logger.error(
            "Create a .env file with these variables or "
            "set them in your environment."
        )
        raise SystemExit(1)

    logger.info("=" * 60)
    logger.info("Certinator AI — Microsoft Certification Prep")
    logger.info("=" * 60)
    logger.info("")
    logger.info(
        "Building orchestration workflow with Azure AI "
        "Foundry Agents..."
    )

    # Build the workflow
    loop = asyncio.new_event_loop()
    workflow, credential, provider = loop.run_until_complete(
        _build_workflow()
    )
    loop.close()

    logger.info("Workflow built successfully!")
    logger.info("")
    logger.info("Launching DevUI...")
    logger.info(
        "Open your browser at http://localhost:8080 to "
        "start chatting."
    )
    logger.info("")

    # Launch the DevUI server
    from agent_framework.devui import serve

    serve(
        entities=[workflow],
        port=8080,
        auto_open=True,
    )


if __name__ == "__main__":
    main()
