"""
Offline router: (start_lat, start_lon, dest_lat, dest_lon) → route.

Fully offline — no network calls, no external services.

Computes:
  • Straight-line (great-circle) distance via the Haversine formula.
  • Estimated driving duration using a conservative average speed.
  • A two-point polyline [start, end] suitable for Leaflet display.
  • ISO-8601 ETA based on current UTC time + estimated duration.

Average speed assumptions (conservative urban/suburban driving):
  • < 1 km   → 20 km/h  (city intersections / parking lots)
  • 1–10 km  → 40 km/h  (city streets)
  • > 10 km  → 80 km/h  (highway / mixed)
"""

import logging
import math
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

# Earth radius (mean, WGS-84)
_EARTH_RADIUS_M = 6_371_000.0

# Speed tiers (metres/second)
_SPEED_URBAN_MS    = 20_000 / 3600   # 20 km/h → ~5.56 m/s
_SPEED_CITY_MS     = 40_000 / 3600   # 40 km/h → ~11.11 m/s
_SPEED_HIGHWAY_MS  = 80_000 / 3600   # 80 km/h → ~22.22 m/s

_TIER_1_M = 1_000.0   # < 1 km  → urban speed
_TIER_2_M = 10_000.0  # < 10 km → city speed  (≥ 10 km → highway speed)


@dataclass
class RouteResult:
    """Driving route between two points."""
    polyline: list[list[float]]   # [[lat, lon], ...]
    distance_m: float
    duration_s: float
    eta_iso: str                   # ISO-8601 arrival time


class RouterError(Exception):
    """Raised when routing fails."""


class Router:
    """
    Offline driving route estimator using Haversine distance.

    Args:
        osrm_url: Accepted for API compatibility but ignored in offline mode.
    """

    def __init__(self, osrm_url: str = ""):  # ignored — kept for API compat
        pass

    def get_route(
        self,
        start_lat: float, start_lon: float,
        dest_lat: float,  dest_lon: float,
    ) -> RouteResult:
        """
        Compute an offline route estimate between two GPS points.

        Uses straight-line Haversine distance and a speed tier based on
        the total distance to estimate travel time.

        Args:
            start_lat / start_lon: Current position.
            dest_lat  / dest_lon : Destination position.

        Returns:
            RouteResult with a 2-point polyline, distance, duration, and ETA.

        Raises:
            RouterError: If inputs are out-of-range.
        """
        self._validate(start_lat, start_lon, "start")
        self._validate(dest_lat, dest_lon, "destination")

        distance_m = _haversine_m(start_lat, start_lon, dest_lat, dest_lon)
        duration_s = _estimate_duration_s(distance_m)
        eta = (
            datetime.now(tz=timezone.utc) + timedelta(seconds=duration_s)
        ).isoformat()

        polyline = [
            [start_lat, start_lon],
            [dest_lat,  dest_lon],
        ]

        logger.debug(
            "Offline route: %.1f m, %.0f s → ETA %s", distance_m, duration_s, eta
        )

        return RouteResult(
            polyline=polyline,
            distance_m=round(distance_m, 1),
            duration_s=round(duration_s, 1),
            eta_iso=eta,
        )

    @staticmethod
    def _validate(lat: float, lon: float, label: str) -> None:
        if not (-90.0 <= lat <= 90.0):
            raise RouterError(f"Invalid {label} latitude: {lat}")
        if not (-180.0 <= lon <= 180.0):
            raise RouterError(f"Invalid {label} longitude: {lon}")


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return great-circle distance in metres between two WGS-84 points."""
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lam = math.radians(lon2 - lon1)

    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lam / 2) ** 2
    )
    return _EARTH_RADIUS_M * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _estimate_duration_s(distance_m: float) -> float:
    """Estimate driving duration in seconds using distance-based speed tiers."""
    if distance_m < _TIER_1_M:
        speed = _SPEED_URBAN_MS
    elif distance_m < _TIER_2_M:
        speed = _SPEED_CITY_MS
    else:
        speed = _SPEED_HIGHWAY_MS
    return distance_m / speed
