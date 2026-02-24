"""Video capture using GStreamer for Jetson Orin Nano Super.

Optimized for sustained 25-30 FPS with:
- Hardware-accelerated GStreamer pipeline (sensor exposure/gain applied)
- Timestamped frame delivery for pipeline synchronization
- Thread-safe frame buffer with atomic swap
- Backoff on capture failure prevents busy-wait
"""
import logging
import threading
import time
from dataclasses import dataclass

import cv2
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class TimestampedFrame:
    """Frame with capture-time metadata for pipeline synchronization."""
    frame: np.ndarray
    timestamp: float        # monotonic capture time (seconds)
    wall_time: float        # wall-clock time (epoch seconds)
    sequence: int           # monotonically increasing frame counter
    fps_actual: float       # measured capture FPS


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
        self._latest_frame: TimestampedFrame | None = None
        self._lock = threading.Lock()
        self._running = False
        self._thread: threading.Thread | None = None

        # Thread-safe counters
        self._sequence = 0
        self._fps_actual = 0.0
        self._fps_frame_count = 0
        self._fps_timer = time.monotonic()
        self._consecutive_failures = 0
        self._max_consecutive_failures = 30

    def _build_pipeline(self) -> str | int:
        """Build optimized GStreamer pipeline with sensor controls.

        CSI pipeline applies exposure/gain ranges from sensor config
        and uses NVMM for hardware-accelerated decode path.
        """
        gst_cfg = self.config.get("gstreamer", {})
        sensor_cfg = self.config.get("sensor", {})

        if self.cam_type == "csi":
            sensor_mode = sensor_cfg.get("sensor_mode", 0)
            exp_lo = sensor_cfg.get("exposure_range", [0.001, 0.033])[0]
            exp_hi = sensor_cfg.get("exposure_range", [0.001, 0.033])[1]
            gain_lo = sensor_cfg.get("gain_range", [1.0, 16.0])[0]
            gain_hi = sensor_cfg.get("gain_range", [1.0, 16.0])[1]
            wb_mode = 1 if sensor_cfg.get("white_balance", "auto") == "auto" else 0
            ae_lock = "false" if sensor_cfg.get("auto_exposure", True) else "true"

            return gst_cfg.get(
                "pipeline_optimized",
                f"nvarguscamerasrc sensor-id={self.source} "
                f"sensor-mode={sensor_mode} "
                f"exposuretimerange=\"{int(exp_lo * 1e9)} {int(exp_hi * 1e9)}\" "
                f"gainrange=\"{gain_lo} {gain_hi}\" "
                f"wbmode={wb_mode} aelock={ae_lock} "
                f"! video/x-raw(memory:NVMM),width={self.width},height={self.height},"
                f"framerate={self.fps}/1,format=NV12 "
                "! nvvidconv flip-method=0 "
                "! video/x-raw,format=BGRx "
                "! videoconvert "
                "! video/x-raw,format=BGR "
                "! appsink drop=1 max-buffers=1 sync=false",
            )
        elif self.cam_type == "usb":
            return gst_cfg.get(
                "usb_pipeline",
                f"v4l2src device=/dev/video{self.source} io-mode=2 "
                f"! video/x-raw,width={self.width},height={self.height},"
                f"framerate={self.fps}/1 "
                "! videoconvert "
                "! video/x-raw,format=BGR "
                "! appsink drop=1 max-buffers=1 sync=false",
            )
        elif self.cam_type == "rtsp":
            return (
                f"rtspsrc location={self.source} latency=50 "
                "! rtph264depay ! h264parse ! nvv4l2decoder "
                "! nvvidconv ! video/x-raw,format=BGRx "
                "! videoconvert ! video/x-raw,format=BGR "
                "! appsink drop=1 max-buffers=1 sync=false"
            )
        else:
            return self.source

    def start(self) -> bool:
        """Start video capture with hardware acceleration."""
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

        self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        self._running = True
        self._sequence = 0
        self._consecutive_failures = 0
        self._fps_timer = time.monotonic()
        self._fps_frame_count = 0

        self._thread = threading.Thread(
            target=self._capture_loop, daemon=True, name="camera-capture"
        )
        self._thread.start()

        logger.info(
            f"Camera started: {self.width}x{self.height} @ {self.fps}fps "
            f"({self.cam_type})"
        )
        return True

    def _capture_loop(self):
        """Background thread for continuous frame capture.

        Timestamps each frame at acquisition time and atomically
        swaps the latest frame buffer.
        """
        while self._running:
            if self._cap is None:
                break

            ret, frame = self._cap.read()
            if not ret:
                self._consecutive_failures += 1
                if self._consecutive_failures >= self._max_consecutive_failures:
                    logger.error(
                        f"Camera failed {self._consecutive_failures} consecutive "
                        f"reads, stopping capture"
                    )
                    self._running = False
                    break
                backoff = min(0.01 * (2 ** min(self._consecutive_failures, 4)), 0.1)
                time.sleep(backoff)
                continue

            self._consecutive_failures = 0
            self._sequence += 1

            # Timestamp at capture time (before any lock contention)
            capture_mono = time.monotonic()
            capture_wall = time.time()

            # Update FPS counter
            self._fps_frame_count += 1
            elapsed = capture_mono - self._fps_timer
            if elapsed >= 1.0:
                self._fps_actual = self._fps_frame_count / elapsed
                self._fps_frame_count = 0
                self._fps_timer = capture_mono

            stamped = TimestampedFrame(
                frame=frame,
                timestamp=capture_mono,
                wall_time=capture_wall,
                sequence=self._sequence,
                fps_actual=self._fps_actual,
            )

            with self._lock:
                self._latest_frame = stamped

    def read(self) -> np.ndarray | None:
        """Read the latest frame (non-blocking, returns a copy)."""
        with self._lock:
            if self._latest_frame is not None:
                return self._latest_frame.frame.copy()
            return None

    def read_timestamped(self) -> TimestampedFrame | None:
        """Read the latest timestamped frame for pipeline synchronization."""
        with self._lock:
            if self._latest_frame is not None:
                return TimestampedFrame(
                    frame=self._latest_frame.frame.copy(),
                    timestamp=self._latest_frame.timestamp,
                    wall_time=self._latest_frame.wall_time,
                    sequence=self._latest_frame.sequence,
                    fps_actual=self._latest_frame.fps_actual,
                )
            return None

    @property
    def is_running(self) -> bool:
        return self._running and self._cap is not None and self._cap.isOpened()

    @property
    def actual_fps(self) -> float:
        return self._fps_actual

    @property
    def frame_sequence(self) -> int:
        return self._sequence

    def stop(self):
        """Stop video capture and release resources."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None
        if self._cap:
            self._cap.release()
            self._cap = None
        logger.info("Camera stopped")
