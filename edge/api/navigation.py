"""
Navigation API endpoints.
"""

import json
import logging
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from edge.api.state import NavigationState
from edge.navigation.geocoder import GeocoderError
from edge.navigation.router import RouterError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/navigation", tags=["navigation"])

_FT_TO_M = 0.3048
_RADIUS_FT_MIN = 1.0
_RADIUS_FT_MAX = 1320.0
_RADIUS_FT_DEFAULT = 300.0

_LAT_MIN = -90.0
_LAT_MAX = 90.0
_LON_MIN = -180.0
_LON_MAX = 180.0
BASE_DIR = Path(__file__).resolve().parents[2]
OPERATOR_PROFILE_PATH = BASE_DIR / "data" / "operator_profile.json"

_OPERATOR_PROFILE_DEFAULTS = {
    "hotlist_refresh_sec": 60,
    "arrival_distance_ft": 300,
    "show_traffic_overlays": True,
    "ocr_confidence_threshold": 0.80,
    "max_tracked_vehicles": 10,
    "auto_checkin_on_arrival": True,
    "silent_shift_mode": False,
    "low_storage_warning": True,
}


class GeocodeRequest(BaseModel):
    address: str = Field(..., min_length=2, description="Street address or place name")


class GeocodeResponse(BaseModel):
    lat: float
    lon: float
    display_name: str


class RouteRequest(BaseModel):
    start_lat: float = Field(..., ge=_LAT_MIN, le=_LAT_MAX)
    start_lon: float = Field(..., ge=_LON_MIN, le=_LON_MAX)
    dest_lat: float = Field(..., ge=_LAT_MIN, le=_LAT_MAX)
    dest_lon: float = Field(..., ge=_LON_MIN, le=_LON_MAX)


class RouteResponse(BaseModel):
    polyline: list[list[float]]
    distance_m: float
    duration_s: float
    eta_iso: str


class StartNavRequest(BaseModel):
    dest_lat: float = Field(..., ge=_LAT_MIN, le=_LAT_MAX)
    dest_lon: float = Field(..., ge=_LON_MIN, le=_LON_MAX)
    display_name: str = ""
    radius_ft: float = Field(
        default=_RADIUS_FT_DEFAULT,
        ge=_RADIUS_FT_MIN,
        le=_RADIUS_FT_MAX,
        description="Arrival geofence radius in feet (1-1320 ft, 1/4 mile max)",
    )


class GPSRequest(BaseModel):
    lat: float = Field(..., ge=_LAT_MIN, le=_LAT_MAX)
    lon: float = Field(..., ge=_LON_MIN, le=_LON_MAX)


class DetectionSearchRequest(BaseModel):
    plate_text: str = ""
    vehicle_class: str = ""
    make: str = ""
    model: str = ""
    address: str = ""
    radius_m: float = Field(default=120.0, ge=1.0, le=5000.0)
    limit: int = Field(default=100, ge=1, le=500)


class DetectionSummary(BaseModel):
    id: int
    timestamp: float
    plate_text: str | None = None
    vehicle_class: str | None = None
    make: str | None = None
    model: str | None = None
    year_range: str | None = None
    confidence: float | None = None
    camera_id: str
    detection_address: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    snapshot_path: str | None = None
    plate_path: str | None = None
    vehicle_path: str | None = None
    composite_path: str | None = None
    distance_m: float | None = None


class DetectionSearchResponse(BaseModel):
    address: str = ""
    total: int
    detections: list[DetectionSummary]


class RuntimeCameraSummary(BaseModel):
    camera_id: str
    name: str
    status: str
    fps: float
    queue_depth: int
    last_frame_age_s: float | None = None


class RuntimeStatusResponse(BaseModel):
    pipeline_active: bool
    navigating: bool
    arrived: bool
    ws_clients: int
    operator_gps: dict[str, float] | None = None
    cameras: list[RuntimeCameraSummary]


class RecentEventsResponse(BaseModel):
    total: int
    events: list[dict[str, Any]]


class OperatorProfile(BaseModel):
    hotlist_refresh_sec: int = Field(default=60, ge=15, le=300)
    arrival_distance_ft: int = Field(default=300, ge=1, le=1320)
    show_traffic_overlays: bool = True
    ocr_confidence_threshold: float = Field(default=0.80, ge=0.50, le=0.99)
    max_tracked_vehicles: int = Field(default=10, ge=1, le=30)
    auto_checkin_on_arrival: bool = True
    silent_shift_mode: bool = False
    low_storage_warning: bool = True


