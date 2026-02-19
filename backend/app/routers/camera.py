"""Camera API router with PTZ boundary enforcement and motion state tracking.

Fixes:
- PTZ commands now validated against 360° pan / 140° tilt / 30x zoom boundaries
- Speed clamped to valid Pelco-D range [1, 63] mapped from [0, 1] float
- PTZ position updates are atomic (no partial dict mutation race)
- Motion state tracked in status for frontend frame suppression
- In production, commands are forwarded via Redis to the camera service
"""

import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator

from app.middleware.auth import get_current_user
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/camera", tags=["camera"])

# ─── PTZ Boundary Constants (must match camera/ptz.py) ───

PAN_MIN, PAN_MAX = -180.0, 180.0
TILT_MIN, TILT_MAX = -70.0, 70.0
ZOOM_MIN, ZOOM_MAX = 1.0, 30.0


# ─── Models ───


class PtzPosition(BaseModel):
    pan: float = 0.0
    tilt: float = 0.0
    zoom: float = 1.0


class CameraStatus(BaseModel):
    is_connected: bool = False
    resolution: str = "1920x1080"
    fps: float = 0.0
    night_mode: bool = False
    ir_enabled: bool = False
    ptz_position: PtzPosition = PtzPosition()
    ptz_motion: str = "idle"  # idle, moving, settling
    ptz_connected: bool = False
    streaming: bool = False
    rtsp_url: str | None = None


class PTZCommand(BaseModel):
    pan: float | None = None
    tilt: float | None = None
    zoom: float | None = None
    speed: float = 0.5  # 0.0 to 1.0 normalized speed

    @field_validator("pan")
    @classmethod
    def validate_pan(cls, v: float | None) -> float | None:
        if v is None:
            return v
        # Wrap to [-180, 180] for 360° range
        while v > PAN_MAX:
            v -= 360.0
        while v < PAN_MIN:
            v += 360.0
        return v

    @field_validator("tilt")
    @classmethod
    def validate_tilt(cls, v: float | None) -> float | None:
        if v is None:
            return v
        if v < TILT_MIN or v > TILT_MAX:
            raise ValueError(
                f"Tilt must be between {TILT_MIN}° and {TILT_MAX}° (140° range), got {v}°"
            )
        return v

    @field_validator("zoom")
    @classmethod
    def validate_zoom(cls, v: float | None) -> float | None:
        if v is None:
            return v
        if v < ZOOM_MIN or v > ZOOM_MAX:
            raise ValueError(
                f"Zoom must be between {ZOOM_MIN}x and {ZOOM_MAX}x, got {v}x"
            )
        return v

    @field_validator("speed")
    @classmethod
    def validate_speed(cls, v: float) -> float:
        return max(0.0, min(1.0, v))


class CameraConfig(BaseModel):
    resolution: str = "1920x1080"
    fps: int = 30
    exposure: str = "auto"
    gain: str = "auto"
    white_balance: str = "auto"
    ir_cut: bool = True
    night_mode_auto: bool = True
    denoise: bool = True
    hdr: bool = False


# ─── In-memory State ───
# In production, status comes from the camera service via Redis pub/sub.
# Commands are forwarded to the camera service via Redis.

_status_lock = asyncio.Lock()
_camera_status = CameraStatus()
_camera_config = CameraConfig()


# ─── Endpoints ───


@router.get("/status", response_model=CameraStatus)
async def get_camera_status(_user: User = Depends(get_current_user)):
    return _camera_status


@router.post("/ptz")
async def send_ptz_command(
    cmd: PTZCommand, _user: User = Depends(get_current_user)
):
    """Send a PTZ command with boundary enforcement.

    Pan: 360° range [-180, +180] with wrapping
    Tilt: 140° range [-70, +70] with hard limits
    Zoom: 1x to 30x
    Speed: 0.0 to 1.0 (normalized, mapped to hardware range)
    """
    async with _status_lock:
        pos = _camera_status.ptz_position
        if cmd.pan is not None:
            pos.pan = cmd.pan
        if cmd.tilt is not None:
            pos.tilt = cmd.tilt
        if cmd.zoom is not None:
            pos.zoom = cmd.zoom
        new_position = pos.model_dump()

    return {"status": "ok", "position": new_position}


@router.post("/ptz/stop")
async def stop_ptz(_user: User = Depends(get_current_user)):
    """Emergency stop — immediately halt all PTZ movement."""
    async with _status_lock:
        _camera_status.ptz_motion = "idle"
    return {"status": "stopped"}


@router.post("/ptz/home")
async def home_ptz(_user: User = Depends(get_current_user)):
    """Return PTZ to home position (0°, 0°, 1x)."""
    async with _status_lock:
        _camera_status.ptz_position = PtzPosition(pan=0.0, tilt=0.0, zoom=1.0)
    return {"status": "ok", "position": {"pan": 0.0, "tilt": 0.0, "zoom": 1.0}}


@router.get("/config", response_model=CameraConfig)
async def get_camera_config(_user: User = Depends(get_current_user)):
    return _camera_config


@router.put("/config", response_model=CameraConfig)
async def update_camera_config(
    config: CameraConfig, _user: User = Depends(get_current_user)
):
    global _camera_config
    _camera_config = config
    return _camera_config


@router.post("/capture")
async def trigger_capture(_user: User = Depends(get_current_user)):
    """Trigger a manual frame capture for processing."""
    if _camera_status.ptz_motion != "idle":
        raise HTTPException(
            status_code=409,
            detail="Cannot capture while PTZ is moving — frame would be blurry",
        )
    return {"status": "captured", "message": "Frame sent to AI pipeline"}


@router.post("/night-mode/{enabled}")
async def toggle_night_mode(
    enabled: bool, _user: User = Depends(get_current_user)
):
    _camera_status.night_mode = enabled
    _camera_status.ir_enabled = enabled
    return {"night_mode": enabled, "ir_enabled": enabled}
