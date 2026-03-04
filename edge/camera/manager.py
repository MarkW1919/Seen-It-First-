"""
SEEN IT FIRST - Edge AI Vehicle LPR System
Camera manager for the Jetson Orin Nano Super 4-camera deployment.

Manages the lifecycle of all CameraCapture instances (2x IMX462 long-range
LPR + 2x IMX327 wide-angle classification cameras).  Provides a unified
interface for the downstream inference pipeline to pull frames, and
aggregates health / status across all cameras.

Graceful degradation: if any single camera fails the remaining cameras
continue operating normally.
"""

import threading
from typing import Dict, List, Optional

from edge.utils.logging import get_logger
from edge.camera.capture import CameraCapture, Frame, SourceType
from edge.camera.health import CameraHealthMonitor, CameraHealth, CameraStatus

logger = get_logger("camera.manager")


class CameraManager:
    """
    Manages all camera streams for the SEEN IT FIRST edge node.

    Parameters
    ----------
    cameras_config : list[dict]
        One dict per camera with keys:
            - camera_id   (str, required)
            - source_type (str, required: ``"csi"`` | ``"rtsp"`` | ``"usb"``)
            - source      (int | str, required)
            - width       (int, default 1920)
            - height      (int, default 1080)
            - fps         (int, default 30)
            - housing_id  (str, default ``""``)
            - role        (str, default ``""``)
            - queue_size  (int, default 4)

    Example config for the 4-camera rig::

        cameras_config = [
            {
                "camera_id": "cam_lpr_front",
                "source_type": "csi",
                "source": 0,
                "width": 1920, "height": 1080, "fps": 30,
                "housing_id": "housing_front",
                "role": "lpr",
            },
            {
                "camera_id": "cam_lpr_rear",
                "source_type": "csi",
                "source": 1,
                "width": 1920, "height": 1080, "fps": 30,
                "housing_id": "housing_rear",
                "role": "lpr",
            },
            {
                "camera_id": "cam_class_front",
                "source_type": "csi",
                "source": 2,
                "width": 1920, "height": 1080, "fps": 30,
                "housing_id": "housing_front",
                "role": "classifier",
            },
            {
                "camera_id": "cam_class_rear",
                "source_type": "csi",
                "source": 3,
                "width": 1920, "height": 1080, "fps": 30,
                "housing_id": "housing_rear",
                "role": "classifier",
            },
        ]
    """

    def __init__(self, cameras_config: List[dict]) -> None:
        self._health_monitor = CameraHealthMonitor()
        self._cameras: Dict[str, CameraCapture] = {}
        self._lock = threading.Lock()

        for cfg in cameras_config:
            camera_id = cfg["camera_id"]
            fps = cfg.get("fps", 30)

            # Register in the health monitor before creating the capture
            self._health_monitor.register_camera(camera_id, target_fps=float(fps))

            capture = CameraCapture(
                camera_id=camera_id,
                source_type=cfg["source_type"],
                source=cfg["source"],
                width=cfg.get("width", 1920),
                height=cfg.get("height", 1080),
                fps=fps,
                housing_id=cfg.get("housing_id", ""),
                role=cfg.get("role", ""),
                health_monitor=self._health_monitor,
                queue_size=cfg.get("queue_size", 4),
            )
            self._cameras[camera_id] = capture

        logger.info(
            "CameraManager initialized with %d camera(s): %s",
            len(self._cameras),
            ", ".join(self._cameras.keys()),
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start_all(self) -> None:
        """
        Start every registered camera's capture thread.

        Failures on individual cameras are logged but do **not** prevent
        the remaining cameras from starting (graceful degradation).
        """
        logger.info("Starting all cameras ...")
        for camera_id, capture in self._cameras.items():
            try:
                capture.start()
            except Exception:
                logger.exception(
                    "Failed to start camera %s – continuing with remaining cameras",
                    camera_id,
                )

    def stop_all(self) -> None:
        """Stop all camera capture threads gracefully."""
        logger.info("Stopping all cameras ...")
        for camera_id, capture in self._cameras.items():
            try:
                capture.stop()
            except Exception:
                logger.exception(
                    "Error stopping camera %s", camera_id,
                )
        logger.info("All cameras stopped")

    # ------------------------------------------------------------------
    # Frame access
    # ------------------------------------------------------------------

    def get_frame(self, camera_id: str) -> Optional[Frame]:
        """
        Return the next buffered frame for *camera_id*, or ``None``.

        Raises ``KeyError`` if *camera_id* is not registered.
        """
        capture = self._cameras.get(camera_id)
        if capture is None:
            raise KeyError(f"Unknown camera_id: {camera_id!r}")
        return capture.get_frame()

    def get_all_frames(self) -> Dict[str, Frame]:
        """
        Return the latest available frame from every **active** camera.

        Cameras whose queues are empty (or whose threads have died) are
        simply omitted from the result.
        """
        frames: Dict[str, Frame] = {}
        for camera_id, capture in self._cameras.items():
            frame = capture.get_frame()
            if frame is not None:
                frames[camera_id] = frame
        return frames

    # ------------------------------------------------------------------
    # Status / health
    # ------------------------------------------------------------------

    def get_active_cameras(self) -> List[str]:
        """Return the IDs of cameras whose capture threads are alive."""
        return [
            cid for cid, cap in self._cameras.items()
            if cap.is_alive
        ]

    def get_health(self) -> Dict[str, dict]:
        """
        Return a JSON-serializable health report keyed by *camera_id*.

        Each value is a dict produced by ``CameraHealth.to_dict()``.
        """
        return self._health_monitor.get_health_report()

    def get_camera_health(self, camera_id: str) -> CameraHealth:
        """Return the ``CameraHealth`` snapshot for a single camera."""
        return self._health_monitor.get_camera_health(camera_id)

    @property
    def health_monitor(self) -> CameraHealthMonitor:
        """Expose the shared health monitor for external consumers."""
        return self._health_monitor

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    @property
    def camera_ids(self) -> List[str]:
        """All registered camera IDs (regardless of status)."""
        return list(self._cameras.keys())

    def __len__(self) -> int:
        return len(self._cameras)

    def __contains__(self, camera_id: str) -> bool:
        return camera_id in self._cameras

    def __repr__(self) -> str:
        active = len(self.get_active_cameras())
        total = len(self._cameras)
        return f"<CameraManager cameras={total} active={active}>"
