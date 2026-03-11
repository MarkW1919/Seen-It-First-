"""
Inference scheduling: controls frame rates and pipeline ordering.

Enforces:
- Vehicle detection at 12-15 FPS (configurable, throttlable)
- Plate detection only on vehicle crops
- OCR only when plate confidence > threshold
- Classifier once per confirmed track
- Bounded queues, drop oldest on overflow

The actual stage execution is delegated to InferencePipeline.  The scheduler
is responsible only for rate limiting, night mode detection, and active/idle
mode switching (navigation-triggered scanning suppression).
"""

import logging
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np

from edge.camera.capture import FramePacket
from edge.inference.vehicle_detector import VehicleDetector, VehicleDetection
from edge.inference.plate_detector import PlateDetector, PlateDetection
from edge.inference.ocr import PlateOCR, OCRResult
from edge.inference.classifier import VehicleClassifier, VehicleClassification
from edge.inference.tracker import Tracker, Track

if TYPE_CHECKING:
    from edge.camera.manager import CameraManager
    from edge.inference.pipeline import InferencePipeline
    from edge.inference.fusion import DetectionFusionEngine
    from edge.inference.events import EventPublisher

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    """Result from processing a single frame through the pipeline."""
    camera_id: str
    timestamp: float
    frame_number: int
    vehicles: list[VehicleDetection] = field(default_factory=list)
    plates: list[PlateDetection] = field(default_factory=list)
    ocr_results: list[OCRResult] = field(default_factory=list)
    tracks: list[Track] = field(default_factory=list)
    classifications: dict[int, VehicleClassification] = field(default_factory=dict)
    processing_time_ms: float = 0.0
    night_mode: bool = False


