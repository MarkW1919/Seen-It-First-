"""
Camera capture module using GStreamer with NVDEC hardware acceleration.

Handles RTSP and CSI camera ingestion at 30 FPS with bounded frame queues.
Drops oldest frames on overflow to never block the ingest pipeline.
"""

import logging
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class CameraConfig:
    """Configuration for a single camera."""
    camera_id: str
    name: str
    uri: str
    camera_type: str = "rtsp"  # rtsp | csi
    enabled: bool = True
    width: int = 1920
    height: int = 1080
    fps: int = 30


@dataclass
class FramePacket:
    """A captured frame with metadata."""
    camera_id: str
    frame: np.ndarray
    timestamp: float
    frame_number: int
    width: int
    height: int


class CameraCapture:
    """
    Single camera capture thread using GStreamer NVDEC pipeline.

    Maintains a bounded deque of frames. When the queue is full,
    the oldest frame is silently dropped. The ingest thread never blocks.
    """

    def __init__(self, config: CameraConfig, queue_size: int = 8):
        self.config = config
        self.queue_size = queue_size
        self._frame_queue: deque[FramePacket] = deque(maxlen=queue_size)
        self._lock = threading.Lock()
        self._capture: Optional[cv2.VideoCapture] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._frame_count = 0
        self._dropped_frames = 0
        self._last_fps_time = 0.0
        self._fps_frame_count = 0
        self._measured_fps = 0.0

    def _build_gstreamer_pipeline(self) -> str:
        """Build GStreamer pipeline string for hardware-accelerated decode."""
        cfg = self.config

        if cfg.camera_type == "csi":
            # CSI camera via nvarguscamerasrc
            pipeline = (
                f"nvarguscamerasrc sensor-id=0 ! "
                f"video/x-raw(memory:NVMM),width={cfg.width},"
                f"height={cfg.height},framerate={cfg.fps}/1,format=NV12 ! "
                f"nvvidconv ! video/x-raw,format=BGRx ! "
                f"videoconvert ! video/x-raw,format=BGR ! appsink drop=1"
            )
        else:
            # RTSP via rtspsrc + NVDEC hardware decoder
            pipeline = (
                f"rtspsrc location={cfg.uri} latency=100 ! "
                f"rtph264depay ! h264parse ! nvv4l2decoder ! "
                f"nvvidconv ! video/x-raw,format=BGRx ! "
                f"videoconvert ! video/x-raw,format=BGR ! appsink drop=1"
            )

        return pipeline

    def start(self) -> bool:
        """Start the capture thread."""
        if self._running:
            logger.warning("Camera %s already running", self.config.camera_id)
            return False

        pipeline = self._build_gstreamer_pipeline()
        logger.info(
            "Starting camera %s (%s): %s",
            self.config.camera_id, self.config.name, self.config.uri,
        )
        logger.debug("GStreamer pipeline: %s", pipeline)

        try:
            self._capture = cv2.VideoCapture(pipeline, cv2.CAP_GSTREAMER)
        except Exception:
            logger.exception("Failed to create VideoCapture for %s", self.config.camera_id)
            return False

        if not self._capture.isOpened():
            # Fallback: try direct RTSP via FFmpeg backend
            logger.warning(
                "GStreamer pipeline failed for %s, falling back to FFmpeg",
                self.config.camera_id,
            )
            self._capture = cv2.VideoCapture(self.config.uri, cv2.CAP_FFMPEG)
            if not self._capture.isOpened():
                logger.error("Cannot open camera %s", self.config.camera_id)
                return False

        self._running = True
        self._frame_count = 0
        self._dropped_frames = 0
        self._last_fps_time = time.monotonic()
        self._fps_frame_count = 0

        self._thread = threading.Thread(
            target=self._capture_loop,
            name=f"capture-{self.config.camera_id}",
            daemon=True,
        )
        self._thread.start()
        logger.info("Camera %s capture started", self.config.camera_id)
        return True

    def stop(self):
        """Stop the capture thread and release resources."""
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=5.0)
            self._thread = None
        if self._capture is not None:
            self._capture.release()
            self._capture = None
        with self._lock:
            self._frame_queue.clear()
        logger.info(
            "Camera %s stopped. Captured: %d, Dropped: %d",
            self.config.camera_id, self._frame_count, self._dropped_frames,
        )

    def _capture_loop(self):
        """Main capture loop running in a dedicated thread."""
        while self._running:
            if self._capture is None or not self._capture.isOpened():
                logger.error("Camera %s lost connection", self.config.camera_id)
                self._running = False
                break

            ret, frame = self._capture.read()
            if not ret:
                logger.warning("Frame read failed for %s", self.config.camera_id)
                time.sleep(0.01)
                continue

            self._frame_count += 1
            now = time.monotonic()

            packet = FramePacket(
                camera_id=self.config.camera_id,
                frame=frame,
                timestamp=now,
                frame_number=self._frame_count,
                width=frame.shape[1],
                height=frame.shape[0],
            )

            with self._lock:
                if len(self._frame_queue) == self.queue_size:
                    self._dropped_frames += 1
                # deque with maxlen automatically drops oldest
                self._frame_queue.append(packet)

            # FPS measurement every 2 seconds
            self._fps_frame_count += 1
            elapsed = now - self._last_fps_time
            if elapsed >= 2.0:
                self._measured_fps = self._fps_frame_count / elapsed
                self._fps_frame_count = 0
                self._last_fps_time = now

    def get_frame(self) -> Optional[FramePacket]:
        """Get the most recent frame, or None if queue is empty."""
        with self._lock:
            if self._frame_queue:
                return self._frame_queue.pop()
            return None

    def get_all_frames(self) -> list[FramePacket]:
        """Drain all queued frames (oldest first)."""
        with self._lock:
            frames = list(self._frame_queue)
            self._frame_queue.clear()
            return frames

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def fps(self) -> float:
        return self._measured_fps

    @property
    def stats(self) -> dict:
        return {
            "camera_id": self.config.camera_id,
            "running": self._running,
            "frames_captured": self._frame_count,
            "frames_dropped": self._dropped_frames,
            "measured_fps": round(self._measured_fps, 1),
            "queue_depth": len(self._frame_queue),
        }
