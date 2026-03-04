"""
SEEN IT FIRST - Edge AI Vehicle LPR System
Single-camera capture with GStreamer / NVDEC on Jetson Orin Nano Super.

Supports CSI (nvarguscamerasrc), RTSP (rtspsrc + nvv4l2decoder), and USB
camera sources.  Each instance runs a dedicated daemon thread that feeds
frames into a bounded queue consumed by downstream pipeline stages.

Auto-reconnects on capture failure with exponential back-off (1 s -> 30 s).
"""

import threading
import time
import queue
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Union

import numpy as np

try:
    import cv2
except ImportError:
    cv2 = None  # type: ignore[assignment]

from edge.utils.logging import get_logger
from edge.camera.health import CameraHealthMonitor

logger = get_logger("camera.capture")


# ---------------------------------------------------------------------------
# Public data structures
# ---------------------------------------------------------------------------

class SourceType(str, Enum):
    """Type of video source connected to this camera."""
    CSI = "csi"
    RTSP = "rtsp"
    USB = "usb"


@dataclass
class Frame:
    """
    A single captured video frame with metadata.

    Attributes:
        image:       BGR numpy array (H x W x 3, dtype uint8).
        timestamp:   Monotonic time (``time.monotonic()``) at capture.
        sequence:    Monotonically increasing frame counter (per camera).
        camera_id:   Identifier of the camera that produced this frame.
        housing_id:  Physical housing / mount point identifier.
        role:        Functional role of the camera (e.g. ``"lpr"`` or ``"classifier"``).
    """
    image: np.ndarray
    timestamp: float
    sequence: int
    camera_id: str
    housing_id: str = ""
    role: str = ""


# ---------------------------------------------------------------------------
# GStreamer pipeline builders
# ---------------------------------------------------------------------------

def _gst_pipeline_csi(
    sensor_id: int, width: int, height: int, fps: int,
) -> str:
    """NVIDIA Argus CSI camera pipeline with hardware video conversion."""
    return (
        f"nvarguscamerasrc sensor-id={sensor_id} ! "
        f"video/x-raw(memory:NVMM),width={width},height={height},"
        f"framerate={fps}/1 ! "
        f"nvvidconv ! video/x-raw,format=BGRx ! "
        f"videoconvert ! video/x-raw,format=BGR ! appsink drop=1"
    )


def _gst_pipeline_rtsp(
    location: str, width: int, height: int, fps: int,
) -> str:
    """RTSP source with hardware H.264 decoding via nvv4l2decoder."""
    return (
        f"rtspsrc location={location} latency=100 ! "
        f"rtph264depay ! h264parse ! nvv4l2decoder ! "
        f"nvvidconv ! video/x-raw,format=BGRx ! "
        f"videoconvert ! video/x-raw,format=BGR ! appsink drop=1"
    )


# ---------------------------------------------------------------------------
# CameraCapture
# ---------------------------------------------------------------------------

