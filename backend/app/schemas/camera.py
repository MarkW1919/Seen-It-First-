from pydantic import BaseModel, field_validator

# PTZ Boundary Constants (must match camera/ptz.py)
PAN_MIN, PAN_MAX = -180.0, 180.0
TILT_MIN, TILT_MAX = -70.0, 70.0
ZOOM_MIN, ZOOM_MAX = 1.0, 30.0


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
        # Wrap to [-180, 180] for 360 degree range
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
                f"Tilt must be between {TILT_MIN} and {TILT_MAX} (140 degree range), got {v}"
            )
        return v

    @field_validator("zoom")
    @classmethod
    def validate_zoom(cls, v: float | None) -> float | None:
        if v is None:
            return v
        if v < ZOOM_MIN or v > ZOOM_MAX:
            raise ValueError(f"Zoom must be between {ZOOM_MIN}x and {ZOOM_MAX}x, got {v}x")
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
