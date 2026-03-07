"""
Vehicle ranking engine.

Maintains an in-memory detection cache (updated by the fusion engine on
every confirmed vehicle detection) and ranks vehicles by likelihood that
they are the target when called from the navigation API.

Design constraints
------------------
- rank_vehicles() must complete in < 3 ms (pure Python, no DB I/O).
- Cache entries older than CACHE_MAX_AGE_S (60 s) are evicted at query time.
- Thread-safe for concurrent writes from the inference thread and reads from
  the uvicorn API thread (GIL-protected dict operations are sufficient).
"""

import math
import time
import logging
from typing import TYPE_CHECKING

from edge.ranking.models import RankedVehicle
from edge.ranking.scoring import VehicleScorer

if TYPE_CHECKING:
    from edge.inference.pipeline import Detection
    from edge.hotlist.matcher import HotlistMatcher

logger = logging.getLogger(__name__)

# Discard vehicles not seen within this window
CACHE_MAX_AGE_S = 60.0

# Earth radius in feet  (3 958.8 miles × 5 280 ft/mi)
_EARTH_RADIUS_FT = 20_902_464.0


class RankingEngine:
    """
    In-memory vehicle ranking engine.

    Usage::

        engine = RankingEngine(hotlist_matcher=matcher)

        # Called by DetectionFusionEngine on every detection:
        engine.update_detection(detection)

        # Called by GET /navigation/targets:
        ranked = engine.rank_vehicles(dest_lat, dest_lon)
    """

    def __init__(self, hotlist_matcher: "HotlistMatcher | None" = None):
        # (camera_id, track_id) → most recent Detection
        self._cache: dict[tuple[str, int], "Detection"] = {}
        self._hotlist = hotlist_matcher
        self._scorer  = VehicleScorer()

    # ------------------------------------------------------------------
    # Write path (inference thread)
    # ------------------------------------------------------------------

    def update_detection(self, detection: "Detection"):
        """
        Insert or update a detection in the in-memory cache.

        Called from the inference thread on every frame where a confirmed
        track is visible.  GIL makes the dict assignment atomic.
        """
        key = (detection.camera_id, detection.track_id)
        self._cache[key] = detection

    # ------------------------------------------------------------------
    # Read path (uvicorn API thread)
    # ------------------------------------------------------------------

    def rank_vehicles(
        self,
        destination_lat: float,
        destination_lon: float,
    ) -> list[RankedVehicle]:
        """
        Rank all cached vehicles by likelihood of being the target.

        Filters out detections older than CACHE_MAX_AGE_S, computes
        Haversine distance from each detection's GPS point to the
        destination, scores via VehicleScorer, and returns a list sorted
        highest score first.

        Args:
            destination_lat: Destination latitude.
            destination_lon: Destination longitude.

        Returns:
            List[RankedVehicle], sorted by score descending.
        """
        now = time.time()
        cutoff = now - CACHE_MAX_AGE_S

        # Snapshot + evict in one pass (GIL protects the dict)
        snapshot = {k: v for k, v in self._cache.items() if v.timestamp >= cutoff}
        self._cache = dict(snapshot)

        results: list[RankedVehicle] = []

        for (cam_id, track_id), det in snapshot.items():
            age_s = now - det.timestamp

            distance_ft = _haversine_ft(
                det.latitude, det.longitude,
                destination_lat, destination_lon,
            )

            hotlist_match = self._is_hotlist(det.plate_text)

            score = self._scorer.score(
                vehicle_conf=det.vehicle_conf,
                plate_text=det.plate_text or None,
                distance_ft=distance_ft,
                hotlist_match=hotlist_match,
                age_s=age_s,
            )

            results.append(RankedVehicle(
                vehicle_id=f"{cam_id}_{track_id}",
                plate_text=det.plate_text or None,
                vehicle_type=det.vehicle_class,
                make=det.make,
                model=det.model,
                color=det.color,
                year_range=det.year_range,
                confidence=det.vehicle_conf,
                distance_ft=distance_ft,
                hotlist_match=hotlist_match,
                score=score,
                latitude=det.latitude,
                longitude=det.longitude,
                timestamp=det.timestamp,
                camera_id=cam_id,
                fingerprint=getattr(det, "fingerprint", ""),
            ))

        results.sort(key=lambda v: v.score, reverse=True)
        return results

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _is_hotlist(self, plate_text: str | None) -> bool:
        """Check plate against hotlist without triggering cooldowns."""
        if not plate_text or not self._hotlist:
            return False
        import re
        normalized = re.sub(r"[^A-Z0-9]", "", plate_text.upper().strip())
        try:
            return normalized in self._hotlist.loader.plates
        except Exception:
            return False

    @property
    def cached_count(self) -> int:
        return len(self._cache)


# ---------------------------------------------------------------------------
# Haversine distance in feet
# ---------------------------------------------------------------------------

def _haversine_ft(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return great-circle distance between two GPS points in feet."""
    if lat1 == 0.0 and lon1 == 0.0:
        # GPS not available — return large distance so vehicle scores low
        return 99_999.0

    lat1r = math.radians(lat1)
    lat2r = math.radians(lat2)
    dlat  = math.radians(lat2 - lat1)
    dlon  = math.radians(lon2 - lon1)

    a = math.sin(dlat / 2) ** 2 + math.cos(lat1r) * math.cos(lat2r) * math.sin(dlon / 2) ** 2
    c = 2 * math.asin(math.sqrt(max(0.0, a)))
    return _EARTH_RADIUS_FT * c
