"""
Inference scheduling: controls frame rates and pipeline ordering.

Enforces:
- Vehicle detection at 12-15 FPS (configurable, throttlable)
- Plate detection only on vehicle crops
- OCR only when plate confidence > threshold
- Classifier once per confirmed track
- Bounded queues, drop oldest on overflow
"""

import logging
import time
from dataclasses import dataclass, field

import numpy as np

from edge.camera.capture import FramePacket
from edge.inference.vehicle_detector import VehicleDetector, VehicleDetection
from edge.inference.plate_detector import PlateDetector, PlateDetection
from edge.inference.ocr import PlateOCR, OCRResult
from edge.inference.classifier import VehicleClassifier, VehicleClassification
from edge.inference.tracker import Tracker, Track

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

    Controls the cadence of each inference stage to stay within
    GPU budget. Supports dynamic FPS adjustment for thermal throttling.
    """

    def __init__(self, config: dict):
        # Target FPS for vehicle detection (adjustable for thermal)
        self.target_det_fps = config.get("vehicle_detection_fps", 15)
        self._current_det_fps = self.target_det_fps
        self._min_frame_interval = 1.0 / self._current_det_fps
        self._last_det_time: dict[str, float] = {}

        # Night mode state
        self._night_mode: dict[str, bool] = {}
        self._brightness_threshold = 60

        # Pipeline components (set via set_models)
        self.vehicle_detector: VehicleDetector | None = None
        self.plate_detector: PlateDetector | None = None
        self.ocr: PlateOCR | None = None
        self.classifier: VehicleClassifier | None = None
        self.trackers: dict[str, Tracker] = {}
        self._tracker_config: dict = {}

        # Stats
        self._frames_processed = 0
        self._frames_skipped = 0

    def set_models(
        self,
        vehicle_detector: VehicleDetector,
        plate_detector: PlateDetector,
        ocr: PlateOCR,
        classifier: VehicleClassifier,
        tracker_config: dict,
    ):
        """Attach loaded models to the scheduler."""
        self.vehicle_detector = vehicle_detector
        self.plate_detector = plate_detector
        self.ocr = ocr
        self.classifier = classifier
        self._tracker_config = tracker_config

    def _get_tracker(self, camera_id: str) -> Tracker:
        """Get or create a per-camera tracker."""
        if camera_id not in self.trackers:
            self.trackers[camera_id] = Tracker(self._tracker_config)
        return self.trackers[camera_id]

    def process_frame(self, packet: FramePacket) -> PipelineResult | None:
        """
        Process a single frame through the full inference pipeline.

        Rate-limits vehicle detection to current_det_fps.
        Returns None if frame is skipped (rate limiting).
        """
        now = time.monotonic()
        cam_id = packet.camera_id

        # Rate limiting: skip if too soon since last detection
        last_time = self._last_det_time.get(cam_id, 0.0)
        if (now - last_time) < self._min_frame_interval:
            self._frames_skipped += 1
            return None

        self._last_det_time[cam_id] = now
        t_start = now

        result = PipelineResult(
            camera_id=cam_id,
            timestamp=packet.timestamp,
            frame_number=packet.frame_number,
        )

        frame = packet.frame

        # Check night mode via histogram brightness
        result.night_mode = self._check_night_mode(cam_id, frame)

        # Stage 1: Vehicle detection (full frame)
        if self.vehicle_detector is not None:
            result.vehicles = self.vehicle_detector.detect(frame)

        # Stage 2: Plate detection (vehicle crops only)
        if self.plate_detector is not None and result.vehicles:
            result.plates = self.plate_detector.detect(frame, result.vehicles)

        # Stage 3: OCR (plates above confidence threshold only)
        if self.ocr is not None and result.plates:
            result.ocr_results = self.ocr.recognize(
                frame, result.plates, night_mode=result.night_mode
            )

        # Stage 4: Tracking
        tracker = self._get_tracker(cam_id)
        if result.vehicles:
            det_arrays = [
                np.array([v.x1, v.y1, v.x2, v.y2, v.confidence])
                for v in result.vehicles
            ]
            result.tracks = tracker.update(det_arrays)
        else:
            result.tracks = tracker.update([])

        # Stage 5: Associate OCR results with tracks
        self._associate_plates_to_tracks(result)

        # Stage 6: Classifier (once per confirmed, unclassified track)
        if self.classifier is not None and not self.classifier.is_suspended:
            for track in result.tracks:
                if track.confirmed and not track.classified:
                    crop = self._crop_track(frame, track)
                    if crop is not None:
                        classification = self.classifier.classify(crop)
                        if classification is not None:
                            result.classifications[track.track_id] = classification
                            track.classified = True

        result.processing_time_ms = (time.monotonic() - t_start) * 1000
        self._frames_processed += 1

        return result

    def _check_night_mode(self, camera_id: str, frame: np.ndarray) -> bool:
        """Determine night mode via histogram brightness threshold."""
        # Sample center region for efficiency
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

    def _associate_plates_to_tracks(self, result: PipelineResult):
        """Match OCR results to the closest track by IoU."""
        for ocr_result in result.ocr_results:
            plate = ocr_result.plate_detection
            vehicle = plate.vehicle_box
            vbox = np.array([vehicle.x1, vehicle.y1, vehicle.x2, vehicle.y2])

            best_track = None
            best_iou = 0.0

            for track in result.tracks:
                iou = self._iou(vbox, track.bbox)
                if iou > best_iou:
                    best_iou = iou
                    best_track = track

            if best_track is not None and best_iou > 0.3:
                # Update track with better-confidence plate
                if ocr_result.confidence > best_track.plate_confidence:
                    best_track.plate_text = ocr_result.text
                    best_track.plate_confidence = ocr_result.confidence

    @staticmethod
    def _crop_track(frame: np.ndarray, track: Track) -> np.ndarray | None:
        """Crop tracked vehicle region from frame."""
        h, w = frame.shape[:2]
        x1 = max(0, int(track.bbox[0]))
        y1 = max(0, int(track.bbox[1]))
        x2 = min(w, int(track.bbox[2]))
        y2 = min(h, int(track.bbox[3]))
        crop = frame[y1:y2, x1:x2]
        if crop.size == 0:
            return None
        return crop

    @staticmethod
    def _iou(box_a: np.ndarray, box_b: np.ndarray) -> float:
        """Compute IoU between two boxes."""
        x1 = max(box_a[0], box_b[0])
        y1 = max(box_a[1], box_b[1])
        x2 = min(box_a[2], box_b[2])
        y2 = min(box_a[3], box_b[3])
        inter = max(0, x2 - x1) * max(0, y2 - y1)
        area_a = (box_a[2] - box_a[0]) * (box_a[3] - box_a[1])
        area_b = (box_b[2] - box_b[0]) * (box_b[3] - box_b[1])
        union = area_a + area_b - inter
        return inter / (union + 1e-6)

    def set_detection_fps(self, fps: int):
        """Dynamically adjust detection FPS (for thermal throttling)."""
        if fps != self._current_det_fps:
            logger.info("Detection FPS adjusted: %d → %d", self._current_det_fps, fps)
            self._current_det_fps = fps
            self._min_frame_interval = 1.0 / fps

    @property
    def stats(self) -> dict:
        return {
            "current_det_fps": self._current_det_fps,
            "frames_processed": self._frames_processed,
            "frames_skipped": self._frames_skipped,
            "active_trackers": len(self.trackers),
        }
