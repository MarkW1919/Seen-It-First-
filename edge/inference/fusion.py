"""
Multi-frame detection fusion engine.

Combines plate reads across consecutive frames for the same tracked vehicle
to produce confident, deduplicated detection events.

Confirmation criteria:
    - The same normalised plate text must appear in ≥ CONFIRM_MIN_FRAMES frames.
    - At least one of those reads must have confidence ≥ CONFIRM_MIN_CONF.

Once a (camera_id, track_id) pair is confirmed it is never re-confirmed,
preventing duplicate alerts within the same tracking lifetime.

Stale track history is evicted every EVICTION_INTERVAL_S seconds to keep
memory usage bounded for 24/7 operation.
"""

import logging
import re
import time
from collections import Counter
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from edge.inference.pipeline import Detection
    from edge.inference.events import EventPublisher
    from edge.hotlist.matcher import HotlistMatcher

logger = logging.getLogger(__name__)

# Confirmation thresholds
CONFIRM_MIN_FRAMES = 2      # plate text must appear this many times
CONFIRM_MIN_CONF   = 0.70   # minimum plate confidence for a read to count

# How long to keep history for a track that produces no new detections
HISTORY_MAX_AGE_S  = 30.0
# How many frames of history to keep per track (hard cap)
HISTORY_MAX_FRAMES = 60
# Interval between eviction sweeps
EVICTION_INTERVAL_S = 10.0


class DetectionFusionEngine:
    """
    Accumulates per-frame Detection objects per track and confirms plates.

    Usage::

        fusion = DetectionFusionEngine(event_publisher, hotlist_matcher)
        fusion.add_detection(detection)  # called by InferencePipeline
    """

    def __init__(
        self,
        event_publisher: "EventPublisher",
        hotlist_matcher: "HotlistMatcher | None" = None,
    ):
        self._publisher = event_publisher
        self._hotlist = hotlist_matcher

        # (camera_id, track_id) → list of Detection objects
        self._history: dict[tuple[str, int], list["Detection"]] = {}
        # (camera_id, track_id) → monotonic timestamp of last add
        self._last_seen: dict[tuple[str, int], float] = {}
        # Confirmed keys — never re-confirm within the same tracking lifetime
        self._confirmed: set[tuple[str, int]] = set()

        self._last_eviction = time.monotonic()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_detection(self, detection: "Detection"):
        """
        Add a frame-level detection to the fusion buffer.

        If confirmation criteria are met for the associated track, emits
        a confirmed detection event and runs the hotlist check.
        """
        key = (detection.camera_id, detection.track_id)
        now = time.monotonic()
        self._last_seen[key] = now

        # Only accumulate reads that have a plate text
        if detection.plate_text:
            history = self._history.setdefault(key, [])
            history.append(detection)
            # Hard cap on history depth
            if len(history) > HISTORY_MAX_FRAMES:
                del history[0]

            # Try to confirm if not already done
            if key not in self._confirmed:
                self._try_confirm(key, history)

        # Periodic eviction of stale tracks
        if (now - self._last_eviction) >= EVICTION_INTERVAL_S:
            self._evict_stale(now)
            self._last_eviction = now

    def set_hotlist_matcher(self, matcher: "HotlistMatcher"):
        """Attach (or replace) the hotlist matcher after construction."""
        self._hotlist = matcher

    # ------------------------------------------------------------------
    # Confirmation logic
    # ------------------------------------------------------------------

    def _try_confirm(self, key: tuple[str, int], history: list["Detection"]):
        """
        Check whether the track's plate reads satisfy confirmation criteria.

        Confirmation requires:
            - ≥ CONFIRM_MIN_FRAMES reads with confidence ≥ CONFIRM_MIN_CONF
            - The most common normalised plate text among those reads is
              consistent (i.e. it is the plurality winner).
        """
        high_conf = [
            d for d in history
            if d.plate_conf >= CONFIRM_MIN_CONF and d.plate_text
        ]
        if len(high_conf) < CONFIRM_MIN_FRAMES:
            return

        # Group by normalised plate text; choose plurality
        text_counts = Counter(_normalise(d.plate_text) for d in high_conf)
        if not text_counts:
            return

        best_text, count = text_counts.most_common(1)[0]
        if count < CONFIRM_MIN_FRAMES:
            return

        # Pick the highest-confidence read for that normalised text
        candidates = [
            d for d in high_conf
            if _normalise(d.plate_text) == best_text
        ]
        best = max(candidates, key=lambda d: d.plate_conf)

        # Mark confirmed
        self._confirmed.add(key)

        camera_id, track_id = key
        logger.info(
            "Plate confirmed: track=%d plate=%s conf=%.2f cam=%s "
            "(from %d/%d frames)",
            track_id, best_text, best.plate_conf, camera_id,
            count, len(history),
        )

        # Publish detection event
        self._publisher.publish_detection({
            "track_id":      track_id,
            "camera_id":     camera_id,
            "bbox":          best.bbox,
            "vehicle_class": best.vehicle_class,
            "vehicle_conf":  best.vehicle_conf,
            "plate_text":    best_text,
            "plate_conf":    best.plate_conf,
            "timestamp":     best.timestamp,
        })

        # Hotlist check
        if self._hotlist is not None:
            alerts = self._hotlist.match_plate(
                plate_text=best_text,
                camera_id=camera_id,
                confidence=best.plate_conf,
                track_id=track_id,
            )
            for alert in alerts:
                self._publisher.publish_alert({
                    "plate":         alert.plate,
                    "vehicle_class": best.vehicle_class,
                    "camera_id":     alert.camera_id,
                    "confidence":    alert.confidence,
                    "timestamp":     alert.timestamp,
                    "reason":        alert.reason,
                    "priority":      alert.priority,
                    "track_id":      track_id,
                })

    # ------------------------------------------------------------------
    # Memory management
    # ------------------------------------------------------------------

    def _evict_stale(self, now: float):
        """Remove history for tracks that have not been updated recently."""
        stale = [
            key for key, ts in self._last_seen.items()
            if (now - ts) > HISTORY_MAX_AGE_S
        ]
        for key in stale:
            self._history.pop(key, None)
            self._last_seen.pop(key, None)
            self._confirmed.discard(key)

        if stale:
            logger.debug("Fusion: evicted %d stale tracks", len(stale))

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------

    @property
    def active_tracks(self) -> int:
        return len(self._last_seen)

    @property
    def confirmed_count(self) -> int:
        return len(self._confirmed)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalise(plate: str) -> str:
    """Uppercase alphanumeric only — matches HotlistMatcher normalisation."""
    return re.sub(r"[^A-Z0-9]", "", plate.upper().strip())
