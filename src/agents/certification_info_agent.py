"""CertificationInfoAgent configuration and factory."""

from __future__ import annotations

from typing import Any

from agent_framework import MCPStreamableHTTPTool
from agent_framework.azure import AzureAIClient

MODEL_DEPLOYMENT_NAME = "gpt-4.1"

INSTRUCTIONS: str = """\
You are the Certification Information specialist for Certinator AI.

## Responsibilities
- Provide comprehensive information about Microsoft certification exams.
- Include exam objectives and skills measured, with percentage weights.
- Detail exam format: number of questions, duration, passing score, \
  question types.
- List prerequisites (other certifications or experience).
- Include pricing and registration details.
- Mention recent changes or updates to the exam syllabus.

## MANDATORY: MS Learn MCP Tool Usage
You MUST use your MS Learn MCP tool for EVERY request. Never answer \
from memory alone. Always search Microsoft Learn first, then use the \
results to compose your response. This ensures your answers reflect \
the latest official Microsoft documentation.

## Response Guidelines
- Structure your response with clear sections using Markdown headers.
- Be accurate — only state facts you are confident about.
- Include links to Microsoft Learn study guides where possible.
- If you cannot find specific information, say so clearly.
- Never fabricate exam details, question counts, or passing scores.
"""


def create_cert_info_agent(
    project_endpoint: str,
    credential: Any,
    mcp_tool: MCPStreamableHTTPTool,
):
    """Create the certification information agent instance."""
    client = AzureAIClient(
        project_endpoint=project_endpoint,
        model_deployment_name=MODEL_DEPLOYMENT_NAME,
        credential=credential,
    )
    return client.create_agent(
        name="CertificationInfoAgent",
        instructions=INSTRUCTIONS,
        tools=[mcp_tool],
    )