def _nav(request: Request) -> NavigationState:
    return request.app.state.nav


def _load_operator_profile() -> OperatorProfile:
    if not OPERATOR_PROFILE_PATH.exists():
        return OperatorProfile(**_OPERATOR_PROFILE_DEFAULTS)

    try:
        raw = json.loads(OPERATOR_PROFILE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        logger.exception("Failed to load operator profile: %s", OPERATOR_PROFILE_PATH)
        return OperatorProfile(**_OPERATOR_PROFILE_DEFAULTS)

    merged = {**_OPERATOR_PROFILE_DEFAULTS, **raw}
    return OperatorProfile(**merged)


def _save_operator_profile(profile: OperatorProfile) -> OperatorProfile:
    OPERATOR_PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    OPERATOR_PROFILE_PATH.write_text(
        profile.model_dump_json(indent=2),
        encoding="utf-8",
    )
    return profile


@router.post("/geocode", response_model=GeocodeResponse)
def geocode(body: GeocodeRequest, request: Request):
    """Convert a human-readable address to GPS coordinates."""
    nav = _nav(request)
    address = body.address.strip()
    if len(address) < 2:
        raise HTTPException(
            status_code=422,
            detail="address must contain at least 2 non-space characters",
        )

    try:
        result = nav.geocoder.geocode(address)
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
            body.start_lat,
            body.start_lon,
            body.dest_lat,
            body.dest_lon,
        )
    except RouterError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    response = RouteResponse(
        polyline=result.polyline,
        distance_m=result.distance_m,
        duration_s=result.duration_s,
        eta_iso=result.eta_iso,
    )
    nav.current_route = response.model_dump()
    return response


@router.post("/start")
def start_navigation(body: StartNavRequest, request: Request):
    """Activate navigation to a destination and pause scanning while en route."""
    radius_m = body.radius_ft * _FT_TO_M
    nav = _nav(request)

    nav.arrival_detector.set_radius(radius_m)
    nav.arrival_detector.set_destination(body.dest_lat, body.dest_lon)
    nav.scheduler.deactivate()

    nav.is_navigating = True
    nav.destination = {
        "lat": body.dest_lat,
        "lon": body.dest_lon,
        "display_name": body.display_name,
        "radius_ft": body.radius_ft,
        "radius_m": round(radius_m, 2),
    }

    nav.gps_state.set_address(body.display_name)

    logger.info(
        "Navigation started -> (%.6f, %.6f) %s radius=%.0fft (%.1fm)",
        body.dest_lat,
        body.dest_lon,
        body.display_name,
        body.radius_ft,
        radius_m,
    )
    return {"status": "navigating", "destination": nav.destination}


@router.post("/stop")
def stop_navigation(request: Request):
    """Cancel active navigation and resume scanning."""
    nav = _nav(request)
    nav.arrival_detector.clear()
    nav.scheduler.activate()
    nav.is_navigating = False
    nav.destination = None
    nav.current_route = None

    nav.gps_state.clear_address()

    logger.info("Navigation stopped -> pipeline ACTIVE")
    return {"status": "stopped"}


@router.post("/gps")
async def update_gps(body: GPSRequest, request: Request):
    """Receive a GPS position update from the dashboard frontend."""
    nav = _nav(request)
    nav.current_pos = {"lat": body.lat, "lon": body.lon}

    nav.gps_state.update(body.lat, body.lon)

    arrived = nav.arrival_detector.update_position(body.lat, body.lon)
    if arrived:
        nav.scheduler.activate()
        nav.is_navigating = False

        try:
            await nav.ws_manager.broadcast(
                {
                    "event": "ARRIVED",
                    "lat": body.lat,
                    "lon": body.lon,
                    "destination": nav.destination,
                }
            )
            logger.info(
                "ARRIVED event broadcast to %d WS client(s)",
                nav.ws_manager.client_count,
            )
        except Exception:
            logger.exception("Failed to broadcast ARRIVED event")

    return {
        "status": "ok",
        "arrived": arrived,
        "distance_m": nav.arrival_detector.last_distance_m,
    }


@router.get("/targets")
def get_targets(request: Request):
    """Return ranked vehicle intelligence for the current destination."""
    nav = _nav(request)

    if nav.ranking_engine is None:
        return {"targets": [], "error": "ranking_engine not initialised"}

    dest = nav.destination
    if not dest:
        return {"targets": []}

    ranked = nav.ranking_engine.rank_vehicles(dest["lat"], dest["lon"])
    return {"targets": [vehicle.to_dict() for vehicle in ranked[:10]]}


