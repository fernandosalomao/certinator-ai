"""
Certinator AI — Health Check Endpoints (G9)

Liveness and readiness probes for Kubernetes / Azure Container Apps.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Timeout (seconds) for readiness probe dependency checks.
_READY_CHECK_TIMEOUT: float = 5.0


async def _check_llm_endpoint() -> tuple[bool, str]:
    """Probe the LLM endpoint with a lightweight HTTP request.

    Returns:
        tuple[bool, str]: ``(ok, detail)`` — True if the endpoint
        is reachable, False with an error message otherwise.
    """
    import config as _cfg

    if _cfg.LLM_PROVIDER == "local":
        return True, "provider=local (implicit)"

    endpoint = _cfg.LLM_ENDPOINT
    if not endpoint:
        return False, "LLM_ENDPOINT not configured"

    try:
        import httpx

        async with httpx.AsyncClient(
            timeout=_READY_CHECK_TIMEOUT,
        ) as client:
            resp = await client.head(endpoint)
            if resp.status_code < 500:
                return True, f"status={resp.status_code}"
            return False, f"status={resp.status_code}"
    except Exception as exc:
        return False, str(exc)


async def _check_mcp_server() -> tuple[bool, str]:
    """Probe the MS Learn MCP server with a lightweight HTTP request.

    Returns:
        tuple[bool, str]: ``(ok, detail)`` — True if the MCP server
        is reachable, False with an error message otherwise.
    """
    mcp_url = "https://learn.microsoft.com/api/mcp"
    try:
        import httpx

        async with httpx.AsyncClient(
            timeout=_READY_CHECK_TIMEOUT,
        ) as client:
            resp = await client.head(mcp_url)
            if resp.status_code < 500:
                return True, f"status={resp.status_code}"
            return False, f"status={resp.status_code}"
    except Exception as exc:
        return False, str(exc)


def _check_thread_store() -> tuple[bool, str]:
    """Check thread store availability.

    For the current in-memory implementation this always succeeds.
    When a persistent backend (Redis / Cosmos DB) is added, this
    should perform a real connectivity check.

    Returns:
        tuple[bool, str]: ``(ok, detail)`` — True with thread count.
    """
    from thread_store import get_thread_count

    return True, f"in-memory, threads={get_thread_count()}"


def register_health_endpoints(app: "FastAPI") -> None:
    """Register ``/health`` and ``/ready`` endpoints on *app*.

    Parameters:
        app: The FastAPI application instance.
    """
    from fastapi.responses import JSONResponse

    @app.get(
        "/health",
        summary="Liveness probe",
        description=(
            "Returns 200 if the process is alive. Suitable for "
            "Kubernetes / Azure Container Apps liveness probes."
        ),
        tags=["ops"],
    )
    async def health() -> JSONResponse:
        """Liveness probe — returns 200 if the server process is running."""
        return JSONResponse(
            status_code=200,
            content={"status": "alive"},
        )

    @app.get(
        "/ready",
        summary="Readiness probe",
        description=(
            "Returns 200 only when all dependencies (LLM endpoint, "
            "MCP server, thread store) are reachable. Returns 503 "
            "with details when any dependency is unavailable."
        ),
        tags=["ops"],
    )
    async def ready() -> JSONResponse:
        """Readiness probe — checks LLM, MCP, and thread store."""
        llm_ok, llm_detail = await _check_llm_endpoint()
        mcp_ok, mcp_detail = await _check_mcp_server()
        ts_ok, ts_detail = _check_thread_store()

        checks = {
            "llm_endpoint": {"ok": llm_ok, "detail": llm_detail},
            "mcp_server": {"ok": mcp_ok, "detail": mcp_detail},
            "thread_store": {"ok": ts_ok, "detail": ts_detail},
        }

        all_ok = llm_ok and mcp_ok and ts_ok
        status_code = 200 if all_ok else 503

        return JSONResponse(
            status_code=status_code,
            content={
                "status": "ready" if all_ok else "not_ready",
                "checks": checks,
            },
        )
