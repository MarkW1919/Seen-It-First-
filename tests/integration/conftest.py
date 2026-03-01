"""Shared fixtures for integration tests.

These tests are designed to run against the docker-compose.test.yml stack
with the backend available at http://localhost:8000.
"""

import uuid

import httpx
import pytest
import pytest_asyncio

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_URL = "http://localhost:8000"

# Default test user credentials — each test session creates a unique user to
# avoid cross-test interference when the stack is reused.
_TEST_EMAIL_PREFIX = "integration"
_TEST_PASSWORD = "TestPass123!Secure"
_TEST_FULL_NAME = "Integration Test User"


def _unique_email() -> str:
    """Generate a unique email for this test session."""
    short_id = uuid.uuid4().hex[:8]
    return f"{_TEST_EMAIL_PREFIX}+{short_id}@test.local"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def base_url() -> str:
    """Return the base URL of the backend under test."""
    return BASE_URL


@pytest.fixture(scope="session")
def anyio_backend():
    """Force pytest-asyncio to use asyncio (not trio)."""
    return "asyncio"


@pytest_asyncio.fixture(scope="session")
async def async_client() -> httpx.AsyncClient:
    """Session-scoped async HTTP client pointed at the backend."""
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
        yield client


@pytest_asyncio.fixture(scope="session")
async def test_user(async_client: httpx.AsyncClient) -> dict:
    """Register a unique test user and return their credentials.

    Returns a dict with keys: email, password, full_name, id.
    """
    email = _unique_email()
    payload = {
        "email": email,
        "password": _TEST_PASSWORD,
        "full_name": _TEST_FULL_NAME,
    }
    resp = await async_client.post("/api/auth/register", json=payload)
    assert resp.status_code == 201, f"Failed to register test user: {resp.text}"
    data = resp.json()
    return {
        "email": email,
        "password": _TEST_PASSWORD,
        "full_name": _TEST_FULL_NAME,
        "id": data["id"],
    }


@pytest_asyncio.fixture(scope="session")
async def auth_tokens(async_client: httpx.AsyncClient, test_user: dict) -> dict:
    """Log in the test user and return access + refresh tokens.

    Returns a dict with keys: access_token, refresh_token.
    """
    payload = {
        "email": test_user["email"],
        "password": test_user["password"],
    }
    resp = await async_client.post("/api/auth/login", json=payload)
    assert resp.status_code == 200, f"Failed to login test user: {resp.text}"
    data = resp.json()
    return {
        "access_token": data["access_token"],
        "refresh_token": data["refresh_token"],
    }


@pytest_asyncio.fixture(scope="session")
async def auth_headers(auth_tokens: dict) -> dict:
    """Return Authorization headers for authenticated requests."""
    return {"Authorization": f"Bearer {auth_tokens['access_token']}"}
