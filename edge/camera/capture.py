"""
Camera capture module using GStreamer with Jetson hardware acceleration.

Handles CSI camera ingestion (nvarguscamerasrc / NVMM) and optional RTSP
fallback at 30 FPS with bounded frame queues.  Drops oldest frames on
overflow so the ingest thread never blocks the inference pipeline.
"""

import logging
import queue
import threading
import time
from dataclasses import dataclass, field
from typing import Optional

import cv2
import numpy as np

from edge.camera.pipeline_builder import build_csi_pipeline, build_rtsp_pipeline

logger = logging.getLogger(__name__)


@dataclass
class CameraConfig:
    """Configuration for a single camera."""
    camera_id: str
    name: str
    camera_type: str = "csi"        # csi | rtsp
    sensor_id: int = 0              # CSI port (nvarguscamerasrc sensor-id)
    uri: str = ""                   # RTSP URI (rtsp:// …) — unused for CSI
    role: str = ""                  # lpr | wide
    housing: str = ""               # front | rear
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
    Single camera capture thread using GStreamer NVMM pipeline.

    Maintains a bounded queue of frames (queue.Queue, maxsize=5).
    When the queue is full, the oldest frame is discarded before the
    new one is inserted so the ingest thread never blocks.

    Public API::

        capture.start()       → bool
        capture.stop()
        capture.read_frame()  → FramePacket | None  (alias: get_frame)
        capture.reconnect()   → bool
    """

    _RECONNECT_DELAY_S = 2.0      # wait between reconnect attempts
    _MAX_READ_FAILURES = 10       # consecutive failures before reconnecting

    def __init__(self, config: CameraConfig, queue_size: int = 5):
        self.config = config
        self._frame_queue: queue.Queue[FramePacket] = queue.Queue(maxsize=queue_size)
        self._lock = threading.Lock()
        self._capture: Optional[cv2.VideoCapture] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._frame_count = 0
        self._dropped_frames = 0
        self._reconnect_count = 0
        self._last_frame_time = 0.0
        self._last_fps_time = 0.0
        self._fps_frame_count = 0
        self._measured_fps = 0.0

    # ------------------------------------------------------------------
    # Pipeline
    # ------------------------------------------------------------------

    def _build_pipeline(self) -> str:
        cfg = self.config
        if cfg.camera_type == "csi":
            return build_csi_pipeline(cfg.sensor_id, cfg.width, cfg.height, cfg.fps)
        return build_rtsp_pipeline(cfg.uri)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> bool:
        """Open the GStreamer pipeline and start the capture thread."""
        if self._running:
            logger.warning("Camera %s already running", self.config.camera_id)
            return False

        if not self._open_capture():
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
        """Signal the capture thread to exit and release resources."""
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=5.0)
            self._thread = None
        self._release_capture()
        # Drain the queue
        while not self._frame_queue.empty():
            try:
                self._frame_queue.get_nowait()
            except queue.Empty:
                break
        logger.info(
            "Camera %s stopped. Captured: %d, Dropped: %d, Reconnects: %d",
            self.config.camera_id,
            self._frame_count,
            self._dropped_frames,
            self._reconnect_count,
        )

    def reconnect(self) -> bool:
        """
        Close the current pipeline and reopen it.

        Called automatically by the capture loop after repeated read failures.
        Can also be called externally (e.g. watchdog thread).

        Returns:
            True if the new pipeline opened successfully.
        """
        logger.warning(
            "Camera %s reconnecting (attempt %d)…",
            self.config.camera_id,
            self._reconnect_count + 1,
        )
        self._release_capture()
        time.sleep(self._RECONNECT_DELAY_S)

        success = self._open_capture()
        if success:
            self._reconnect_count += 1
            logger.info(
                "Camera %s reconnected (total reconnects: %d)",
                self.config.camera_id,
                self._reconnect_count,
            )
        else:
            logger.error("Camera %s reconnect failed", self.config.camera_id)
        return success

    # ------------------------------------------------------------------
    # Frame retrieval
    # ------------------------------------------------------------------

    def read_frame(self) -> Optional[FramePacket]:
        """
        Return the most recent frame from the queue, or None if empty.

        Equivalent to get_frame(); provided so call-sites can use either name.
        """
        try:
            return self._frame_queue.get_nowait()
        except queue.Empty:
            return None

    def get_frame(self) -> Optional[FramePacket]:
        """Alias for read_frame()."""
        return self.read_frame()

    def get_all_frames(self) -> list[FramePacket]:
        """Drain all queued frames and return them oldest-first."""
        frames: list[FramePacket] = []
        while True:
            try:
                frames.append(self._frame_queue.get_nowait())
            except queue.Empty:
                break
        return frames

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _open_capture(self) -> bool:
        """Open cv2.VideoCapture via GStreamer pipeline."""
        pipeline = self._build_pipeline()
        logger.info(
            "Opening camera %s (%s) — sensor_id=%d",
            self.config.camera_id,
            self.config.name,
            self.config.sensor_id,
        )
        logger.debug("GStreamer pipeline: %s", pipeline)

        try:
            cap = cv2.VideoCapture(pipeline, cv2.CAP_GSTREAMER)
        except Exception:
            logger.exception(
                "VideoCapture constructor failed for %s", self.config.camera_id
            )
            return False

        if not cap.isOpened():
            logger.error(
                "GStreamer pipeline failed to open for %s", self.config.camera_id
            )
            cap.release()
            return False

        self._capture = cap
        return True

    def _release_capture(self):
        if self._capture is not None:
            self._capture.release()
            self._capture = None

    def _enqueue(self, packet: FramePacket):
        """Insert packet; drop oldest if queue is full."""
        if self._frame_queue.full():
            try:
                self._frame_queue.get_nowait()   # discard oldest
                self._dropped_frames += 1
            except queue.Empty:
                pass
        self._frame_queue.put_nowait(packet)

    def _capture_loop(self):
        """Main loop running in a dedicated daemon thread."""
        consecutive_failures = 0

        while self._running:
            if self._capture is None or not self._capture.isOpened():
                if not self.reconnect():
                    time.sleep(self._RECONNECT_DELAY_S)
                    continue
                consecutive_failures = 0

            ret, frame = self._capture.read()

            if not ret:
                consecutive_failures += 1
                logger.warning(
                    "Camera %s: read failure %d/%d",
                    self.config.camera_id,
                    consecutive_failures,
                    self._MAX_READ_FAILURES,
                )
                if consecutive_failures >= self._MAX_READ_FAILURES:
                    if not self.reconnect():
                        time.sleep(self._RECONNECT_DELAY_S)
                    consecutive_failures = 0
                else:
                    time.sleep(0.01)
                continue

            consecutive_failures = 0
            self._frame_count += 1
            now = time.monotonic()
            self._last_frame_time = now

            packet = FramePacket(
                camera_id=self.config.camera_id,
                frame=frame,
                timestamp=now,
                frame_number=self._frame_count,
                width=frame.shape[1],
                height=frame.shape[0],
            )
            self._enqueue(packet)

            # FPS measurement — update every 2 seconds
            self._fps_frame_count += 1
            elapsed = now - self._last_fps_time
            if elapsed >= 2.0:
                self._measured_fps = self._fps_frame_count / elapsed
                self._fps_frame_count = 0
                self._last_fps_time = now

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

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
            "reconnect_count": self._reconnect_count,
            "measured_fps": round(self._measured_fps, 1),
            "last_frame_time": self._last_frame_time,
            "queue_depth": self._frame_queue.qsize(),
        }


# ---------------------------------------------------------------------------
# Quick smoke-test: python -m edge.camera.capture
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    import signal

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    from edge.camera.manager import CameraManager

    config_path = sys.argv[1] if len(sys.argv) > 1 else "edge/camera/config.yaml"
    manager = CameraManager(config_path)
    manager.start_all()

    stop = threading.Event()
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    signal.signal(signal.SIGTERM, lambda *_: stop.set())

    print(f"\nMonitoring {len(manager.cameras)} cameras (Ctrl-C to stop)…\n")
    try:
        while not stop.is_set():
            time.sleep(2.0)
            for cam_id, cap in manager.cameras.items():
                s = cap.stats
                print(
                    f"  {cam_id}: {s['measured_fps']:.1f} FPS  "
                    f"captured={s['frames_captured']}  "
                    f"dropped={s['frames_dropped']}  "
                    f"reconnects={s['reconnect_count']}  "
                    f"running={s['running']}"
                )
            print()
    finally:
        manager.stop_all()
