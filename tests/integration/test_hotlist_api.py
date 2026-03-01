"""Integration tests for the hot list API.

Covers: create entry, list entries, update entry, delete entry.
"""

import httpx
import pytest

pytestmark = pytest.mark.asyncio(loop_scope="session")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SAMPLE_ENTRY = {
    "plate_text": "HOT12345",
    "plate_state": "FL",
    "case_number": "CASE-INT-001",
    "lender_name": "Integration Bank",
    "lender_contact": "555-0100",
    "order_type": "repossession",
    "vehicle_year": 2020,
    "vehicle_make": "Honda",
    "vehicle_model": "Civic",
    "vehicle_color": "red",
    "vin": "1HGBH41JXMN109186",
    "debtor_name": "Test Debtor",
    "debtor_address": "456 Test Ave",
    "priority": "high",
    "notes": "Integration test entry",
}


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


async def test_create_hotlist_entry(
    async_client: httpx.AsyncClient, auth_headers: dict
):
    """POST /api/hotlist/entries should create an entry and return 201."""
    resp = await async_client.post(
        "/api/hotlist/entries", json=_SAMPLE_ENTRY, headers=auth_headers
    )
    assert resp.status_code == 201

    data = resp.json()
    assert "id" in data
    assert data["plate_text"] == "HOT12345"
    assert data["plate_state"] == "FL"
    assert data["case_number"] == "CASE-INT-001"
    assert data["lender_name"] == "Integration Bank"
    assert data["vehicle_make"] == "Honda"
    assert data["priority"] == "high"
    assert data["is_active"] is True
    assert "created_at" in data
    assert "updated_at" in data


