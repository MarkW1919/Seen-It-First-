"""
Navigation API endpoints.

POST /navigation/geocode     — address string → lat/lon
POST /navigation/route       — two GPS points → route polyline + ETA
POST /navigation/start       — set destination, enter IDLE (en-route) mode
POST /navigation/stop        — clear destination, resume ACTIVE scanning
POST /navigation/gps         — receive GPS position from frontend
GET  /navigation/status      — current navigation state snapshot
"""

import logging

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from edge.navigation.geocoder import GeocoderError
from edge.navigation.router import RouterError
from edge.api.app import NavigationState

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/navigation", tags=["navigation"])


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class GeocodeRequest(BaseModel):
    address: str = Field(..., min_length=2, description="Street address or place name")

class GeocodeResponse(BaseModel):
    lat: float
    lon: float
    display_name: str


class RouteRequest(BaseModel):
    start_lat: float
    start_lon: float
    dest_lat: float
    dest_lon: float

class RouteResponse(BaseModel):
    polyline: list[list[float]]   # [[lat, lon], ...]
    distance_m: float
    duration_s: float
    eta_iso: str


_FT_TO_M = 0.3048
_RADIUS_FT_MIN = 1.0
_RADIUS_FT_MAX = 1320.0   # ¼ mile
_RADIUS_FT_DEFAULT = 300.0


class StartNavRequest(BaseModel):
    dest_lat: float
    dest_lon: float
    display_name: str = ""
    radius_ft: float = Field(
        default=_RADIUS_FT_DEFAULT,
        description="Arrival geofence radius in feet (1–1320 ft, ¼ mile max)",
    )

class GPSRequest(BaseModel):
    lat: float
    lon: float


# ---------------------------------------------------------------------------
# Dependency: pull NavigationState from app.state
# ---------------------------------------------------------------------------

def _nav(request: Request) -> NavigationState:
    return request.app.state.nav


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/geocode", response_model=GeocodeResponse)
def geocode(body: GeocodeRequest, request: Request):
    """Convert a human-readable address to GPS coordinates."""
    nav = _nav(request)
    try:
        result = nav.geocoder.geocode(body.address)
    except GeocoderError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return GeocodeResponse(
        lat=result.lat,
        lon=result.lon,
        display_name=result.display_name,
    )


@router.post("/route", response_model=RouteResponse)
def get_route(body: RouteRequest, request: Request):
    """Compute a driving route between two GPS points."""
    nav = _nav(request)
    try:
        result = nav.router.get_route(
            body.start_lat, body.start_lon,
            body.dest_lat,  body.dest_lon,
        )
    except RouterError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return RouteResponse(
        polyline=result.polyline,
        distance_m=result.distance_m,
        duration_s=result.duration_s,
        eta_iso=result.eta_iso,
    )


@router.post("/start")
def start_navigation(body: StartNavRequest, request: Request):
    """
    Activate navigation to a destination.

    - Validates radius_ft (1–1320 ft) and converts to metres.
    - Updates the arrival detector radius and geofence.
    - Switches the LPR pipeline to IDLE (no scanning while en route).
    - Stores destination in session state.
    """
    if not (_RADIUS_FT_MIN <= body.radius_ft <= _RADIUS_FT_MAX):
        raise HTTPException(
            status_code=400,
            detail=f"radius_ft must be between {_RADIUS_FT_MIN:.0f} and {_RADIUS_FT_MAX:.0f} ft",
        )

    radius_m = body.radius_ft * _FT_TO_M

    nav = _nav(request)
    nav.arrival_detector.set_radius(radius_m)
    nav.arrival_detector.set_destination(body.dest_lat, body.dest_lon)

    # Switch pipeline to IDLE — vehicle is driving, not scanning
    nav.scheduler.deactivate()

    nav.is_navigating = True
    nav.destination = {
        "lat": body.dest_lat,
        "lon": body.dest_lon,
        "display_name": body.display_name,
        "radius_ft": body.radius_ft,
        "radius_m": round(radius_m, 2),
    }

    logger.info(
        "Navigation started → (%.6f, %.6f) %s  radius=%.0fft (%.1fm)",
        body.dest_lat, body.dest_lon, body.display_name, body.radius_ft, radius_m,
    )
    return {"status": "navigating", "destination": nav.destination}


@router.post("/stop")
def stop_navigation(request: Request):
    """
    Cancel active navigation.

    - Clears the arrival detector.
    - Resumes the LPR pipeline (ACTIVE scanning).
    """
    nav = _nav(request)
    nav.arrival_detector.clear()
    nav.scheduler.activate()
    nav.is_navigating = False
    nav.destination = None
    nav.current_route = None

    logger.info("Navigation stopped — pipeline ACTIVE")
    return {"status": "stopped"}


@router.post("/gps")
async def update_gps(body: GPSRequest, request: Request):
    """
    Receive a GPS position update from the dashboard frontend.

    The frontend posts the operator's browser geolocation here.
    If the vehicle has entered the arrival geofence, this handler:
      1. Activates the LPR pipeline (IDLE → ACTIVE).
      2. Broadcasts an ARRIVED WebSocket event to all connected clients.
    """
    nav = _nav(request)
    nav.current_pos = {"lat": body.lat, "lon": body.lon}

    arrived = nav.arrival_detector.update_position(body.lat, body.lon)
    if arrived:
        # Switch pipeline from IDLE → ACTIVE
        nav.scheduler.activate()
        nav.is_navigating = False

        # Broadcast ARRIVED event to all dashboard clients
        await nav.ws_manager.broadcast({
            "event": "ARRIVED",
            "lat": body.lat,
            "lon": body.lon,
            "destination": nav.destination,
        })
        logger.info("ARRIVED event broadcast to %d WS client(s)", nav.ws_manager.client_count)

    return {
        "status": "ok",
        "arrived": arrived,
        "distance_m": nav.arrival_detector.last_distance_m,
    }


@router.get("/status")
def get_status(request: Request):
    """Return full navigation status snapshot."""
    nav = _nav(request)
    return {
        "navigating": nav.is_navigating,
        "destination": nav.destination,
        "current_pos": nav.current_pos,
        "pipeline_active": nav.scheduler.is_active,
        "arrival": nav.arrival_detector.status(),
        "ws_clients": nav.ws_manager.client_count,
    }
