"""
SEEN IT FIRST - Edge AI Vehicle LPR System
Camera health monitoring for the Jetson Orin Nano Super deployment.

Tracks per-camera FPS (rolling 5-second window), status transitions,
drop rates, and reconnection counts.  All public state is exposed as
JSON-serializable dicts for the REST / WebSocket health endpoints.
"""

import time
import threading
from collections import deque
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Dict, Optional

from edge.utils.logging import get_logger

logger = get_logger("camera.health")


# ---------------------------------------------------------------------------
# Enums & data classes
# ---------------------------------------------------------------------------

class CameraStatus(str, Enum):
    """Operational status of a single camera stream."""
    ACTIVE = "active"
    DEGRADED = "degraded"
    DISCONNECTED = "disconnected"
    RECONNECTING = "reconnecting"


@dataclass
class CameraHealth:
    """Snapshot of health metrics for one camera."""
    camera_id: str
    status: CameraStatus = CameraStatus.DISCONNECTED
    actual_fps: float = 0.0
    target_fps: float = 30.0
    total_frames: int = 0
    dropped_frames: int = 0
    reconnect_count: int = 0
    last_frame_timestamp: Optional[float] = None
    uptime_seconds: float = 0.0

    def to_dict(self) -> dict:
        """Return a JSON-serializable dictionary."""
        d = asdict(self)
        d["status"] = self.status.value
        # Round floats for readability
        d["actual_fps"] = round(self.actual_fps, 2)
        d["uptime_seconds"] = round(self.uptime_seconds, 2)
        return d


# ---------------------------------------------------------------------------
# Per-camera tracker (internal)
# ---------------------------------------------------------------------------

class _CameraTracker:
    """Internal bookkeeping for a single camera's health metrics."""

    # Width of the sliding window used to compute actual FPS.
    FPS_WINDOW_SECONDS: float = 5.0
    # If no frame arrives for this long the camera is considered disconnected.
    DISCONNECT_TIMEOUT_SECONDS: float = 5.0

    def __init__(self, camera_id: str, target_fps: float = 30.0) -> None:
        self.camera_id = camera_id
        self.target_fps = target_fps
        self.total_frames: int = 0
        self.dropped_frames: int = 0
        self.reconnect_count: int = 0
        self.start_time: float = time.monotonic()
        self.last_frame_time: Optional[float] = None
        self.is_reconnecting: bool = False

        # Deque of monotonic timestamps for frames received within the window.
        self._frame_times: deque = deque()
        self._lock = threading.Lock()

    # ----- mutations (thread-safe) -----

    def record_frame(self) -> None:
        now = time.monotonic()
        with self._lock:
            self.total_frames += 1
            self.last_frame_time = now
            self._frame_times.append(now)
            self._prune_window(now)

    def record_drop(self) -> None:
        with self._lock:
            self.dropped_frames += 1

    def record_reconnect(self) -> None:
        with self._lock:
            self.reconnect_count += 1
            self.is_reconnecting = True

    def mark_reconnected(self) -> None:
        with self._lock:
            self.is_reconnecting = False

    def mark_reconnecting(self) -> None:
        with self._lock:
            self.is_reconnecting = True

    # ----- queries (thread-safe) -----

    def compute_fps(self) -> float:
        now = time.monotonic()
        with self._lock:
            self._prune_window(now)
            count = len(self._frame_times)
            if count < 2:
                return 0.0
            span = self._frame_times[-1] - self._frame_times[0]
            if span <= 0:
                return 0.0
            return (count - 1) / span

    def determine_status(self) -> CameraStatus:
        now = time.monotonic()
        with self._lock:
            if self.is_reconnecting:
                return CameraStatus.RECONNECTING

            if self.last_frame_time is None:
                return CameraStatus.DISCONNECTED

            elapsed = now - self.last_frame_time
            if elapsed > self.DISCONNECT_TIMEOUT_SECONDS:
                return CameraStatus.DISCONNECTED

        # FPS check is outside the lock (compute_fps acquires its own lock).
        fps = self.compute_fps()
        if fps >= self.target_fps * 0.8:
            return CameraStatus.ACTIVE
        if fps > 0:
            return CameraStatus.DEGRADED
        return CameraStatus.DISCONNECTED

    def snapshot(self) -> CameraHealth:
        now = time.monotonic()
        with self._lock:
            uptime = now - self.start_time
            last_ts = self.last_frame_time
            total = self.total_frames
            dropped = self.dropped_frames
            reconnects = self.reconnect_count
            target = self.target_fps

        return CameraHealth(
            camera_id=self.camera_id,
            status=self.determine_status(),
            actual_fps=self.compute_fps(),
            target_fps=target,
            total_frames=total,
            dropped_frames=dropped,
            reconnect_count=reconnects,
            last_frame_timestamp=last_ts,
            uptime_seconds=uptime,
        )

    # ----- internal -----

    def _prune_window(self, now: float) -> None:
        """Remove timestamps older than the FPS window.  Caller holds _lock."""
        cutoff = now - self.FPS_WINDOW_SECONDS
        while self._frame_times and self._frame_times[0] < cutoff:
            self._frame_times.popleft()


