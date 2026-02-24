"""Stress / concurrency tests — schema validation under load, route state machines."""
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.schemas.detection import DetectionCreate, PlateReadCreate
from app.schemas.hotlist import HotListEntryCreate, HotListEntryUpdate
from app.routers.routes import (
    StopCreate,
    RouteCreate,
    _route_to_response,
    _get_stop_by_index,
)


# ── Concurrent schema validation ────────────────────────────────────────────


def _create_detection(i: int) -> DetectionCreate:
    return DetectionCreate(
        vehicle_type="sedan",
        vehicle_confidence=0.8 + (i % 20) * 0.01,
        latitude=33.0 + i * 0.0001,
        longitude=-112.0 + i * 0.0001,
        plate_reads=[
            PlateReadCreate(
                plate_text=f"PLT{i:05d}",
                confidence=0.9,
            )
        ],
    )


def test_concurrent_detection_creation():
    """Validate 500 DetectionCreate schemas in parallel threads."""
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(_create_detection, i) for i in range(500)]
        results = [f.result() for f in futures]
    assert len(results) == 500
    assert all(r.vehicle_type == "sedan" for r in results)
    plates = {r.plate_reads[0].plate_text for r in results}
    assert len(plates) == 500


def test_concurrent_hotlist_entry_creation():
    """Validate 200 HotListEntryCreate schemas in parallel threads."""
    def _create_entry(i):
        return HotListEntryCreate(
            plate_text=f"HOT{i:05d}",
            case_number=f"CASE-{i}",
            priority="high" if i % 3 == 0 else "normal",
        )

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(_create_entry, i) for i in range(200)]
        results = [f.result() for f in futures]
    assert len(results) == 200
    high_priority = [r for r in results if r.priority == "high"]
    assert len(high_priority) == 67  # 0, 3, 6, ..., 198 → 67 items


# ── Route mock helpers (using SimpleNamespace to avoid ORM init) ─────────────


def _make_stop(route_id, order_index, status="pending"):
    return SimpleNamespace(
        id=uuid.uuid4(),
        route_id=route_id,
        order_index=order_index,
        address=f"Addr {order_index}",
        latitude=33.0 + order_index * 0.001,
        longitude=-112.0 + order_index * 0.001,
        geofence_radius_m=50.0,
        status=status,
        arrived_at=None,
        scan_started_at=None,
        completed_at=None,
        plates_found=0,
        notes=None,
    )


def _make_route_with_n_stops(n: int):
    route_id = uuid.uuid4()
    return SimpleNamespace(
        id=route_id,
        agent_id=uuid.uuid4(),
        name=f"Route-{n}",
        status="active",
        current_stop_index=0,
        total_stops=n,
        created_at=datetime.now(timezone.utc),
        completed_at=None,
        stops=[_make_stop(route_id, i) for i in range(n)],
    )


# ── Route state machine stress ───────────────────────────────────────────────


def test_large_route_serialization():
    """Serialize a 200-stop route to response without crashing."""
    route = _make_route_with_n_stops(200)
    resp = _route_to_response(route)
    assert resp.total_stops == 200
    assert len(resp.stops) == 200
    assert resp.stops[199].order_index == 199


def test_route_stop_lifecycle_all_completed():
    """Walk all stops through pending → arrived → scanning → completed."""
    route = _make_route_with_n_stops(50)
    now = datetime.now(timezone.utc)

    for i in range(50):
        stop = _get_stop_by_index(route, i)
        assert stop.status == "pending"

        stop.status = "arrived"
        stop.arrived_at = now
        assert stop.status == "arrived"

        stop.status = "scanning"
        stop.scan_started_at = now
        assert stop.status == "scanning"

        stop.status = "completed"
        stop.completed_at = now
        assert stop.status == "completed"

    all_done = all(s.status in ("completed", "skipped") for s in route.stops)
    assert all_done


def test_route_stop_lifecycle_mixed_skip_complete():
    """Mix of completed and skipped stops should all count as done."""
    route = _make_route_with_n_stops(20)
    now = datetime.now(timezone.utc)

    for i in range(20):
        stop = _get_stop_by_index(route, i)
        if i % 3 == 0:
            stop.status = "skipped"
        else:
            stop.status = "completed"
        stop.completed_at = now

    all_done = all(s.status in ("completed", "skipped") for s in route.stops)
    assert all_done
    skipped = sum(1 for s in route.stops if s.status == "skipped")
    assert skipped == 7  # 0, 3, 6, 9, 12, 15, 18


def test_concurrent_route_response_serialization():
    """Serialize 100 routes concurrently."""
    routes = [_make_route_with_n_stops(10) for _ in range(100)]

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(_route_to_response, r) for r in routes]
        results = [f.result() for f in futures]

    assert len(results) == 100
    assert all(r.total_stops == 10 for r in results)


# ── Schema edge cases under load ────────────────────────────────────────────


def test_detection_with_many_plate_reads():
    """A detection with 50 plate reads (multi-plate vehicle or OCR alternatives)."""
    plates = [
        PlateReadCreate(
            plate_text=f"MULTI{i:03d}",
            confidence=0.5 + (i % 50) * 0.01,
        )
        for i in range(50)
    ]
    dc = DetectionCreate(
        vehicle_type="truck",
        vehicle_confidence=0.85,
        plate_reads=plates,
    )
    assert len(dc.plate_reads) == 50


def test_hotlist_entry_update_all_fields_simultaneously():
    """Update all mutable fields at once — boundary test."""
    u = HotListEntryUpdate(
        plate_text="NEWPLATE",
        plate_state="NY",
        case_number="CASE-999",
        lender_name="New Lender",
        lender_contact="999-999-9999",
        order_type="voluntary",
        vehicle_year=2025,
        vehicle_make="Tesla",
        vehicle_model="Model Y",
        vehicle_color="Red",
        vin="5YJ3E1EA5MF000001",
        debtor_name="New Debtor",
        debtor_address="999 New St",
        debtor_phone="888-888-8888",
        is_active=False,
        priority="urgent",
        notes="Updated all fields",
        expires_at=datetime(2027, 1, 1, tzinfo=timezone.utc),
        extra={"batch": True},
    )
    dumped = u.model_dump(exclude_unset=True)
    assert len(dumped) == 19  # all fields set


def test_route_create_max_stops():
    """Create a route with 200 stops (max allowed)."""
    stops = [
        StopCreate(
            address=f"Address {i}",
            latitude=33.0 + i * 0.001,
            longitude=-112.0 + i * 0.001,
        )
        for i in range(200)
    ]
    rc = RouteCreate(name="Max Route", stops=stops)
    assert len(rc.stops) == 200
