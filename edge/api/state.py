"""
Shared navigation state container.

Separated from app.py to break the circular import between
app.py (which mounts the navigation router) and navigation.py
(which references NavigationState in its dependency function).
"""

from typing import TYPE_CHECKING, Any
import threading

from edge.navigation.geocoder import Geocoder
from edge.navigation.router import Router
from edge.navigation.arrival_detector import ArrivalDetector

if TYPE_CHECKING:
    from edge.inference.scheduler import InferenceScheduler
    from edge.ranking.engine import RankingEngine


class GpsState:
    """
    Thread-safe operator GPS position holder.

    Written by the navigation GPS endpoint (uvicorn thread) and read by
    the inference pipeline (inference thread) when building Detection
    objects. A small lock keeps the lat/lon pair consistent across reads.
    """

    def __init__(self):
        self._lat: float = 0.0
        self._lon: float = 0.0
        self._lock = threading.Lock()

    def update(self, lat: float, lon: float):
        with self._lock:
            self._lat = lat
            self._lon = lon

    def get(self) -> tuple[float, float]:
        with self._lock:
            return self._lat, self._lon

    @property
    def lat(self) -> float:
        with self._lock:
            return self._lat

    @property
    def lon(self) -> float:
        with self._lock:
            return self._lon


class NavigationState:
    """
    Holds all shared state for the navigation subsystem.
    Injected into FastAPI request handlers via app.state.
    """

    def __init__(
        self,
        scheduler:        "InferenceScheduler",
        geocoder:         Geocoder,
        router:           Router,
        arrival_detector: ArrivalDetector,
        ws_manager:       Any,       # ConnectionManager — typed as Any to avoid re-importing
        ranking_engine:   "RankingEngine | None" = None,
        gps_state:        "GpsState | None" = None,
    ):
        self.scheduler        = scheduler
        self.geocoder         = geocoder
        self.router           = router
        self.arrival_detector = arrival_detector
        self.ws_manager       = ws_manager
        self.ranking_engine   = ranking_engine
        self.gps_state        = gps_state or GpsState()

        # Navigation session state
        self.is_navigating: bool = False
        self.destination: dict | None = None        # {lat, lon, display_name, radius_ft, radius_m}
        self.current_pos: dict | None = None        # {lat, lon}
        self.current_route: dict | None = None      # route payload for status
