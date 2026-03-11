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
        self.queue_size = max(1, int(queue_size))
        self.cameras: dict[str, CameraCapture] = {}

        # Sliding-window frame counters for manager-level FPS
        self._fps_window: dict[str, deque[float]] = {}

        self._load_config()
        self.health = CameraHealthMonitor(self.cameras)

    # ------------------------------------------------------------------
    # Config loading
    # ------------------------------------------------------------------


    def _as_int(self, value, default: int, field_name: str, cam_id: str) -> int:
        """Best-effort int coercion with fallback logging."""
        try:
            return int(value)
        except (TypeError, ValueError):
            logger.warning(
                "Camera %s has invalid %s=%r; using default=%d",
                cam_id,
                field_name,
                value,
                default,
            )
            return default

    def _load_config(self):
        """Load camera definitions from YAML config (dict format)."""
        if not self.config_path.exists():
            logger.error("Camera config not found: %s", self.config_path)
            return

        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                raw = yaml.safe_load(f) or {}
        except yaml.YAMLError:
            logger.exception("Failed to parse camera config YAML: %s", self.config_path)
            return

        if not isinstance(raw, dict):
            logger.error("Camera config root must be a mapping: %s", self.config_path)
        except (OSError, yaml.YAMLError):
            logger.exception("Failed to parse camera config: %s", self.config_path)
            return

        if not isinstance(raw, dict):
            logger.error("Invalid camera config root type: %s", type(raw).__name__)
            return

        cameras_section = raw.get("cameras", {})

        # Support both dict-keyed format (cam1: {...}) and legacy list format
        if isinstance(cameras_section, dict):
            items = cameras_section.items()
        elif isinstance(cameras_section, list):
            # Legacy list format: [{id: cam_0, ...}, ...]
            items = ((cam.get("id", f"cam{i}"), cam) for i, cam in enumerate(cameras_section) if isinstance(cam, dict))
        else:
            logger.error("'cameras' must be a mapping or list in %s", self.config_path)
            logger.error("Invalid cameras section type: %s", type(cameras_section).__name__)
            return

        for cam_id, cam_def in items:
            if not isinstance(cam_def, dict):
                logger.warning("Camera %s config is not a mapping, skipping", cam_id)
                continue
                logger.warning("Skipping camera %s due to invalid definition type: %s", cam_id, type(cam_def).__name__)
                continue

            if not cam_def.get("enabled", True):
                logger.info("Camera %s disabled, skipping", cam_id)
                continue

            config = CameraConfig(
                camera_id=str(cam_id),
                name=cam_def.get("name", str(cam_id)),
                camera_type=str(cam_def.get("type", "csi")).lower(),
                sensor_id=self._as_int(cam_def.get("sensor_id", 0), 0, "sensor_id", str(cam_id)),
                uri=cam_def.get("uri", ""),
                role=cam_def.get("role", ""),
                housing=cam_def.get("housing", ""),
                enabled=True,
                width=self._as_int(cam_def.get("width", 1920), 1920, "width", str(cam_id)),
                height=self._as_int(cam_def.get("height", 1080), 1080, "height", str(cam_id)),
                fps=self._as_int(cam_def.get("fps", 30), 30, "fps", str(cam_id)),
            )
            self.cameras[str(cam_id)] = CameraCapture(config, self.queue_size)
            self._fps_window[str(cam_id)] = deque()

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
        if not self.cameras:
            logger.warning("CameraManager has no configured cameras")
        logger.info(
            "CameraManager started — %d/%d cameras active: %s",
            len(active), len(self.cameras), ", ".join(active) if active else "none",
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
