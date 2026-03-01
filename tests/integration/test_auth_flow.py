"""Integration tests for the authentication flow.

Covers: register -> login -> get me -> refresh token.
"""

import uuid

import httpx
import pytest

pytestmark = pytest.mark.asyncio(loop_scope="session")


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


async def test_register_new_user(async_client: httpx.AsyncClient):
    """POST /api/auth/register should create a new user and return 201."""
    email = f"register+{uuid.uuid4().hex[:8]}@test.local"
    payload = {
        "email": email,
        "password": "SecurePass123!",
        "full_name": "Register Test",
    }
    resp = await async_client.post("/api/auth/register", json=payload)
    assert resp.status_code == 201

    data = resp.json()
    assert data["email"] == email
    assert data["full_name"] == "Register Test"
    assert data["role"] == "agent"
    assert data["is_active"] is True
    assert "id" in data
    assert "created_at" in data


async def test_register_duplicate_email(
    async_client: httpx.AsyncClient, test_user: dict
):
    """POST /api/auth/register with an already-registered email should return 409."""
    payload = {
        "email": test_user["email"],
        "password": "AnyPassword1!",
        "full_name": "Duplicate",
    }
    resp = await async_client.post("/api/auth/register", json=payload)
    assert resp.status_code == 409


async def test_register_missing_fields(async_client: httpx.AsyncClient):
    """POST /api/auth/register with missing required fields should return 422."""
    resp = await async_client.post("/api/auth/register", json={"email": "bad@test.local"})
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------


async def test_login_valid_credentials(
    async_client: httpx.AsyncClient, test_user: dict
):
    """POST /api/auth/login with valid credentials should return tokens."""
    payload = {
        "email": test_user["email"],
        "password": test_user["password"],
    }
    resp = await async_client.post("/api/auth/login", json=payload)
    assert resp.status_code == 200

    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


async def test_login_invalid_password(
    async_client: httpx.AsyncClient, test_user: dict
):
    """POST /api/auth/login with wrong password should return 401."""
    payload = {
        "email": test_user["email"],
        "password": "WrongPassword!",
    }
    resp = await async_client.post("/api/auth/login", json=payload)
    assert resp.status_code == 401


async def test_login_nonexistent_user(async_client: httpx.AsyncClient):
    """POST /api/auth/login with a non-existent email should return 401."""
    payload = {
        "email": "nonexistent@test.local",
        "password": "AnyPassword1!",
    }
    resp = await async_client.post("/api/auth/login", json=payload)
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Get current user (GET /api/auth/me)
# ---------------------------------------------------------------------------


async def test_get_me_authenticated(
    async_client: httpx.AsyncClient, test_user: dict, auth_headers: dict
):
    """GET /api/auth/me with a valid token should return the current user."""
    resp = await async_client.get("/api/auth/me", headers=auth_headers)
    assert resp.status_code == 200

    data = resp.json()
    assert data["email"] == test_user["email"]
    assert data["full_name"] == test_user["full_name"]
    assert data["id"] == test_user["id"]


async def test_get_me_unauthenticated(async_client: httpx.AsyncClient):
    """GET /api/auth/me without a token should return 401 or 403."""
    resp = await async_client.get("/api/auth/me")
    assert resp.status_code in (401, 403)


async def test_get_me_invalid_token(async_client: httpx.AsyncClient):
    """GET /api/auth/me with a garbage token should return 401 or 403."""
    headers = {"Authorization": "Bearer invalid.token.here"}
    resp = await async_client.get("/api/auth/me", headers=headers)
    assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# Token refresh
# ---------------------------------------------------------------------------


async def test_refresh_token_valid(
    async_client: httpx.AsyncClient, auth_tokens: dict
):
    """POST /api/auth/refresh with a valid refresh token should return new tokens."""
    payload = {"refresh_token": auth_tokens["refresh_token"]}
    resp = await async_client.post("/api/auth/refresh", json=payload)
    assert resp.status_code == 200

    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"
    # New tokens should be different from the originals
    assert data["access_token"] != auth_tokens["access_token"]


async def test_refresh_token_invalid(async_client: httpx.AsyncClient):
    """POST /api/auth/refresh with an invalid token should return 401."""
    payload = {"refresh_token": "invalid.refresh.token"}
    resp = await async_client.post("/api/auth/refresh", json=payload)
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Full flow (end-to-end)
# ---------------------------------------------------------------------------


async def test_full_auth_flow(async_client: httpx.AsyncClient):
    """Register -> Login -> Get Me -> Refresh: full auth lifecycle."""
    email = f"fullflow+{uuid.uuid4().hex[:8]}@test.local"
    password = "FlowTest123!"

    # 1. Register
    resp = await async_client.post(
        "/api/auth/register",
        json={"email": email, "password": password, "full_name": "Flow Test"},
    )
    assert resp.status_code == 201
    user_id = resp.json()["id"]

    # 2. Login
    resp = await async_client.post(
        "/api/auth/login",
        json={"email": email, "password": password},
    )
    assert resp.status_code == 200
    tokens = resp.json()

    # 3. Get me
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    resp = await async_client.get("/api/auth/me", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == user_id
    assert resp.json()["email"] == email

    # 4. Refresh
    resp = await async_client.post(
        "/api/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert resp.status_code == 200
    new_tokens = resp.json()
    assert "access_token" in new_tokens

    # 5. Verify refreshed token works
    headers = {"Authorization": f"Bearer {new_tokens['access_token']}"}
    resp = await async_client.get("/api/auth/me", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == user_id
