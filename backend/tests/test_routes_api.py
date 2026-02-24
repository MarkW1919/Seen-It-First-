"""Tests for route API schemas and helper logic — no DB required."""
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

from app.routers.routes import (
    StopCreate,
    RouteCreate,
    StopResponse,
    RouteResponse,
    StopUpdate,
    _get_stop_by_index,
    _route_to_response,
)

import pytest
from fastapi import HTTPException


# ── Schema validation ────────────────────────────────────────────────────────


def test_stop_create_defaults():
    s = StopCreate(address="123 Main St", latitude=33.45, longitude=-112.07)
    assert s.geofence_radius_m == 50.0


def test_stop_create_custom_geofence():
    s = StopCreate(
        address="456 Oak Ave", latitude=34.0, longitude=-118.0,
        geofence_radius_m=100.0,
    )
    assert s.geofence_radius_m == 100.0


def test_stop_create_geofence_min_bound():
    with pytest.raises(Exception):
        StopCreate(
            address="789 Pine", latitude=33.0, longitude=-112.0,
            geofence_radius_m=5.0,  # below 10.0 minimum
        )


def test_stop_create_geofence_max_bound():
    with pytest.raises(Exception):
        StopCreate(
            address="789 Pine", latitude=33.0, longitude=-112.0,
            geofence_radius_m=600.0,  # above 500.0 maximum
        )


def test_route_create_requires_at_least_one_stop():
    with pytest.raises(Exception):
        RouteCreate(name="Empty", stops=[])


def test_route_create_with_stops():
    rc = RouteCreate(
        name="Test Route",
        stops=[
            StopCreate(address="A", latitude=33.0, longitude=-112.0),
            StopCreate(address="B", latitude=34.0, longitude=-113.0),
        ],
    )
    assert rc.name == "Test Route"
    assert len(rc.stops) == 2


def test_route_create_name_optional():
    rc = RouteCreate(
        stops=[StopCreate(address="A", latitude=33.0, longitude=-112.0)]
    )
    assert rc.name is None


def test_stop_update_fields():
    su = StopUpdate(notes="Some notes", plates_found=3)
    assert su.notes == "Some notes"
    assert su.plates_found == 3


def test_stop_update_empty():
    su = StopUpdate()
    assert su.notes is None
    assert su.plates_found is None


# ── StopResponse ─────────────────────────────────────────────────────────────


def test_stop_response_defaults():
    sr = StopResponse(
        id=str(uuid.uuid4()),
        order_index=0,
        address="123 Main",
        latitude=33.45,
        longitude=-112.07,
        geofence_radius_m=50.0,
        status="pending",
    )
    assert sr.plates_found == 0
    assert sr.arrived_at is None
    assert sr.notes is None


# ── RouteResponse ────────────────────────────────────────────────────────────


def test_route_response_structure():
    rr = RouteResponse(
        id=str(uuid.uuid4()),
        name="Test",
        status="active",
        current_stop_index=0,
        total_stops=3,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    assert rr.status == "active"
    assert rr.stops == []


def test_route_response_with_stops():
    stops = [
        StopResponse(
            id=str(uuid.uuid4()),
            order_index=i,
            address=f"Stop {i}",
            latitude=33.0 + i * 0.01,
            longitude=-112.0 + i * 0.01,
            geofence_radius_m=50.0,
            status="pending",
        )
        for i in range(3)
    ]
    rr = RouteResponse(
        id=str(uuid.uuid4()),
        name="Multi-stop",
        status="active",
        current_stop_index=0,
        total_stops=3,
        created_at=datetime.now(timezone.utc).isoformat(),
        stops=stops,
    )
    assert len(rr.stops) == 3
    assert rr.stops[1].address == "Stop 1"


# ── Helper: mock Route/RouteStop using SimpleNamespace ───────────────────────


def _make_stop(route_id, order_index, status="pending"):
    """Create a stop-like object that mimics RouteStop ORM."""
    return SimpleNamespace(
        id=uuid.uuid4(),
        route_id=route_id,
        order_index=order_index,
        address=f"Address {order_index}",
        latitude=33.0 + order_index * 0.01,
        longitude=-112.0 + order_index * 0.01,
        geofence_radius_m=50.0,
        status=status,
        arrived_at=None,
        scan_started_at=None,
        completed_at=None,
        plates_found=0,
        notes=None,
    )


def _make_route(num_stops):
    """Create a route-like object that mimics Route ORM."""
    route_id = uuid.uuid4()
    route = SimpleNamespace(
        id=route_id,
        agent_id=uuid.uuid4(),
        name="Test Route",
        status="active",
        current_stop_index=0,
        total_stops=num_stops,
        created_at=datetime.now(timezone.utc),
        completed_at=None,
        stops=[_make_stop(route_id, i) for i in range(num_stops)],
    )
    return route


# ── Helper: _get_stop_by_index ───────────────────────────────────────────────


def test_get_stop_by_index_found():
    route = _make_route(3)
    stop = _get_stop_by_index(route, 1)
    assert stop.order_index == 1
    assert stop.address == "Address 1"


def test_get_stop_by_index_not_found():
    route = _make_route(3)
    with pytest.raises(HTTPException) as exc_info:
        _get_stop_by_index(route, 99)
    assert exc_info.value.status_code == 404


# ── Helper: _route_to_response ───────────────────────────────────────────────


def test_route_to_response_conversion():
    route = _make_route(2)
    resp = _route_to_response(route)
    assert resp.id == str(route.id)
    assert resp.total_stops == 2
    assert len(resp.stops) == 2
    assert resp.stops[0].order_index == 0
    assert resp.stops[1].address == "Address 1"


def test_route_to_response_completed_route():
    route = _make_route(1)
    route.status = "completed"
    route.completed_at = datetime.now(timezone.utc)
    resp = _route_to_response(route)
    assert resp.status == "completed"
    assert resp.completed_at is not None


def test_route_to_response_stop_timestamps():
    route = _make_route(1)
    now = datetime.now(timezone.utc)
    route.stops[0].status = "completed"
    route.stops[0].arrived_at = now
    route.stops[0].scan_started_at = now
    route.stops[0].completed_at = now
    route.stops[0].plates_found = 5

    resp = _route_to_response(route)
    assert resp.stops[0].status == "completed"
    assert resp.stops[0].plates_found == 5
    assert resp.stops[0].arrived_at is not None
