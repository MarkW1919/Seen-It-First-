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

_FPS_WINDOW_S = 5.0


class CameraManager:
    """
    Manages multiple camera capture instances.

    Reads camera definitions from config.yaml in either dict-keyed or legacy
    list form, and exposes lifecycle helpers plus manager-level FPS tracking.
    """

    def __init__(self, config_path: str, queue_size: int = 5):
        self.config_path = Path(config_path)
        self.queue_size = max(1, int(queue_size))
        self.cameras: dict[str, CameraCapture] = {}
        self._fps_window: dict[str, deque[float]] = {}

        self._load_config()
        self.health = CameraHealthMonitor(self.cameras)

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
        """Load camera definitions from YAML config."""
        if not self.config_path.exists():
            logger.error("Camera config not found: %s", self.config_path)
            return

        try:
            with open(self.config_path, "r", encoding="utf-8") as file_obj:
                raw = yaml.safe_load(file_obj) or {}
        except (OSError, yaml.YAMLError):
            logger.exception("Failed to parse camera config: %s", self.config_path)
            return

        if not isinstance(raw, dict):
            logger.error(
                "Camera config root must be a mapping, got %s",
                type(raw).__name__,
            )
            return

        cameras_section = raw.get("cameras", {})
        if isinstance(cameras_section, dict):
            items = cameras_section.items()
        elif isinstance(cameras_section, list):
            items = (
                (cam.get("id", f"cam{i}"), cam)
                for i, cam in enumerate(cameras_section)
                if isinstance(cam, dict)
            )
        else:
            logger.error("'cameras' must be a mapping or list in %s", self.config_path)
            logger.error("Invalid cameras section type: %s", type(cameras_section).__name__)
            return

        for cam_id, cam_def in items:
            if not isinstance(cam_def, dict):
                logger.warning(
                    "Skipping camera %s due to invalid definition type: %s",
                    cam_id,
                    type(cam_def).__name__,
                )
                continue

            if not cam_def.get("enabled", True):
                logger.info("Camera %s disabled, skipping", cam_id)
                continue

            config = CameraConfig(
                camera_id=str(cam_id),
                name=cam_def.get("name", str(cam_id)),
                camera_type=str(cam_def.get("type", "csi")).lower(),
                sensor_id=self._as_int(
                    cam_def.get("sensor_id", 0),
                    0,
                    "sensor_id",
                    str(cam_id),
                ),
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

    def start_all(self) -> dict[str, bool]:
        """Start all camera capture threads and return {camera_id: success}."""
        results: dict[str, bool] = {}
        for cam_id, capture in self.cameras.items():
            results[cam_id] = capture.start()

        active = [cid for cid, ok in results.items() if ok]
        if not self.cameras:
            logger.warning("CameraManager has no configured cameras")
        logger.info(
            "CameraManager started - %d/%d cameras active: %s",
            len(active),
            len(self.cameras),
            ", ".join(active) if active else "none",
        )
        return results

    def stop_all(self):
        """Stop all camera capture threads."""
        for cam_id, capture in self.cameras.items():
            logger.info("Stopping camera %s", cam_id)
            capture.stop()

    def get_frames(self) -> dict[str, Optional[FramePacket]]:
        """
        Get the most recent frame from each running camera.

        Returns a dict keyed by camera_id. Cameras with no queued frame map to
        None. The sliding-window FPS counter is updated for returned frames.
        """
        now = time.monotonic()
        frames: dict[str, Optional[FramePacket]] = {}

        for cam_id, capture in self.cameras.items():
            if not capture.is_running:
                frames[cam_id] = None
                continue

            packet = capture.read_frame()
            frames[cam_id] = packet

            if packet is not None:
                window = self._fps_window[cam_id]
                window.append(now)
                while window and (now - window[0]) > _FPS_WINDOW_S:
                    window.popleft()

        return frames

    def get_latest_frames(self) -> dict[str, Optional[FramePacket]]:
        """Alias for get_frames() for backwards compatibility."""
        return self.get_frames()

    def get_fps(self, cam_id: str) -> float:
        """Return the manager-measured FPS for a camera using a sliding window."""
        window = self._fps_window.get(cam_id)
        if not window or len(window) < 2:
            return 0.0
        span = window[-1] - window[0]
        return (len(window) - 1) / span if span > 0 else 0.0

    def get_camera(self, camera_id: str) -> Optional[CameraCapture]:
        """Get a specific camera capture instance."""
        return self.cameras.get(camera_id)

    @property
    def active_camera_ids(self) -> list[str]:
        return [cid for cid, cap in self.cameras.items() if cap.is_running]

    @property
    def stats(self) -> list[dict]:
        return [cap.stats for cap in self.cameras.values()]
