"""Video capture using GStreamer for Jetson Orin Nano Super."""
import logging
import threading
import time

import cv2
import numpy as np
import yaml

logger = logging.getLogger(__name__)


class VideoCapture:
    """Hardware-accelerated video capture for Sony IMX685 via MIPI CSI-2."""

    def __init__(self, config: dict):
        self.config = config
        cam_cfg = config.get("camera", {})
        self.source = cam_cfg.get("source", 0)
        self.width = cam_cfg.get("width", 1920)
        self.height = cam_cfg.get("height", 1080)
        self.fps = cam_cfg.get("fps", 30)
        self.cam_type = cam_cfg.get("type", "csi")

        self._cap: cv2.VideoCapture | None = None
        self._frame: np.ndarray | None = None
        self._lock = threading.Lock()
        self._running = False
        self._thread: threading.Thread | None = None
        self._frame_count = 0
        self._fps_actual = 0.0
        self._fps_timer = time.monotonic()

    def _build_pipeline(self) -> str | int:
        """Build GStreamer pipeline string based on camera type."""
        gst_cfg = self.config.get("gstreamer", {})

        if self.cam_type == "csi":
            return gst_cfg.get(
                "pipeline",
                f"nvarguscamerasrc sensor-id={self.source} "
                f"! video/x-raw(memory:NVMM),width={self.width},height={self.height},"
                f"framerate={self.fps}/1,format=NV12 "
                "! nvvidconv flip-method=0 "
                "! video/x-raw,format=BGRx "
                "! videoconvert "
                "! video/x-raw,format=BGR "
                "! appsink drop=1 max-buffers=2",
            )
        elif self.cam_type == "usb":
            return gst_cfg.get(
                "usb_pipeline",
                f"v4l2src device=/dev/video{self.source} "
                f"! video/x-raw,width={self.width},height={self.height},"
                f"framerate={self.fps}/1 "
                "! videoconvert "
                "! video/x-raw,format=BGR "
                "! appsink drop=1 max-buffers=2",
            )
        elif self.cam_type == "rtsp":
            return (
                f"rtspsrc location={self.source} latency=100 "
                "! rtph264depay ! h264parse ! nvv4l2decoder "
                "! nvvidconv ! video/x-raw,format=BGRx "
                "! videoconvert ! video/x-raw,format=BGR "
                "! appsink drop=1 max-buffers=2"
            )
        else:
            # Fallback to device index
            return self.source

    def start(self) -> bool:
        """Start video capture."""
        pipeline = self._build_pipeline()

        if isinstance(pipeline, str):
            self._cap = cv2.VideoCapture(pipeline, cv2.CAP_GSTREAMER)
        else:
            self._cap = cv2.VideoCapture(pipeline)
            self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
            self._cap.set(cv2.CAP_PROP_FPS, self.fps)

        if not self._cap.isOpened():
            logger.error("Failed to open camera")
            return False

        self._running = True
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()

        logger.info(
            f"Camera started: {self.width}x{self.height} @ {self.fps}fps ({self.cam_type})"
        )
        return True

    def _capture_loop(self):
        """Background thread for continuous frame capture."""
        while self._running:
            if self._cap is None:
                break

            ret, frame = self._cap.read()
            if not ret:
                logger.warning("Frame capture failed, retrying...")
                time.sleep(0.1)
                continue

            with self._lock:
                self._frame = frame
                self._frame_count += 1

            # Calculate actual FPS
            now = time.monotonic()
            elapsed = now - self._fps_timer
            if elapsed >= 1.0:
                self._fps_actual = self._frame_count / elapsed
                self._frame_count = 0
                self._fps_timer = now

    def read(self) -> np.ndarray | None:
        """Read the latest frame (non-blocking)."""
        with self._lock:
            return self._frame.copy() if self._frame is not None else None

    @property
    def is_running(self) -> bool:
        return self._running and self._cap is not None and self._cap.isOpened()

    @property
    def actual_fps(self) -> float:
        return self._fps_actual

    def stop(self):
        """Stop video capture."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        if self._cap:
            self._cap.release()
            self._cap = None
        logger.info("Camera stopped")
