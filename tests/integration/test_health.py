"""Integration tests for health and root endpoints.

These endpoints are unauthenticated and should always be available
when the backend is running.
"""

import httpx
import pytest

pytestmark = pytest.mark.asyncio(loop_scope="session")


# ---------------------------------------------------------------------------
# /health
# ---------------------------------------------------------------------------


async def test_health_endpoint_returns_200(async_client: httpx.AsyncClient):
    """GET /health should return 200 with a healthy status."""
    resp = await async_client.get("/health")
    assert resp.status_code == 200


async def test_health_endpoint_body(async_client: httpx.AsyncClient):
    """GET /health response body should contain status and service fields."""
    resp = await async_client.get("/health")
    data = resp.json()
    assert data["status"] == "healthy"
    assert "service" in data


# ---------------------------------------------------------------------------
# / (root)
# ---------------------------------------------------------------------------


async def test_root_endpoint_returns_200(async_client: httpx.AsyncClient):
    """GET / should return 200."""
    resp = await async_client.get("/")
    assert resp.status_code == 200


async def test_root_endpoint_body(async_client: httpx.AsyncClient):
    """GET / response body should identify the service and version."""
    resp = await async_client.get("/")
    data = resp.json()
    assert data["service"] == "RepoScan Pro"
    assert "version" in data


# ---------------------------------------------------------------------------
# /docs (OpenAPI — available in DEBUG mode)
# ---------------------------------------------------------------------------


async def test_openapi_docs_available(async_client: httpx.AsyncClient):
    """GET /docs should return 200 in the test environment (DEBUG=true)."""
    resp = await async_client.get("/docs")
    assert resp.status_code == 200


async def test_openapi_json_available(async_client: httpx.AsyncClient):
    """GET /openapi.json should return valid OpenAPI spec."""
    resp = await async_client.get("/openapi.json")
    assert resp.status_code == 200
    data = resp.json()
    assert "openapi" in data
    assert "paths" in data