@router.get("/runtime", response_model=RuntimeStatusResponse)
def get_runtime_status(request: Request):
    """Return live runtime summary for dashboard operator surfaces."""
    nav = _nav(request)
    manager = nav.scheduler.camera_manager
    cameras: list[RuntimeCameraSummary] = []
    now = time.monotonic()

    if manager is not None:
        for camera_id, capture in manager.cameras.items():
            stats = capture.stats
            last_frame_time = float(stats.get("last_frame_time") or 0.0)
            last_frame_age_s = round(now - last_frame_time, 1) if last_frame_time > 0 else None
            cameras.append(
                RuntimeCameraSummary(
                    camera_id=camera_id,
                    name=capture.config.name,
                    status="Online" if capture.is_running else "Offline",
                    fps=float(stats.get("measured_fps") or 0.0),
                    queue_depth=int(stats.get("queue_depth") or 0),
                    last_frame_age_s=last_frame_age_s,
                )
            )

    return RuntimeStatusResponse(
        pipeline_active=nav.scheduler.is_active,
        navigating=nav.is_navigating,
        arrived=nav.arrival_detector.has_arrived,
        ws_clients=nav.ws_manager.client_count,
        operator_gps=nav.current_pos,
        cameras=cameras,
    )


@router.get("/events/recent", response_model=RecentEventsResponse)
def get_recent_events(request: Request, event_type: str = "", limit: int = 25):
    """Return recent WebSocket events for dashboard hydration on page load."""
    nav = _nav(request)
    if nav.event_publisher is None:
        return RecentEventsResponse(total=0, events=[])

    normalized_type = event_type.strip().upper() or None
    events = nav.event_publisher.recent_events(normalized_type, limit)
    return RecentEventsResponse(total=len(events), events=events)


@router.get("/operator-profile", response_model=OperatorProfile)
def get_operator_profile():
    """Return persisted operator dashboard settings."""
    return _load_operator_profile()


@router.put("/operator-profile", response_model=OperatorProfile)
def update_operator_profile(profile: OperatorProfile):
    """Persist operator dashboard settings for future sessions."""
    return _save_operator_profile(profile)


@router.post("/detections/search", response_model=DetectionSearchResponse)
def search_detections(body: DetectionSearchRequest, request: Request):
    """Search detections by plate, vehicle, and optional address proximity."""
    nav = _nav(request)
    if nav.repository is None:
        return DetectionSearchResponse(address=body.address, total=0, detections=[])

    detections: list[dict]
    if body.address.strip():
        try:
            geo = nav.geocoder.geocode(body.address.strip())
            detections = nav.repository.search_detections_near(
                geo.lat,
                geo.lon,
                radius_m=body.radius_m,
                plate_text=body.plate_text,
                vehicle_class=body.vehicle_class,
                make=body.make,
                model=body.model,
                limit=body.limit,
            )
        except GeocoderError:
            detections = nav.repository.search_detections(
                plate_text=body.plate_text,
                vehicle_class=body.vehicle_class,
                make=body.make,
                model=body.model,
                detection_address=body.address,
                limit=body.limit,
            )
    else:
        detections = nav.repository.search_detections(
            plate_text=body.plate_text,
            vehicle_class=body.vehicle_class,
            make=body.make,
            model=body.model,
            detection_address=body.address,
            limit=body.limit,
        )

    return DetectionSearchResponse(
        address=body.address,
        total=len(detections),
        detections=[DetectionSummary(**d) for d in detections],
    )


@router.get("/detections/{detection_id}")
def get_detection(detection_id: int, request: Request):
    """Return full detection detail by ID."""
    nav = _nav(request)
    if nav.repository is None:
        raise HTTPException(status_code=503, detail="repository not initialised")

    row = nav.repository.get_detection_by_id(detection_id)
    if not row:
        raise HTTPException(status_code=404, detail="detection not found")
    return row


@router.get("/status")
def get_status(request: Request):
    """Return the current navigation status snapshot."""
    nav = _nav(request)
    return {
        "navigating": nav.is_navigating,
        "destination": nav.destination,
        "current_pos": nav.current_pos,
        "current_route": nav.current_route,
        "pipeline_active": nav.scheduler.is_active,
        "arrival": nav.arrival_detector.status(),
        "ws_clients": nav.ws_manager.client_count,
    }
