"""
Arrival detector: monitors GPS position and emits ARRIVED when the
vehicle enters the destination geofence.

Usage:
    detector = ArrivalDetector(radius_m=80)
    detector.set_destination(37.7749, -122.4194)

    # Call from GPS position update handler:
    arrived = detector.update_position(lat, lon)
    if arrived:
        # first crossing — do something
        ...

    detector.clear()   # stop monitoring, reset state
"""

import logging
import math
import threading
import time
from dataclasses import dataclass

logger = logging.getLogger(__name__)

_EARTH_RADIUS_M = 6_371_000.0


@dataclass
class PositionUpdate:
    lat: float
    lon: float
    distance_to_dest_m: float | None = None


class ArrivalDetector:
    """
    Thread-safe geofence arrival detector.

    Computes Haversine distance between the current GPS position and
    the active destination.  When the distance drops below `radius_m`
    for the first time, returns True from `update_position()`.

    A 90-second cooldown prevents duplicate triggers caused by GPS
    jitter near the geofence boundary.

    Subsequent calls after arrival continue to return False until
    `clear()` is called (i.e. arrival fires only once per trip).
    """

    def __init__(self, radius_m: float = 80.0):
        self.radius_m = radius_m
        self._lock = threading.Lock()

        self._dest_lat: float | None = None
        self._dest_lon: float | None = None
        self._arrived: bool = False
        self._active: bool = False
        self._last_position: PositionUpdate | None = None

        # Cooldown: prevents re-triggering within 90s of the last arrival
        self._cooldown_sec: float = 90.0
        self._last_trigger_time: float = 0.0

    # ------------------------------------------------------------------
    # Control
    # ------------------------------------------------------------------

    def set_destination(self, lat: float, lon: float):
        """Start monitoring arrival at (lat, lon)."""
        with self._lock:
            self._dest_lat = lat
            self._dest_lon = lon
            self._arrived = False
            self._active = True
            self._last_position = None
        logger.info(
            "Arrival detector active: dest=(%.6f, %.6f) radius=%.0fm",
            lat, lon, self.radius_m,
        )

    def set_radius(self, radius_m: float):
        """Update the arrival geofence radius (thread-safe)."""
        with self._lock:
            self.radius_m = radius_m
        logger.info("Arrival radius updated: %.1fm", radius_m)

    def clear(self):
        """Stop monitoring and reset all state."""
        with self._lock:
            self._dest_lat = None
            self._dest_lon = None
            self._arrived = False
            self._active = False
            self._last_position = None
            self._last_trigger_time = 0.0
        logger.info("Arrival detector cleared")

    # ------------------------------------------------------------------
    # Position update
    # ------------------------------------------------------------------

    def update_position(self, lat: float, lon: float) -> bool:
        """
        Feed a new GPS position into the detector.

        Returns True when the vehicle enters the arrival geofence AND
        the cooldown period has elapsed since the last trigger.

        Returns False when:
        - Navigation is inactive
        - Arrival was already detected this trip
        - The vehicle is outside the geofence
        - The 90-second cooldown is still active (GPS jitter protection)

        Args:
            lat: Current latitude in decimal degrees.
            lon: Current longitude in decimal degrees.

        Returns:
            True on first valid geofence entry, False otherwise.
        """
        with self._lock:
            if not self._active or self._arrived:
                return False

            dist = self._haversine(
                lat, lon,
                self._dest_lat, self._dest_lon,
            )
            self._last_position = PositionUpdate(
                lat=lat, lon=lon, distance_to_dest_m=dist,
            )

            if dist <= self.radius_m:
                now = time.monotonic()
                cooldown_remaining = self._cooldown_sec - (now - self._last_trigger_time)

                if cooldown_remaining > 0:
                    logger.debug(
                        "Arrival cooldown active — %.0fs remaining (GPS jitter suppressed)",
                        cooldown_remaining,
                    )
                    return False

                # Cooldown elapsed: fire arrival
                self._arrived = True
                self._last_trigger_time = now
                logger.info(
                    "ARRIVED at destination (%.6f, %.6f) — distance=%.1fm",
                    self._dest_lat, self._dest_lon, dist,
                )
                return True

        return False

    # ------------------------------------------------------------------
    # Status properties
    # ------------------------------------------------------------------

    @property
    def is_active(self) -> bool:
        return self._active

    @property
    def has_arrived(self) -> bool:
        return self._arrived

    @property
    def destination(self) -> tuple[float, float] | None:
        if self._dest_lat is None:
            return None
        return (self._dest_lat, self._dest_lon)

    @property
    def last_distance_m(self) -> float | None:
        pos = self._last_position
        return pos.distance_to_dest_m if pos else None

    def status(self) -> dict:
        """Serialisable status snapshot for API responses."""
        with self._lock:
            now = time.monotonic()
            cooldown_remaining = max(
                0.0, self._cooldown_sec - (now - self._last_trigger_time)
            )
            return {
                "active": self._active,
                "arrived": self._arrived,
                "destination": (
                    {"lat": self._dest_lat, "lon": self._dest_lon}
                    if self._dest_lat is not None else None
                ),
                "last_distance_m": (
                    self._last_position.distance_to_dest_m
                    if self._last_position else None
                ),
                "radius_m": self.radius_m,
                "cooldown_remaining_s": round(cooldown_remaining, 1),
            }

    # ------------------------------------------------------------------
    # Haversine formula
    # ------------------------------------------------------------------

    @staticmethod
    def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        Return the great-circle distance in metres between two GPS points.
        """
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlam = math.radians(lon2 - lon1)

        a = (
            math.sin(dphi / 2) ** 2
            + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
        )
        return 2 * _EARTH_RADIUS_M * math.asin(math.sqrt(a))
