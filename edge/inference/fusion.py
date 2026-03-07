"""
Multi-frame detection fusion engine.

Combines plate reads across consecutive frames for the same tracked vehicle
to produce confident, deduplicated detection events.

Confirmation criteria:
    - The same normalised plate text must appear in ≥ CONFIRM_MIN_FRAMES frames.
    - At least one of those reads must have confidence ≥ CONFIRM_MIN_CONF.

Once a (camera_id, track_id) pair is confirmed it is never re-confirmed,
preventing duplicate alerts within the same tracking lifetime.

After confirmation the engine calls SnapshotCapture to save vehicle, plate,
and composite images, then calls EvidenceStorage to persist the record to
SQLite.  Both operations are non-blocking (JPEG writes go to a thread pool).

Stale track history is evicted every EVICTION_INTERVAL_S seconds to keep
memory usage bounded for 24/7 operation.
"""

import logging
import re
import time
from collections import Counter
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable

import numpy as np

from edge.inference.vehicle_fingerprint import FingerprintDeduplicator

if TYPE_CHECKING:
    from edge.inference.pipeline import Detection
    from edge.inference.events import EventPublisher
    from edge.hotlist.matcher import HotlistMatcher, HotlistAlert
    from edge.evidence.capture import SnapshotCapture
    from edge.evidence.storage import EvidenceStorage
    from edge.ranking.engine import RankingEngine

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
        event_publisher:  "EventPublisher",
        hotlist_matcher:  "HotlistMatcher | None"  = None,
        snapshot_capture: "SnapshotCapture | None" = None,
        evidence_storage: "EvidenceStorage | None" = None,
        ranking_engine:   "RankingEngine | None"   = None,
        alert_callback:   "Callable[[HotlistAlert], None] | None" = None,
    ):
        self._publisher       = event_publisher
        self._hotlist         = hotlist_matcher
        self._snapshot        = snapshot_capture
        self._evidence        = evidence_storage
        self._ranking         = ranking_engine
        # Called for every confirmed hotlist match (console alert, DB save, etc.)
        self._alert_callback  = alert_callback

        # (camera_id, track_id) → list of Detection objects (plate_text reads)
        self._history: dict[tuple[str, int], list["Detection"]] = {}
        # (camera_id, track_id) → monotonic timestamp of last add
        self._last_seen: dict[tuple[str, int], float] = {}
        # Confirmed keys — never re-confirm within the same tracking lifetime
        self._confirmed: set[tuple[str, int]] = set()

        # Best evidence per track: (frame, plate_bbox) for the highest-conf read
        # Frame is stored once and cleared immediately after evidence capture.
        self._best_evidence: dict[tuple[str, int], tuple[np.ndarray, list[float] | None, float]] = {}
        # key → (frame, plate_bbox, plate_conf)

        self._last_eviction = time.monotonic()

        # Fingerprint-based deduplication (5 s / 10 ft window)
        self._fp_dedup = FingerprintDeduplicator()

    # ------------------------------------------------------------------
    # Wiring setters (called after construction to avoid circular imports)
    # ------------------------------------------------------------------

    def set_hotlist_matcher(self, matcher: "HotlistMatcher"):
        self._hotlist = matcher

    def set_snapshot_capture(self, capture: "SnapshotCapture"):
        self._snapshot = capture

    def set_evidence_storage(self, storage: "EvidenceStorage"):
        self._evidence = storage

    def set_ranking_engine(self, engine: "RankingEngine"):
        self._ranking = engine

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_detection(self, detection: "Detection"):
        """
        Add a frame-level detection to the fusion buffer.

        If confirmation criteria are met for the associated track, emits
        a confirmed detection event, captures evidence images, and runs
        the hotlist check.
        """
        key = (detection.camera_id, detection.track_id)
        now = time.monotonic()
        self._last_seen[key] = now

        # Fingerprint-based deduplication — suppress duplicate vehicle events
        # that appear within 5 s and 10 ft (e.g. same vehicle seen by two cameras).
        if self._fp_dedup.is_duplicate(
            detection.fingerprint, detection.timestamp,
            detection.latitude, detection.longitude,
        ):
            # Still update the ranking cache with the latest position/confidence
            if self._ranking is not None:
                self._ranking.update_detection(detection)
            return

        # Feed ALL vehicle detections into the ranking engine cache,
        # regardless of whether a plate was read.
        if self._ranking is not None:
            self._ranking.update_detection(detection)

        # Keep best evidence frame (highest plate confidence with a frame)
        if detection.frame is not None:
            existing = self._best_evidence.get(key)
            if existing is None or detection.plate_conf > existing[2]:
                self._best_evidence[key] = (
                    detection.frame,
                    detection.plate_bbox,
                    detection.plate_conf,
                )
            # Detach frame from Detection so it can be GC'd if not selected
            detection.frame = None

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

    # ------------------------------------------------------------------
    # Confirmation logic
    # ------------------------------------------------------------------

    def _try_confirm(self, key: tuple[str, int], history: list["Detection"]):
        """
        Check whether the track's plate reads satisfy confirmation criteria.

        Confirmation requires:
            - ≥ CONFIRM_MIN_FRAMES reads with confidence ≥ CONFIRM_MIN_CONF
            - The most common normalised plate text among those reads is
              the plurality winner.
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

        # Mark confirmed before any I/O to prevent double-confirmation
        self._confirmed.add(key)

        camera_id, track_id = key
        logger.info(
            "Plate confirmed: track=%d plate=%s conf=%.2f cam=%s "
            "(from %d/%d frames)",
            track_id, best_text, best.plate_conf, camera_id,
            count, len(history),
        )

        # ── Evidence capture ──────────────────────────────────────────
        vehicle_path   = ""
        plate_path     = ""
        composite_path = ""

        evidence = self._best_evidence.pop(key, None)
        if evidence is not None and self._snapshot is not None:
            ev_frame, ev_plate_bbox, _ = evidence
            try:
                vehicle_path = self._snapshot.capture_vehicle(
                    ev_frame, best.bbox, camera_id
                )
                if ev_plate_bbox is not None:
                    plate_path = self._snapshot.capture_plate(
                        ev_frame, ev_plate_bbox, best_text, camera_id
                    )
                composite_path = self._snapshot.capture_composite(
                    ev_frame, best.bbox, ev_plate_bbox
                )
                logger.debug(
                    "Evidence scheduled: vehicle=%s plate=%s composite=%s",
                    vehicle_path, plate_path, composite_path,
                )
            except Exception:
                logger.exception(
                    "Evidence capture failed: track=%d cam=%s", track_id, camera_id
                )
            finally:
                # Release frame reference regardless of success
                del ev_frame

        # ── DB persistence ────────────────────────────────────────────
        if self._evidence is not None:
            try:
                self._evidence.store_detection(
                    vehicle_path=vehicle_path,
                    plate_path=plate_path,
                    composite_path=composite_path,
                    plate_text=best_text,
                    vehicle_class=best.vehicle_class,
                    confidence=best.plate_conf,
                    camera_id=camera_id,
                    track_id=track_id,
                    bbox=best.bbox,
                    make=best.make,
                    model=best.model,
                    color=best.color,
                    year_range=best.year_range,
                    latitude=best.latitude,
                    longitude=best.longitude,
                    fingerprint=best.fingerprint,
                )
            except Exception:
                logger.exception(
                    "EvidenceStorage.store_detection failed: track=%d cam=%s",
                    track_id, camera_id,
                )

        # ── WebSocket event ───────────────────────────────────────────
        self._publisher.publish_detection({
            "track_id":       track_id,
            "camera_id":      camera_id,
            "bbox":           best.bbox,
            "vehicle_class":  best.vehicle_class,
            "make":           best.make,
            "model":          best.model,
            "color":          best.color,
            "year_range":     best.year_range,
            "fingerprint":    best.fingerprint,
            "vehicle_conf":   best.vehicle_conf,
            "plate_text":     best_text,
            "plate_conf":     best.plate_conf,
            "timestamp":      best.timestamp,
            "vehicle_path":   vehicle_path,
            "plate_path":     plate_path,
            "composite_path": composite_path,
        })

        # ── Hotlist check ─────────────────────────────────────────────
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
                # Side effects: console/audio alert + DB persistence
                if self._alert_callback is not None:
                    try:
                        self._alert_callback(alert)
                    except Exception:
                        logger.exception("alert_callback raised for plate=%s", alert.plate)

    # ------------------------------------------------------------------
    # Memory management
    # ------------------------------------------------------------------

    def _evict_stale(self, now: float):
        """Remove history and evidence frames for tracks not recently updated."""
        stale = [
            key for key, ts in self._last_seen.items()
            if (now - ts) > HISTORY_MAX_AGE_S
        ]
        for key in stale:
            self._history.pop(key, None)
            self._last_seen.pop(key, None)
            self._confirmed.discard(key)
            self._best_evidence.pop(key, None)   # release frame memory

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