async def test_create_hotlist_entry_minimal(
    async_client: httpx.AsyncClient, auth_headers: dict
):
    """POST /api/hotlist/entries with only required fields."""
    payload = {"plate_text": "MIN00001"}
    resp = await async_client.post(
        "/api/hotlist/entries", json=payload, headers=auth_headers
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["plate_text"] == "MIN00001"
    assert data["order_type"] == "repossession"  # default
    assert data["priority"] == "normal"  # default


async def test_create_hotlist_entry_unauthenticated(
    async_client: httpx.AsyncClient,
):
    """POST /api/hotlist/entries without auth should return 401/403."""
    resp = await async_client.post("/api/hotlist/entries", json=_SAMPLE_ENTRY)
    assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------


async def test_list_hotlist_entries(
    async_client: httpx.AsyncClient, auth_headers: dict
):
    """GET /api/hotlist/entries should return a list of entries."""
    resp = await async_client.get("/api/hotlist/entries", headers=auth_headers)
    assert resp.status_code == 200

    data = resp.json()
    assert isinstance(data, list)
    # We created at least one entry above
    assert len(data) >= 1


async def test_list_hotlist_entries_pagination(
    async_client: httpx.AsyncClient, auth_headers: dict
):
    """GET /api/hotlist/entries with pagination params should be respected."""
    resp = await async_client.get(
        "/api/hotlist/entries",
        params={"page": 1, "page_size": 1},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) <= 1


async def test_list_hotlist_entries_unauthenticated(
    async_client: httpx.AsyncClient,
):
    """GET /api/hotlist/entries without auth should return 401/403."""
    resp = await async_client.get("/api/hotlist/entries")
    assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# Get by ID
# ---------------------------------------------------------------------------


async def test_get_hotlist_entry_by_id(
    async_client: httpx.AsyncClient, auth_headers: dict
):
    """GET /api/hotlist/entries/{id} should return the entry."""
    # Create
    create_resp = await async_client.post(
        "/api/hotlist/entries",
        json={"plate_text": "GETBYID1", "priority": "normal"},
        headers=auth_headers,
    )
    assert create_resp.status_code == 201
    entry_id = create_resp.json()["id"]

    # Retrieve
    resp = await async_client.get(
        f"/api/hotlist/entries/{entry_id}", headers=auth_headers
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == entry_id
    assert resp.json()["plate_text"] == "GETBYID1"


async def test_get_hotlist_entry_not_found(
    async_client: httpx.AsyncClient, auth_headers: dict
):
    """GET /api/hotlist/entries/{id} with non-existent ID should return 404."""
    fake_id = "00000000-0000-0000-0000-000000000000"
    resp = await async_client.get(
        f"/api/hotlist/entries/{fake_id}", headers=auth_headers
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Update (PATCH)
# ---------------------------------------------------------------------------


async def test_update_hotlist_entry(
    async_client: httpx.AsyncClient, auth_headers: dict
):
    """PATCH /api/hotlist/entries/{id} should update fields."""
    # Create
    create_resp = await async_client.post(
        "/api/hotlist/entries",
        json={"plate_text": "UPD00001", "priority": "normal", "notes": "original"},
        headers=auth_headers,
    )
    assert create_resp.status_code == 201
    entry_id = create_resp.json()["id"]

    # Update
    update_payload = {
        "priority": "high",
        "notes": "updated via integration test",
        "vehicle_color": "green",
    }
    resp = await async_client.patch(
        f"/api/hotlist/entries/{entry_id}",
        json=update_payload,
        headers=auth_headers,
    )
    assert resp.status_code == 200

    data = resp.json()
    assert data["priority"] == "high"
    assert data["notes"] == "updated via integration test"
    assert data["vehicle_color"] == "green"
    # Unchanged fields should remain
    assert data["plate_text"] == "UPD00001"


async def test_update_hotlist_entry_deactivate(
    async_client: httpx.AsyncClient, auth_headers: dict
):
    """PATCH can deactivate an entry by setting is_active=false."""
    # Create
    create_resp = await async_client.post(
        "/api/hotlist/entries",
        json={"plate_text": "DEACT001"},
        headers=auth_headers,
    )
    assert create_resp.status_code == 201
    entry_id = create_resp.json()["id"]

    # Deactivate
    resp = await async_client.patch(
        f"/api/hotlist/entries/{entry_id}",
        json={"is_active": False},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False


async def test_update_hotlist_entry_not_found(
    async_client: httpx.AsyncClient, auth_headers: dict
):
    """PATCH with a non-existent ID should return 404."""
    fake_id = "00000000-0000-0000-0000-000000000000"
    resp = await async_client.patch(
        f"/api/hotlist/entries/{fake_id}",
        json={"notes": "no such entry"},
        headers=auth_headers,
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------


async def test_delete_hotlist_entry(
    async_client: httpx.AsyncClient, auth_headers: dict
):
    """DELETE /api/hotlist/entries/{id} should return 204."""
    # Create
    create_resp = await async_client.post(
        "/api/hotlist/entries",
        json={"plate_text": "DEL00001"},
        headers=auth_headers,
    )
    assert create_resp.status_code == 201
    entry_id = create_resp.json()["id"]

    # Delete
    resp = await async_client.delete(
        f"/api/hotlist/entries/{entry_id}", headers=auth_headers
    )
    assert resp.status_code == 204

    # Verify it is gone
    get_resp = await async_client.get(
        f"/api/hotlist/entries/{entry_id}", headers=auth_headers
    )
    assert get_resp.status_code == 404


async def test_delete_hotlist_entry_not_found(
    async_client: httpx.AsyncClient, auth_headers: dict
):
    """DELETE with a non-existent ID should return 404."""
    fake_id = "00000000-0000-0000-0000-000000000000"
    resp = await async_client.delete(
        f"/api/hotlist/entries/{fake_id}", headers=auth_headers
    )
    assert resp.status_code == 404


async def test_delete_hotlist_entry_unauthenticated(
    async_client: httpx.AsyncClient,
):
    """DELETE without auth should return 401/403."""
    fake_id = "00000000-0000-0000-0000-000000000000"
    resp = await async_client.delete(f"/api/hotlist/entries/{fake_id}")
    assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# Full CRUD flow
# ---------------------------------------------------------------------------


async def test_hotlist_full_crud_flow(
    async_client: httpx.AsyncClient, auth_headers: dict
):
    """Create -> Read -> Update -> Delete: full lifecycle."""
    # Create
    resp = await async_client.post(
        "/api/hotlist/entries",
        json={
            "plate_text": "CRUD0001",
            "lender_name": "CRUD Bank",
            "priority": "normal",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201
    entry_id = resp.json()["id"]

    # Read
    resp = await async_client.get(
        f"/api/hotlist/entries/{entry_id}", headers=auth_headers
    )
    assert resp.status_code == 200
    assert resp.json()["plate_text"] == "CRUD0001"

    # Update
    resp = await async_client.patch(
        f"/api/hotlist/entries/{entry_id}",
        json={"priority": "high", "notes": "escalated"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["priority"] == "high"
    assert resp.json()["notes"] == "escalated"

    # Delete
    resp = await async_client.delete(
        f"/api/hotlist/entries/{entry_id}", headers=auth_headers
    )
    assert resp.status_code == 204

    # Verify deleted
    resp = await async_client.get(
        f"/api/hotlist/entries/{entry_id}", headers=auth_headers
    )
    assert resp.status_code == 404