class CameraCapture:
    """
    Threaded video capture for a single camera on the Jetson Orin Nano Super.

    Parameters
    ----------
    camera_id : str
        Unique logical identifier (e.g. ``"cam_lpr_front"``).
    source_type : str | SourceType
        One of ``"csi"``, ``"rtsp"``, ``"usb"``.
    source : int | str
        CSI sensor index, RTSP URL, or USB device index.
    width : int
        Capture width in pixels.
    height : int
        Capture height in pixels.
    fps : int
        Target capture frame-rate.
    housing_id : str
        Physical housing label (propagated on every ``Frame``).
    role : str
        Camera role label (``"lpr"`` or ``"classifier"``).
    health_monitor : CameraHealthMonitor | None
        Shared health monitor instance (optional).
    queue_size : int
        Max frames buffered before the oldest is dropped.
    """

    # Back-off constants for auto-reconnect
    _BACKOFF_BASE: float = 1.0
    _BACKOFF_MAX: float = 30.0

    def __init__(
        self,
        camera_id: str,
        source_type: Union[str, SourceType],
        source: Union[int, str],
        width: int = 1920,
        height: int = 1080,
        fps: int = 30,
        housing_id: str = "",
        role: str = "",
        health_monitor: Optional[CameraHealthMonitor] = None,
        queue_size: int = 4,
    ) -> None:
        if cv2 is None:
            raise RuntimeError(
                "OpenCV (cv2) is required but not installed. "
                "Install with: apt-get install python3-opencv"
            )

        self.camera_id = camera_id
        self.source_type = SourceType(source_type)
        self.source = source
        self.width = width
        self.height = height
        self.fps = fps
        self.housing_id = housing_id
        self.role = role

        self._health_monitor = health_monitor
        self._frame_queue: queue.Queue[Frame] = queue.Queue(maxsize=queue_size)
        self._sequence: int = 0
        self._running = threading.Event()
        self._thread: Optional[threading.Thread] = None

        # Metrics (updated atomically via the GIL – no extra lock needed)
        self.total_frames: int = 0
        self.dropped_frames: int = 0
        self.reconnect_count: int = 0
        self.last_frame_time: Optional[float] = None
        self._start_time: Optional[float] = None

        logger.info(
            "CameraCapture created: id=%s type=%s source=%s %dx%d@%dfps "
            "housing=%s role=%s",
            camera_id, self.source_type.value, source,
            width, height, fps, housing_id, role,
        )

    # ----- public interface ----

    def start(self) -> None:
        """Start the capture thread (idempotent)."""
        if self._thread is not None and self._thread.is_alive():
            logger.warning("Camera %s capture thread already running", self.camera_id)
            return

        self._running.set()
        self._start_time = time.monotonic()
        self._thread = threading.Thread(
            target=self._capture_thread,
            name=f"capture-{self.camera_id}",
            daemon=True,
        )
        self._thread.start()
        logger.info("Camera %s capture started", self.camera_id)

    def stop(self) -> None:
        """Signal the capture thread to stop and wait for it to exit."""
        if not self._running.is_set():
            return

        logger.info("Camera %s stopping capture ...", self.camera_id)
        self._running.clear()
        if self._thread is not None:
            self._thread.join(timeout=5.0)
            if self._thread.is_alive():
                logger.warning(
                    "Camera %s capture thread did not exit within 5 s",
                    self.camera_id,
                )
            self._thread = None
        logger.info(
            "Camera %s stopped (total=%d, dropped=%d, reconnects=%d)",
            self.camera_id, self.total_frames,
            self.dropped_frames, self.reconnect_count,
        )

    def get_frame(self) -> Optional[Frame]:
        """Return the next buffered frame, or ``None`` if the queue is empty."""
        try:
            return self._frame_queue.get_nowait()
        except queue.Empty:
            return None

    @property
    def is_alive(self) -> bool:
        """``True`` if the capture thread is currently running."""
        return self._thread is not None and self._thread.is_alive()

    def get_metrics(self) -> dict:
        """Return a snapshot of capture-level metrics."""
        return {
            "camera_id": self.camera_id,
            "total_frames": self.total_frames,
            "dropped_frames": self.dropped_frames,
            "reconnect_count": self.reconnect_count,
            "last_frame_time": self.last_frame_time,
            "is_alive": self.is_alive,
            "queue_depth": self._frame_queue.qsize(),
        }

    # ----- internal: capture loop -----

    def _open_capture(self) -> "cv2.VideoCapture":
        """Create and return a ``cv2.VideoCapture`` for the configured source."""
        if self.source_type == SourceType.CSI:
            pipeline = _gst_pipeline_csi(
                int(self.source), self.width, self.height, self.fps,
            )
            logger.debug("Camera %s GStreamer CSI pipeline: %s", self.camera_id, pipeline)
            cap = cv2.VideoCapture(pipeline, cv2.CAP_GSTREAMER)

        elif self.source_type == SourceType.RTSP:
            pipeline = _gst_pipeline_rtsp(
                str(self.source), self.width, self.height, self.fps,
            )
            logger.debug("Camera %s GStreamer RTSP pipeline: %s", self.camera_id, pipeline)
            cap = cv2.VideoCapture(pipeline, cv2.CAP_GSTREAMER)

        elif self.source_type == SourceType.USB:
            dev_index = int(self.source)
            logger.debug("Camera %s opening USB device %d", self.camera_id, dev_index)
            cap = cv2.VideoCapture(dev_index)
            if cap.isOpened():
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
                cap.set(cv2.CAP_PROP_FPS, self.fps)
        else:
            raise ValueError(f"Unsupported source type: {self.source_type}")

        return cap

    def _capture_thread(self) -> None:
        """
        Main capture loop.

        Reads frames at up to ``self.fps`` and pushes them into the
        bounded queue.  On failure, releases the capture and reconnects
        with exponential back-off.
        """
        backoff: float = self._BACKOFF_BASE
        cap: Optional["cv2.VideoCapture"] = None
        frame_interval: float = 1.0 / max(self.fps, 1)

        try:
            while self._running.is_set():
                # --- open / reconnect --------------------------------
                if cap is None or not cap.isOpened():
                    try:
                        cap = self._open_capture()
                    except Exception:
                        logger.exception(
                            "Camera %s failed to create VideoCapture",
                            self.camera_id,
                        )
                        cap = None

                    if cap is None or not cap.isOpened():
                        self.reconnect_count += 1
                        if self._health_monitor:
                            self._health_monitor.record_reconnect(self.camera_id)
                        logger.warning(
                            "Camera %s could not open source, retrying in %.1f s "
                            "(reconnect #%d)",
                            self.camera_id, backoff, self.reconnect_count,
                        )
                        # Sleep in small increments so we can exit quickly
                        deadline = time.monotonic() + backoff
                        while self._running.is_set() and time.monotonic() < deadline:
                            time.sleep(0.25)
                        backoff = min(backoff * 2, self._BACKOFF_MAX)
                        continue

                    # Successful open – reset back-off
                    backoff = self._BACKOFF_BASE
                    if self._health_monitor:
                        self._health_monitor.mark_reconnected(self.camera_id)
                    logger.info("Camera %s video capture opened", self.camera_id)

                # --- read frame -------------------------------------
                loop_start = time.monotonic()
                ret, raw_frame = cap.read()

                if not ret or raw_frame is None:
                    logger.warning(
                        "Camera %s read() failed – releasing capture",
                        self.camera_id,
                    )
                    cap.release()
                    cap = None
                    if self._health_monitor:
                        self._health_monitor.mark_reconnecting(self.camera_id)
                    continue

                now = time.monotonic()
                self._sequence += 1
                frame = Frame(
                    image=raw_frame,
                    timestamp=now,
                    sequence=self._sequence,
                    camera_id=self.camera_id,
                    housing_id=self.housing_id,
                    role=self.role,
                )

                # --- enqueue (drop oldest if full) ------------------
                dropped = False
                try:
                    self._frame_queue.put_nowait(frame)
                except queue.Full:
                    # Discard the oldest frame to make room
                    try:
                        self._frame_queue.get_nowait()
                    except queue.Empty:
                        pass
                    try:
                        self._frame_queue.put_nowait(frame)
                    except queue.Full:
                        pass
                    dropped = True
                    self.dropped_frames += 1

                self.total_frames += 1
                self.last_frame_time = now

                # Notify health monitor
                if self._health_monitor:
                    self._health_monitor.update(
                        self.camera_id,
                        frame_received=True,
                        dropped=dropped,
                    )

                # --- pace to target FPS -----------------------------
                elapsed = time.monotonic() - loop_start
                sleep_time = frame_interval - elapsed
                if sleep_time > 0:
                    time.sleep(sleep_time)

        except Exception:
            logger.exception(
                "Camera %s capture thread crashed unexpectedly",
                self.camera_id,
            )
        finally:
            if cap is not None:
                try:
                    cap.release()
                except Exception:
                    pass
            logger.info("Camera %s capture thread exited", self.camera_id)