class InferenceScheduler:
    """
    Orchestrates the inference pipeline with frame-rate control.

    Controls the cadence of each inference stage to stay within GPU budget.
    Supports dynamic FPS adjustment for thermal throttling and active/idle
    mode switching for navigation-triggered scanning suppression.

    Stage execution is fully delegated to InferencePipeline (set via
    set_models()).  This class handles only scheduling concerns.
    """

    def __init__(self, config: dict):
        # Target FPS for vehicle detection (adjustable for thermal)
        self.target_det_fps = config.get("vehicle_detection_fps", 15)
        self._current_det_fps = self.target_det_fps
        self._min_frame_interval = 1.0 / self._current_det_fps
        self._last_det_time: dict[str, float] = {}

        # Night mode state
        self._night_mode: dict[str, bool] = {}
        self._brightness_threshold = config.get("brightness_threshold", 60)

        # Model references kept for backward compat (thermal management,
        # shutdown, and external callers that access scheduler.classifier etc.)
        self.vehicle_detector: VehicleDetector | None = None
        self.plate_detector: PlateDetector | None = None
        self.ocr: PlateOCR | None = None
        self.classifier: VehicleClassifier | None = None

        # InferencePipeline — created by set_models()
        self.pipeline: "InferencePipeline | None" = None

        # Pipeline active flag.
        # False = IDLE (navigation en-route mode, no scanning).
        # True  = ACTIVE (default; scanning runs normally).
        self._active: bool = True

        # Camera manager — set via set_camera_manager() after construction
        self.camera_manager: "CameraManager | None" = None

        # Stats
        self._frames_processed = 0
        self._frames_skipped = 0

    # ------------------------------------------------------------------
    # Wiring
    # ------------------------------------------------------------------

    def set_camera_manager(self, manager: "CameraManager"):
        """Attach the CameraManager so the scheduler can pull frames directly."""
        self.camera_manager = manager

    def set_models(
        self,
        vehicle_detector: VehicleDetector,
        plate_detector: PlateDetector,
        ocr: PlateOCR,
        classifier: VehicleClassifier,
        tracker_config: dict,
        fusion_engine: "DetectionFusionEngine | None" = None,
        event_publisher: "EventPublisher | None" = None,
    ):
        """
        Attach loaded models and create the InferencePipeline.

        Args:
            vehicle_detector: Loaded YOLOv8n TRT engine.
            plate_detector:   Loaded YOLOv8s plate TRT engine.
            ocr:              Loaded PP-OCRv4 TRT engine.
            classifier:       Loaded YOLOv8n-cls TRT engine.
            tracker_config:   DeepSORT config dict.
            fusion_engine:    DetectionFusionEngine for multi-frame confirmation.
            event_publisher:  EventPublisher for WebSocket broadcasting.
        """
        from edge.inference.pipeline import InferencePipeline

        self.vehicle_detector = vehicle_detector
        self.plate_detector = plate_detector
        self.ocr = ocr
        self.classifier = classifier

        # Create no-op stubs if not provided (e.g. unit tests)
        if fusion_engine is None:
            fusion_engine = _NoOpFusionEngine()
        if event_publisher is None:
            event_publisher = _NoOpEventPublisher()

        self.pipeline = InferencePipeline(
            vehicle_detector=vehicle_detector,
            plate_detector=plate_detector,
            ocr=ocr,
            classifier=classifier,
            tracker_config=tracker_config,
            fusion_engine=fusion_engine,
            event_publisher=event_publisher,
        )

    # ------------------------------------------------------------------
    # Tracker access (backward compat — tracker state lives in pipeline)
    # ------------------------------------------------------------------

    @property
    def trackers(self) -> dict[str, Tracker]:
        if self.pipeline is not None:
            return self.pipeline.trackers
        return {}

    # ------------------------------------------------------------------
    # Active / idle mode
    # ------------------------------------------------------------------

    def activate(self):
        """Switch pipeline to ACTIVE (normal scanning). Called on arrival."""
        if not self._active:
            logger.info("Pipeline ACTIVE — LPR scanning enabled")
            self._active = True

    def deactivate(self):
        """Switch pipeline to IDLE (no scanning while en route)."""
        if self._active:
            logger.info("Pipeline IDLE — LPR scanning suspended (navigation mode)")
            self._active = False

    @property
    def is_active(self) -> bool:
        return self._active

    # ------------------------------------------------------------------
    # Frame processing
    # ------------------------------------------------------------------

    def process_frame(self, packet: FramePacket) -> PipelineResult | None:
        """
        Apply rate limiting and night-mode detection, then run the pipeline.

        Returns None if:
        - Pipeline is IDLE (navigation mode, en route)
        - Frame is skipped due to FPS rate limiting
        - No InferencePipeline has been initialised (set_models not called)
        """
        if not self._active:
            return None

        if self.pipeline is None:
            return None

        now = time.monotonic()
        cam_id = packet.camera_id

        # Rate limiting: skip if too soon since last detection
        last_time = self._last_det_time.get(cam_id, 0.0)
        if (now - last_time) < self._min_frame_interval:
            self._frames_skipped += 1
            return None

        self._last_det_time[cam_id] = now

        night_mode = self._check_night_mode(cam_id, packet.frame)

        result = self.pipeline.process_frame(packet, night_mode=night_mode)

        self._frames_processed += 1
        return result

    # ------------------------------------------------------------------
    # Night mode
    # ------------------------------------------------------------------

    def _check_night_mode(self, camera_id: str, frame: np.ndarray) -> bool:
        """Determine night mode via histogram brightness of the centre region."""
        h, w = frame.shape[:2]
        sample = frame[h // 4 : 3 * h // 4, w // 4 : 3 * w // 4]
        gray = np.mean(sample)
        is_night = gray < self._brightness_threshold
        prev = self._night_mode.get(camera_id)
        if prev != is_night:
            logger.info(
                "Camera %s night mode: %s (brightness: %.1f)",
                camera_id, is_night, gray,
            )
        self._night_mode[camera_id] = is_night
        return is_night

    # ------------------------------------------------------------------
    # FPS control (thermal throttling)
    # ------------------------------------------------------------------

    def set_detection_fps(self, fps: int):
        """Dynamically adjust detection FPS (for thermal throttling)."""
        if fps != self._current_det_fps:
            logger.info("Detection FPS adjusted: %d → %d", self._current_det_fps, fps)
            self._current_det_fps = fps
            self._min_frame_interval = 1.0 / fps

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    @property
    def stats(self) -> dict:
        return {
            "current_det_fps":  self._current_det_fps,
            "frames_processed": self._frames_processed,
            "frames_skipped":   self._frames_skipped,
            "active_trackers":  len(self.trackers),
            "pipeline_active":  self._active,
        }


# ---------------------------------------------------------------------------
# No-op stubs used when fusion / publisher are not provided
# ---------------------------------------------------------------------------

class _NoOpFusionEngine:
    """Fallback fusion engine used when a real engine is not wired."""

    def __init__(self):
        self.detections_seen = 0

    def add_detection(self, detection):
        self.detections_seen += 1
        return None


class _NoOpEventPublisher:
    """Fallback event publisher that records dropped events for observability."""

    def __init__(self):
        self.detection_events = 0
        self.alert_events = 0
        self.system_events = 0
        self.last_event_loop = None
        self.last_ws_manager = None

    def publish_detection(self, data):
        self.detection_events += 1
        logger.debug("No-op publisher dropped detection event: %s", data)

    def publish_alert(self, data):
        self.alert_events += 1
        logger.debug("No-op publisher dropped alert event: %s", data)

    def publish_system_event(self, event_type, data):
        self.system_events += 1
        logger.debug(
            "No-op publisher dropped system event type=%s payload=%s",
            event_type,
            data,
        )

    def set_event_loop(self, loop):
        self.last_event_loop = loop

    def set_ws_manager(self, ws_manager):
        self.last_ws_manager = ws_manager
