from app.models.detection import Detection, PlateRead
from app.models.hotlist import HotListAlert, HotListEntry
from app.models.route import Route, RouteStop
from app.models.scan_session import ScanSession
from app.models.user import User

__all__ = [
    "Detection",
    "HotListAlert",
    "HotListEntry",
    "PlateRead",
    "Route",
    "RouteStop",
    "ScanSession",
    "User",
]
