"""
Per-camera health monitoring.

Aggregates FPS, drop counts, reconnect counts, and last-frame staleness
from live CameraCapture instances and exposes a single get_status() call
for dashboards and watchdog processes.
"""

import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from edge.camera.capture import CameraCapture


class CameraHealthMonitor:
    """
    Wraps a dict of CameraCapture instances and surfaces health metrics.

    Usage::

        monitor = CameraHealthMonitor(camera_manager.cameras)
        status  = monitor.get_status()
        # {'cam1': {'fps': 29.7, 'frame_drops': 3, 'reconnect_count': 0,
        #           'last_frame_time': 1709123456.789, 'running': True}, ...}
    """

    def __init__(self, cameras: dict[str, "CameraCapture"]):
        """
        Args:
            cameras: Mapping of camera_id → CameraCapture instances
                     (typically CameraManager.cameras).
        """
        self._cameras = cameras

    def get_status(self) -> dict[str, dict]:
        """
        Return a health snapshot for every registered camera.

        Returns:
            Dict keyed by camera_id with fields:
                fps             – measured frames per second (float)
                frame_drops     – cumulative dropped frames (int)
                reconnect_count – number of reconnection attempts (int)
                last_frame_time – monotonic timestamp of the most recent
                                  successfully queued frame, or 0.0 if
                                  no frame has been captured yet (float)
                running         – whether the capture thread is alive (bool)
        """
        status: dict[str, dict] = {}
        for cam_id, capture in self._cameras.items():
            stats = capture.stats
            status[cam_id] = {
                "fps": stats["measured_fps"],
                "frame_drops": stats["frames_dropped"],
                "reconnect_count": stats.get("reconnect_count", 0),
                "last_frame_time": stats.get("last_frame_time", 0.0),
                "running": stats["running"],
            }
        return status

    def is_healthy(self, cam_id: str, stale_threshold_s: float = 2.0) -> bool:
        """
        Return True if the named camera is running and producing recent frames.

        Args:
            cam_id:           Camera identifier.
            stale_threshold_s: Maximum seconds since last frame before
                               declaring the stream stale.
        """
        capture = self._cameras.get(cam_id)
        if capture is None or not capture.is_running:
            return False
        last = capture.stats.get("last_frame_time", 0.0)
        return last > 0.0 and (time.monotonic() - last) < stale_threshold_s

    def unhealthy_cameras(self, stale_threshold_s: float = 2.0) -> list[str]:
        """Return list of camera IDs that are not healthy."""
        return [
            cam_id for cam_id in self._cameras
            if not self.is_healthy(cam_id, stale_threshold_s)
        ]
