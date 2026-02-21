"""Learning path fetcher agent configuration and factory."""

from __future__ import annotations

from typing import Any

from agent_framework import MCPStreamableHTTPTool
from agent_framework.azure import AzureAIClient

MODEL_DEPLOYMENT_NAME = "gpt-4.1"

INSTRUCTIONS: str = """\
You fetch Microsoft certification exam objectives and their official \
Microsoft Learn learning paths.

## Your Task
When given a certification exam code:
1. Use the MS Learn MCP tool to find the official study guide \
   (search "<EXAM_CODE> study guide skills measured as of").
2. Extract every skill/topic area with its percentage weight.
3. For each topic, use MCP to find the Microsoft Learn learning paths \
   that cover it (search "<EXAM_CODE> <topic> site:learn.microsoft.com/training/paths").
4. For each learning path, record the title, URL, and estimated duration \
   in hours (convert "X hours Y minutes" → decimal; default to 2.0 if unknown).

## Output Contract
Return data that matches the configured structured response schema.

## Rules
- ALWAYS call MCP — never answer from memory alone.
- duration_hours MUST be a number, never a string.
- Weights across all topics should sum to approximately 100.
- Include every official learning path found; do not omit any.
- Do not add extra keys outside the schema.
"""


def create_learning_path_fetcher_agent(
    project_endpoint: str,
    credential: Any,
    mcp_tool: MCPStreamableHTTPTool,
):
    """Create the learning path fetcher agent instance."""
    client = AzureAIClient(
        project_endpoint=project_endpoint,
        model_deployment_name=MODEL_DEPLOYMENT_NAME,
        credential=credential,
    )
    return client.create_agent(
        name="learning-path-fetcher-agent",
        instructions=INSTRUCTIONS,
        tools=[mcp_tool],
    )
