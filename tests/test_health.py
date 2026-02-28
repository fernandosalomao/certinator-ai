"""
Certinator AI — Health Check Endpoint Tests (G9)

Tests for the ``/health`` (liveness) and ``/ready`` (readiness) endpoints.

Covers:
    - /health returns 200 with ``{"status": "alive"}``
    - /ready returns 200 when all dependencies are healthy
    - /ready returns 503 when LLM endpoint is unreachable
    - /ready returns 503 when MCP server is unreachable
    - /ready returns 503 when thread store is unhealthy
    - /ready response includes per-check detail fields
    - _check_llm_endpoint handles missing LLM_ENDPOINT
    - _check_llm_endpoint handles local provider shortcut
    - _check_mcp_server handles network errors
    - _check_thread_store reports thread count
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

# Ensure ``src/`` is on the import path.
_SRC = str(Path(__file__).resolve().parent.parent / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from health import (
    _check_llm_endpoint,
    _check_mcp_server,
    _check_thread_store,
)
from thread_store import _thread_store

# ──────────────────────────────────────────────────────────────────────────
# Unit tests for individual check functions
# ──────────────────────────────────────────────────────────────────────────


class TestCheckLLMEndpoint:
    """Tests for ``_check_llm_endpoint``."""

    def test_local_provider_returns_ok(self) -> None:
        """FoundryLocal provider always returns ok (implicit liveness)."""
        with patch("config.LLM_PROVIDER", "local"):
            ok, detail = asyncio.run(_check_llm_endpoint())
        assert ok is True
        assert "local" in detail

    def test_missing_endpoint_returns_not_ok(self) -> None:
        """Missing LLM_ENDPOINT should report not ok."""
        with (
            patch("config.LLM_PROVIDER", "azure"),
            patch("config.LLM_ENDPOINT", ""),
        ):
            ok, detail = asyncio.run(_check_llm_endpoint())
        assert ok is False
        assert "not configured" in detail

    def test_reachable_endpoint_returns_ok(self) -> None:
        """A reachable endpoint returning 200 should be ok."""
        mock_response = AsyncMock()
        mock_response.status_code = 200

        mock_client = AsyncMock()
        mock_client.head = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("config.LLM_PROVIDER", "azure"),
            patch("config.LLM_ENDPOINT", "https://example.com"),
            patch("httpx.AsyncClient", return_value=mock_client),
        ):
            ok, detail = asyncio.run(_check_llm_endpoint())
        assert ok is True
        assert "200" in detail

    def test_server_error_returns_not_ok(self) -> None:
        """A 500 response from LLM endpoint should be not ok."""
        mock_response = AsyncMock()
        mock_response.status_code = 500

        mock_client = AsyncMock()
        mock_client.head = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("config.LLM_PROVIDER", "azure"),
            patch("config.LLM_ENDPOINT", "https://example.com"),
            patch("httpx.AsyncClient", return_value=mock_client),
        ):
            ok, detail = asyncio.run(_check_llm_endpoint())
        assert ok is False
        assert "500" in detail

    def test_network_error_returns_not_ok(self) -> None:
        """Network errors should be caught and reported."""
        mock_client = AsyncMock()
        mock_client.head = AsyncMock(
            side_effect=ConnectionError("Connection refused"),
        )
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("config.LLM_PROVIDER", "azure"),
            patch("config.LLM_ENDPOINT", "https://example.com"),
            patch("httpx.AsyncClient", return_value=mock_client),
        ):
            ok, detail = asyncio.run(_check_llm_endpoint())
        assert ok is False
        assert "Connection refused" in detail

    def test_github_provider_checks_endpoint(self) -> None:
        """GitHub provider should check its endpoint like Azure."""
        mock_response = AsyncMock()
        mock_response.status_code = 200

        mock_client = AsyncMock()
        mock_client.head = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("config.LLM_PROVIDER", "github"),
            patch(
                "config.LLM_ENDPOINT",
                "https://models.github.ai/inference",
            ),
            patch("httpx.AsyncClient", return_value=mock_client),
        ):
            ok, detail = asyncio.run(_check_llm_endpoint())
        assert ok is True


class TestCheckMCPServer:
    """Tests for ``_check_mcp_server``."""

    def test_reachable_mcp_returns_ok(self) -> None:
        """Reachable MCP server should return ok."""
        mock_response = AsyncMock()
        mock_response.status_code = 200

        mock_client = AsyncMock()
        mock_client.head = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            ok, detail = asyncio.run(_check_mcp_server())
        assert ok is True
        assert "200" in detail

    def test_server_error_returns_not_ok(self) -> None:
        """MCP server 500 should return not ok."""
        mock_response = AsyncMock()
        mock_response.status_code = 503

        mock_client = AsyncMock()
        mock_client.head = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            ok, detail = asyncio.run(_check_mcp_server())
        assert ok is False
        assert "503" in detail

    def test_timeout_returns_not_ok(self) -> None:
        """MCP server timeout should return not ok."""
        mock_client = AsyncMock()
        mock_client.head = AsyncMock(
            side_effect=TimeoutError("Request timed out"),
        )
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            ok, detail = asyncio.run(_check_mcp_server())
        assert ok is False
        assert "timed out" in detail.lower()


class TestCheckThreadStore:
    """Tests for ``_check_thread_store``."""

    def test_returns_ok_with_thread_count(self) -> None:
        """In-memory store always returns ok with thread count."""
        ok, detail = _check_thread_store()
        assert ok is True
        assert "in-memory" in detail
        assert "threads=" in detail

    def test_reports_correct_count(self) -> None:
        """Thread count in detail matches actual store size."""
        initial_count = len(_thread_store)
        ok, detail = _check_thread_store()
        assert f"threads={initial_count}" in detail


# ──────────────────────────────────────────────────────────────────────────
# Integration tests for /health and /ready endpoints (FastAPI TestClient)
# ──────────────────────────────────────────────────────────────────────────


class TestHealthEndpoint:
    """Tests for the ``/health`` liveness probe endpoint."""

    def _make_app(self):
        """Create a minimal FastAPI app with health endpoints."""
        from fastapi import FastAPI

        from health import register_health_endpoints

        app = FastAPI()
        register_health_endpoints(app)
        return app

    def test_health_returns_200(self) -> None:
        """GET /health should return 200 with status=alive."""
        from starlette.testclient import TestClient

        client = TestClient(self._make_app())
        resp = client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "alive"


class TestReadyEndpoint:
    """Tests for the ``/ready`` readiness probe endpoint."""

    def _make_app(self):
        """Create a minimal FastAPI app with health endpoints."""
        from fastapi import FastAPI

        from health import register_health_endpoints

        app = FastAPI()
        register_health_endpoints(app)
        return app

    def test_ready_all_ok(self) -> None:
        """When all checks pass, /ready returns 200."""
        from starlette.testclient import TestClient

        with (
            patch(
                "health._check_llm_endpoint",
                return_value=(True, "status=200"),
            ),
            patch(
                "health._check_mcp_server",
                return_value=(True, "status=200"),
            ),
            patch(
                "health._check_thread_store",
                return_value=(True, "in-memory, threads=0"),
            ),
        ):
            client = TestClient(self._make_app())
            resp = client.get("/ready")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ready"
        assert body["checks"]["llm_endpoint"]["ok"] is True
        assert body["checks"]["mcp_server"]["ok"] is True
        assert body["checks"]["thread_store"]["ok"] is True

    def test_ready_llm_down_returns_503(self) -> None:
        """When LLM endpoint is down, /ready returns 503."""
        from starlette.testclient import TestClient

        with (
            patch(
                "health._check_llm_endpoint",
                return_value=(False, "Connection refused"),
            ),
            patch(
                "health._check_mcp_server",
                return_value=(True, "status=200"),
            ),
            patch(
                "health._check_thread_store",
                return_value=(True, "in-memory, threads=0"),
            ),
        ):
            client = TestClient(self._make_app())
            resp = client.get("/ready")
        assert resp.status_code == 503
        body = resp.json()
        assert body["status"] == "not_ready"
        assert body["checks"]["llm_endpoint"]["ok"] is False

    def test_ready_mcp_down_returns_503(self) -> None:
        """When MCP server is down, /ready returns 503."""
        from starlette.testclient import TestClient

        with (
            patch(
                "health._check_llm_endpoint",
                return_value=(True, "status=200"),
            ),
            patch(
                "health._check_mcp_server",
                return_value=(False, "status=503"),
            ),
            patch(
                "health._check_thread_store",
                return_value=(True, "in-memory, threads=0"),
            ),
        ):
            client = TestClient(self._make_app())
            resp = client.get("/ready")
        assert resp.status_code == 503
        body = resp.json()
        assert body["status"] == "not_ready"
        assert body["checks"]["mcp_server"]["ok"] is False

    def test_ready_multiple_failures(self) -> None:
        """When multiple checks fail, /ready returns 503 with all details."""
        from starlette.testclient import TestClient

        with (
            patch(
                "health._check_llm_endpoint",
                return_value=(False, "timeout"),
            ),
            patch(
                "health._check_mcp_server",
                return_value=(False, "DNS failure"),
            ),
            patch(
                "health._check_thread_store",
                return_value=(True, "in-memory, threads=0"),
            ),
        ):
            client = TestClient(self._make_app())
            resp = client.get("/ready")
        assert resp.status_code == 503
        body = resp.json()
        assert body["status"] == "not_ready"
        assert body["checks"]["llm_endpoint"]["ok"] is False
        assert body["checks"]["mcp_server"]["ok"] is False
        assert body["checks"]["thread_store"]["ok"] is True

    def test_ready_response_has_detail_fields(self) -> None:
        """Each check in /ready should have both ``ok`` and ``detail``."""
        from starlette.testclient import TestClient

        with (
            patch(
                "health._check_llm_endpoint",
                return_value=(True, "status=200"),
            ),
            patch(
                "health._check_mcp_server",
                return_value=(True, "status=200"),
            ),
            patch(
                "health._check_thread_store",
                return_value=(True, "in-memory, threads=0"),
            ),
        ):
            client = TestClient(self._make_app())
            resp = client.get("/ready")
        body = resp.json()
        for check_name in ("llm_endpoint", "mcp_server", "thread_store"):
            assert "ok" in body["checks"][check_name]
            assert "detail" in body["checks"][check_name]
