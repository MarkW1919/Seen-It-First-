from app.schemas.camera import (
    CameraConfig,
    CameraStatus,
    PTZCommand,
    PtzPosition,
)
from app.schemas.detection import (
    DetectionCreate,
    DetectionList,
    DetectionResponse,
    PlateReadCreate,
    PlateReadResponse,
)
from app.schemas.hotlist import (
    HotListAlertResponse,
    HotListAlertUpdate,
    HotListEntryCreate,
    HotListEntryResponse,
    HotListEntryUpdate,
    HotListImport,
)
from app.schemas.route import (
    RouteCreate,
    RouteResponse,
    StopCreate,
    StopResponse,
    StopUpdate,
)
from app.schemas.scan_session import (
    ScanSessionCreate,
    ScanSessionResponse,
    ScanSessionUpdate,
)
from app.schemas.system import (
    ScanSessionSummary,
    SystemInfo,
    SystemStats,
)
from app.schemas.user import (
    Token,
    TokenRefresh,
    UserCreate,
    UserLogin,
    UserResponse,
)

__all__ = [
    "CameraConfig",
    "CameraStatus",
    "DetectionCreate",
    "DetectionList",
    "DetectionResponse",
    "HotListAlertResponse",
    "HotListAlertUpdate",
    "HotListEntryCreate",
    "HotListEntryResponse",
    "HotListEntryUpdate",
    "HotListImport",
    "PTZCommand",
    "PlateReadCreate",
    "PlateReadResponse",
    "PtzPosition",
    "RouteCreate",
    "RouteResponse",
    "ScanSessionCreate",
    "ScanSessionResponse",
    "ScanSessionSummary",
    "ScanSessionUpdate",
    "StopCreate",
    "StopResponse",
    "StopUpdate",
    "SystemInfo",
    "SystemStats",
    "Token",
    "TokenRefresh",
    "UserCreate",
    "UserLogin",
    "UserResponse",
]
