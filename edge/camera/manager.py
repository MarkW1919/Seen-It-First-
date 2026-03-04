"""
Camera manager: loads camera config, starts/stops all capture threads.
"""

import logging
from pathlib import Path
from typing import Optional

import yaml

from edge.camera.capture import CameraCapture, CameraConfig, FramePacket

logger = logging.getLogger(__name__)


class CameraManager:
    """
    Manages multiple camera capture instances.

    Reads camera definitions from config.yaml, creates CameraCapture
    instances for enabled cameras, and provides a unified interface
    for retrieving frames.
    """

    def __init__(self, config_path: str, queue_size: int = 8):
        self.config_path = Path(config_path)
        self.queue_size = queue_size
        self.cameras: dict[str, CameraCapture] = {}
        self._load_config()

    def _load_config(self):
        """Load camera definitions from YAML config."""
        if not self.config_path.exists():
            logger.error("Camera config not found: %s", self.config_path)
            return

        with open(self.config_path, "r") as f:
            raw = yaml.safe_load(f)

        for cam_def in raw.get("cameras", []):
            if not cam_def.get("enabled", True):
                logger.info("Camera %s disabled, skipping", cam_def.get("id", "unknown"))
                continue

            config = CameraConfig(
                camera_id=cam_def["id"],
                name=cam_def.get("name", cam_def["id"]),
                uri=cam_def["uri"],
                camera_type=cam_def.get("type", "rtsp"),
                enabled=True,
                width=cam_def.get("width", 1920),
                height=cam_def.get("height", 1080),
                fps=cam_def.get("fps", 30),
            )
            self.cameras[config.camera_id] = CameraCapture(config, self.queue_size)

        logger.info("Loaded %d enabled cameras", len(self.cameras))

    def start_all(self) -> dict[str, bool]:
        """Start all camera capture threads. Returns {camera_id: success}."""
        results = {}
        for cam_id, capture in self.cameras.items():
            results[cam_id] = capture.start()
        return results

    def stop_all(self):
        """Stop all camera capture threads."""
        for cam_id, capture in self.cameras.items():
            logger.info("Stopping camera %s", cam_id)
            capture.stop()

    def get_latest_frames(self) -> dict[str, Optional[FramePacket]]:
        """Get the most recent frame from each camera."""
        frames = {}
        for cam_id, capture in self.cameras.items():
            if capture.is_running:
                frames[cam_id] = capture.get_frame()
        return frames

    def get_camera(self, camera_id: str) -> Optional[CameraCapture]:
        """Get a specific camera capture instance."""
        return self.cameras.get(camera_id)

    @property
    def active_camera_ids(self) -> list[str]:
        return [cid for cid, cap in self.cameras.items() if cap.is_running]

    @property
    def stats(self) -> list[dict]:
        return [cap.stats for cap in self.cameras.values()]
