from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.middleware.auth import get_current_user
from app.models.user import User

router = APIRouter(prefix="/api/camera", tags=["camera"])


class CameraStatus(BaseModel):
    is_connected: bool = False
    resolution: str = "1920x1080"
    fps: float = 0.0
    night_mode: bool = False
    ir_enabled: bool = False
    ptz_position: dict = {"pan": 0.0, "tilt": 0.0, "zoom": 1.0}
    streaming: bool = False
    rtsp_url: str | None = None


class PTZCommand(BaseModel):
    pan: float | None = None
    tilt: float | None = None
    zoom: float | None = None
    speed: float = 0.5


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


# In-memory state (in production, this talks to the camera service via Redis)
_camera_status = CameraStatus()
_camera_config = CameraConfig()


@router.get("/status", response_model=CameraStatus)
async def get_camera_status(_user: User = Depends(get_current_user)):
    return _camera_status


@router.post("/ptz")
async def send_ptz_command(
    cmd: PTZCommand, _user: User = Depends(get_current_user)
):
    # Forward to camera service via Redis in production
    if cmd.pan is not None:
        _camera_status.ptz_position["pan"] = cmd.pan
    if cmd.tilt is not None:
        _camera_status.ptz_position["tilt"] = cmd.tilt
    if cmd.zoom is not None:
        _camera_status.ptz_position["zoom"] = cmd.zoom
    return {"status": "ok", "position": _camera_status.ptz_position}


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
    return {"status": "captured", "message": "Frame sent to AI pipeline"}


@router.post("/night-mode/{enabled}")
async def toggle_night_mode(
    enabled: bool, _user: User = Depends(get_current_user)
):
    _camera_status.night_mode = enabled
    _camera_status.ir_enabled = enabled
    return {"night_mode": enabled, "ir_enabled": enabled}
