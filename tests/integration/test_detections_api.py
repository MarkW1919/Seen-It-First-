"""Integration tests for the detections API.

Covers: create detection, list detections, search by plate.
"""

import httpx
import pytest

pytestmark = pytest.mark.asyncio(loop_scope="session")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SAMPLE_DETECTION = {
    "vehicle_type": "sedan",
    "vehicle_color": "blue",
    "vehicle_make": "Toyota",
    "vehicle_model": "Camry",
    "vehicle_year": 2021,
    "vehicle_confidence": 0.95,
    "latitude": 33.749,
    "longitude": -84.388,
    "address": "123 Integration Test Blvd",
    "image_path": "/images/test_detection.jpg",
    "plate_reads": [
        {
            "plate_text": "INTG1234",
            "plate_state": "GA",
            "confidence": 0.98,
        }
    ],
}


# ---------------------------------------------------------------------------
# Create detection
# ---------------------------------------------------------------------------


async def test_create_detection(
    async_client: httpx.AsyncClient, auth_headers: dict
):
    """POST /api/detections/ should create a detection and return 201."""
    resp = await async_client.post(
        "/api/detections/", json=_SAMPLE_DETECTION, headers=auth_headers
    )
    assert resp.status_code == 201

    data = resp.json()
    assert "id" in data
    assert data["vehicle_make"] == "Toyota"
    assert data["vehicle_model"] == "Camry"
    assert data["vehicle_color"] == "blue"
    assert data["vehicle_year"] == 2021
    assert data["latitude"] == pytest.approx(33.749)
    assert data["longitude"] == pytest.approx(-84.388)
    assert "created_at" in data


async def test_create_detection_with_plate_reads(
    async_client: httpx.AsyncClient, auth_headers: dict
):
    """Created detection should include the plate reads."""
    resp = await async_client.post(
        "/api/detections/", json=_SAMPLE_DETECTION, headers=auth_headers
    )
    assert resp.status_code == 201

    data = resp.json()
    assert len(data["plate_reads"]) >= 1
    plate = data["plate_reads"][0]
    assert plate["plate_text"] == "INTG1234"
    assert plate["plate_state"] == "GA"
    assert plate["confidence"] == pytest.approx(0.98)


async def test_create_detection_unauthenticated(async_client: httpx.AsyncClient):
    """POST /api/detections/ without auth should return 401/403."""
    resp = await async_client.post("/api/detections/", json=_SAMPLE_DETECTION)
    assert resp.status_code in (401, 403)


async def test_create_detection_minimal_payload(
    async_client: httpx.AsyncClient, auth_headers: dict
):
    """POST /api/detections/ with minimal payload (no optional fields)."""
    payload = {
        "plate_reads": [
            {
                "plate_text": "MINIMAL1",
                "confidence": 0.80,
            }
        ],
    }
    resp = await async_client.post(
        "/api/detections/", json=payload, headers=auth_headers
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["plate_reads"][0]["plate_text"] == "MINIMAL1"


# ---------------------------------------------------------------------------
# List detections
# ---------------------------------------------------------------------------


async def test_list_detections(
    async_client: httpx.AsyncClient, auth_headers: dict
):
    """GET /api/detections/ should return a paginated list."""
    resp = await async_client.get("/api/detections/", headers=auth_headers)
    assert resp.status_code == 200

    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert "page" in data
    assert "page_size" in data
    assert isinstance(data["items"], list)
    assert data["total"] >= 0


async def test_list_detections_pagination(
    async_client: httpx.AsyncClient, auth_headers: dict
):
    """GET /api/detections/?page=1&page_size=2 should respect pagination params."""
    resp = await async_client.get(
        "/api/detections/", params={"page": 1, "page_size": 2}, headers=auth_headers
    )
    assert resp.status_code == 200

    data = resp.json()
    assert data["page"] == 1
    assert data["page_size"] == 2
    assert len(data["items"]) <= 2


async def test_list_detections_unauthenticated(async_client: httpx.AsyncClient):
    """GET /api/detections/ without auth should return 401/403."""
    resp = await async_client.get("/api/detections/")
    assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# Get detection by ID
# ---------------------------------------------------------------------------


async def test_get_detection_by_id(
    async_client: httpx.AsyncClient, auth_headers: dict
):
    """GET /api/detections/{id} should return the created detection."""
    # Create one first
    create_resp = await async_client.post(
        "/api/detections/", json=_SAMPLE_DETECTION, headers=auth_headers
    )
    assert create_resp.status_code == 201
    detection_id = create_resp.json()["id"]

    # Retrieve it
    resp = await async_client.get(
        f"/api/detections/{detection_id}", headers=auth_headers
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == detection_id


async def test_get_detection_not_found(
    async_client: httpx.AsyncClient, auth_headers: dict
):
    """GET /api/detections/{id} with a non-existent ID should return 404."""
    fake_id = "00000000-0000-0000-0000-000000000000"
    resp = await async_client.get(
        f"/api/detections/{fake_id}", headers=auth_headers
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Multiple plate reads
# ---------------------------------------------------------------------------


async def test_create_detection_multiple_plates(
    async_client: httpx.AsyncClient, auth_headers: dict
):
    """Detection with multiple plate reads should store all of them."""
    payload = {
        "vehicle_type": "truck",
        "vehicle_color": "white",
        "plate_reads": [
            {"plate_text": "MULTI001", "confidence": 0.95},
            {"plate_text": "MULTI002", "confidence": 0.88},
        ],
    }
    resp = await async_client.post(
        "/api/detections/", json=payload, headers=auth_headers
    )
    assert resp.status_code == 201
    plates = resp.json()["plate_reads"]
    plate_texts = {p["plate_text"] for p in plates}
    assert "MULTI001" in plate_texts
    assert "MULTI002" in plate_texts
