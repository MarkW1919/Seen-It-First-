"""
Shared navigation state container.

Separated from app.py to break the circular import between
app.py (which mounts the navigation router) and navigation.py
(which references NavigationState in its dependency function).
"""

from typing import TYPE_CHECKING, Any

from edge.navigation.geocoder import Geocoder
from edge.navigation.router import Router
from edge.navigation.arrival_detector import ArrivalDetector

if TYPE_CHECKING:
    from edge.inference.scheduler import InferenceScheduler


class NavigationState:
    """
    Holds all shared state for the navigation subsystem.
    Injected into FastAPI request handlers via app.state.
    """

    def __init__(
        self,
        scheduler: "InferenceScheduler",
        geocoder: Geocoder,
        router: Router,
        arrival_detector: ArrivalDetector,
        ws_manager: Any,  # ConnectionManager — typed as Any to avoid re-importing app
    ):
        self.scheduler = scheduler
        self.geocoder = geocoder
        self.router = router
        self.arrival_detector = arrival_detector
        self.ws_manager = ws_manager

        # Navigation session state
        self.is_navigating: bool = False
        self.destination: dict | None = None        # {lat, lon, display_name, radius_ft, radius_m}
        self.current_pos: dict | None = None        # {lat, lon}
        self.current_route: dict | None = None      # route payload for status