# ---------------------------------------------------------------------------
# Public monitor
# ---------------------------------------------------------------------------

class CameraHealthMonitor:
    """
    Aggregated health monitor for all cameras in the system.

    Thread-safe: multiple capture threads may call ``update`` concurrently.
    """

    def __init__(self) -> None:
        self._trackers: Dict[str, _CameraTracker] = {}
        self._lock = threading.Lock()
        logger.info("CameraHealthMonitor initialized")

    # ----- registration -----

    def register_camera(self, camera_id: str, target_fps: float = 30.0) -> None:
        """Register a camera so health can be tracked from the start."""
        with self._lock:
            if camera_id not in self._trackers:
                self._trackers[camera_id] = _CameraTracker(
                    camera_id, target_fps=target_fps,
                )
                logger.info(
                    "Registered camera %s for health monitoring (target_fps=%.1f)",
                    camera_id, target_fps,
                )

    def unregister_camera(self, camera_id: str) -> None:
        with self._lock:
            self._trackers.pop(camera_id, None)
            logger.info("Unregistered camera %s from health monitoring", camera_id)

    # ----- updates -----

    def update(
        self,
        camera_id: str,
        frame_received: bool,
        dropped: bool = False,
    ) -> None:
        """
        Record a capture-loop tick for *camera_id*.

        Args:
            camera_id: Identifier of the camera.
            frame_received: ``True`` if a valid frame was obtained this tick.
            dropped: ``True`` if the frame was dropped (queue full).
        """
        tracker = self._get_tracker(camera_id)
        if frame_received:
            tracker.record_frame()
        if dropped:
            tracker.record_drop()

    def record_reconnect(self, camera_id: str) -> None:
        """Increment reconnect counter and set status to RECONNECTING."""
        tracker = self._get_tracker(camera_id)
        tracker.record_reconnect()
        logger.warning("Camera %s reconnect attempt #%d", camera_id, tracker.reconnect_count)

    def mark_reconnected(self, camera_id: str) -> None:
        """Clear the RECONNECTING flag after a successful reconnect."""
        tracker = self._get_tracker(camera_id)
        tracker.mark_reconnected()
        logger.info("Camera %s reconnected successfully", camera_id)

    def mark_reconnecting(self, camera_id: str) -> None:
        """Set the camera status to RECONNECTING."""
        tracker = self._get_tracker(camera_id)
        tracker.mark_reconnecting()

    # ----- queries -----

    def get_camera_health(self, camera_id: str) -> CameraHealth:
        """Return a ``CameraHealth`` snapshot for one camera."""
        tracker = self._get_tracker(camera_id)
        return tracker.snapshot()

    def get_health_report(self) -> dict:
        """
        Return a JSON-serializable dict keyed by camera_id containing
        every camera's current health snapshot.
        """
        with self._lock:
            ids = list(self._trackers.keys())
        return {cid: self.get_camera_health(cid).to_dict() for cid in ids}

    # ----- internal -----

    def _get_tracker(self, camera_id: str) -> _CameraTracker:
        with self._lock:
            tracker = self._trackers.get(camera_id)
            if tracker is None:
                # Auto-register on first use (defensive).
                tracker = _CameraTracker(camera_id)
                self._trackers[camera_id] = tracker
                logger.debug(
                    "Auto-registered camera %s in health monitor", camera_id,
                )
            return tracker
