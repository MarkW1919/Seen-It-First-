"""
Camera manager: loads camera config, starts/stops all capture threads,
and exposes per-camera health metrics.
"""

import logging
import time
from collections import deque
from pathlib import Path
from typing import Optional

import yaml

from edge.camera.capture import CameraCapture, CameraConfig, FramePacket
from edge.camera.health import CameraHealthMonitor

logger = logging.getLogger(__name__)

# Sliding window length (seconds) for manager-level FPS tracking
_FPS_WINDOW_S = 5.0


class CameraManager:
    """
    Manages multiple CSI camera capture instances.

    Reads camera definitions from config.yaml (dict-keyed format):

        cameras:
          cam1:
            sensor_id: 0
            role: lpr
            housing: front
            width: 1920
            height: 1080
            fps: 30

    Provides:
        start_all()          → dict[str, bool]
        stop_all()
        get_frames()         → dict[str, FramePacket | None]
        get_latest_frames()  → same (alias)
        health               → CameraHealthMonitor
        stats                → list[dict]
    """

    def __init__(self, config_path: str, queue_size: int = 5):
        self.config_path = Path(config_path)
        self.queue_size = queue_size
        self.cameras: dict[str, CameraCapture] = {}

        # Sliding-window frame counters for manager-level FPS
        self._fps_window: dict[str, deque[float]] = {}

        self._load_config()
        self.health = CameraHealthMonitor(self.cameras)

    # ------------------------------------------------------------------
    # Config loading
    # ------------------------------------------------------------------

    def _load_config(self):
        """Load camera definitions from YAML config (dict format)."""
        if not self.config_path.exists():
            logger.error("Camera config not found: %s", self.config_path)
            return

        with open(self.config_path, "r") as f:
            raw = yaml.safe_load(f)

        cameras_section = raw.get("cameras", {})

        # Support both dict-keyed format (cam1: {...}) and legacy list format
        if isinstance(cameras_section, dict):
            items = cameras_section.items()
        else:
            # Legacy list format: [{id: cam_0, ...}, ...]
            items = ((cam.get("id", f"cam{i}"), cam) for i, cam in enumerate(cameras_section))

        for cam_id, cam_def in items:
            if not cam_def.get("enabled", True):
                logger.info("Camera %s disabled, skipping", cam_id)
                continue

            config = CameraConfig(
                camera_id=cam_id,
                name=cam_def.get("name", cam_id),
                camera_type=cam_def.get("type", "csi"),
                sensor_id=cam_def.get("sensor_id", 0),
                uri=cam_def.get("uri", ""),
                role=cam_def.get("role", ""),
                housing=cam_def.get("housing", ""),
                enabled=True,
                width=cam_def.get("width", 1920),
                height=cam_def.get("height", 1080),
                fps=cam_def.get("fps", 30),
            )
            self.cameras[cam_id] = CameraCapture(config, self.queue_size)
            self._fps_window[cam_id] = deque()

        logger.info("CameraManager loaded %d enabled cameras", len(self.cameras))

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start_all(self) -> dict[str, bool]:
        """Start all camera capture threads. Returns {camera_id: success}."""
        results: dict[str, bool] = {}
        for cam_id, capture in self.cameras.items():
            results[cam_id] = capture.start()

        active = [cid for cid, ok in results.items() if ok]
        logger.info(
            "CameraManager started — %d/%d cameras active: %s",
            len(active), len(self.cameras), ", ".join(active),
        )
        return results

    def stop_all(self):
        """Stop all camera capture threads."""
        for cam_id, capture in self.cameras.items():
            logger.info("Stopping camera %s", cam_id)
            capture.stop()

    # ------------------------------------------------------------------
    # Frame retrieval
    # ------------------------------------------------------------------

    def get_frames(self) -> dict[str, Optional[FramePacket]]:
        """
        Get the most recent frame from each running camera.

        Returns a dict keyed by camera_id.  Cameras with no queued
        frame map to None.  Updates the sliding-window FPS counter.
        """
        now = time.monotonic()
        frames: dict[str, Optional[FramePacket]] = {}

        for cam_id, capture in self.cameras.items():
            if not capture.is_running:
                frames[cam_id] = None
                continue

            packet = capture.read_frame()
            frames[cam_id] = packet

            # Update sliding-window timestamps for manager-level FPS
            if packet is not None:
                window = self._fps_window[cam_id]
                window.append(now)
                # Evict timestamps older than the window
                while window and (now - window[0]) > _FPS_WINDOW_S:
                    window.popleft()

        return frames

    def get_latest_frames(self) -> dict[str, Optional[FramePacket]]:
        """Alias for get_frames() — backwards-compatible name."""
        return self.get_frames()

    # ------------------------------------------------------------------
    # FPS (sliding window)
    # ------------------------------------------------------------------

    def get_fps(self, cam_id: str) -> float:
        """
        Return the manager-measured FPS for cam_id using a sliding window.

        This reflects how often get_frames() returned a frame for this
        camera, which may differ slightly from the capture-thread FPS.
        """
        window = self._fps_window.get(cam_id)
        if not window or len(window) < 2:
            return 0.0
        span = window[-1] - window[0]
        return (len(window) - 1) / span if span > 0 else 0.0

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    def get_camera(self, camera_id: str) -> Optional[CameraCapture]:
        """Get a specific camera capture instance."""
        return self.cameras.get(camera_id)

    @property
    def active_camera_ids(self) -> list[str]:
        return [cid for cid, cap in self.cameras.items() if cap.is_running]

    @property
    def stats(self) -> list[dict]:
        return [cap.stats for cap in self.cameras.values()]
