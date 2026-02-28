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


def is_mcp_error(exc: Exception) -> bool:
    """
    Return True when *exc* indicates an MCP connectivity failure.

    Classifies network-level and HTTP server-error exceptions that
    originate from the MS Learn MCP endpoint
    (``learn.microsoft.com/api/mcp``) as MCP errors.  Falls back to
    inspecting the exception message for MCP-related keywords when the
    exception type alone is not conclusive.

    Parameters:
        exc (Exception): The exception to classify.

    Returns:
        bool: True if the error is likely caused by MCP unavailability.
    """
    # Network / transport layer errors are always MCP candidates
    if isinstance(exc, (TimeoutError, OSError, ConnectionError)):
        return True

    # httpx errors emitted by the agent framework's HTTP transport
    try:
        import httpx  # optional dependency — present when agent_framework is

        if isinstance(
            exc,
            (
                httpx.TimeoutException,
                httpx.ConnectError,
                httpx.RemoteProtocolError,
            ),
        ):
            return True

        # HTTP 5xx from the MCP server itself
        if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code >= 500:
            return True
    except ImportError:  # pragma: no cover — httpx always present with AF
        pass

    # Catch SDK-wrapped errors whose message references the MCP endpoint
    msg = str(exc).lower()
    return "learn.microsoft.com" in msg or "/api/mcp" in msg
