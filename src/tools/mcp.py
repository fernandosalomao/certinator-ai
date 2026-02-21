"""Shared MCP tool builders for agent configuration."""

from __future__ import annotations

from agent_framework import MCPStreamableHTTPTool


def create_ms_learn_mcp_tool() -> MCPStreamableHTTPTool:
    """Build the Microsoft Learn MCP tool used by supported agents."""
    return MCPStreamableHTTPTool(
        name="Microsoft Learn MCP",
        url="https://learn.microsoft.com/api/mcp",
        approval_mode="never_require",
    )
