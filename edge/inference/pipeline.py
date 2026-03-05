"""
Unified AI detection pipeline for Seen-It-First edge node.

InferencePipeline orchestrates every AI stage in sequence for a single
camera frame and feeds confirmed detections into the fusion engine.

Stage order (all on Jetson GPU via TensorRT FP16):
    1. Vehicle detection        — YOLOv8n, full frame, ~8 ms
    2. Tracking                 — DeepSORT-lite, IoU + embedding, ~1 ms
    3. Vehicle classification   — YOLOv8n-cls, per confirmed track, ~4 ms
    4. Plate detection          — YOLOv8s, vehicle crops, ~6 ms
    5. OCR                      — PP-OCRv4, plate crops, ~10 ms
    6. Plate ↔ track fusion     — DetectionFusionEngine, ~0.5 ms

Total target: < 30 ms per frame on Jetson Orin Nano Super.
"""

import logging
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

from edge.camera.capture import FramePacket
from edge.inference.scheduler import PipelineResult
from edge.inference.tracker import Tracker
from edge.inference.vehicle_detector import VehicleDetector
from edge.inference.plate_detector import PlateDetector
from edge.inference.ocr import PlateOCR
from edge.inference.classifier import VehicleClassifier

if TYPE_CHECKING:
    from edge.inference.fusion import DetectionFusionEngine
    from edge.inference.events import EventPublisher

logger = logging.getLogger(__name__)


@dataclass
class Detection:
    """
    A fully resolved vehicle detection fused across multiple pipeline stages.

    Produced by InferencePipeline.process_frame() for every confirmed track
    and forwarded to DetectionFusionEngine for multi-frame plate confirmation.
    """
    track_id:      int
    camera_id:     str
    bbox:          list[float]    # [x1, y1, x2, y2] in pixel space
    vehicle_class: str
    vehicle_conf:  float
    plate_text:    str
    plate_conf:    float
    timestamp:     float


class InferencePipeline:
    """
    Runs all AI inference stages for one camera frame and routes results
    to the fusion engine and event publisher.

    One InferencePipeline instance is shared across all cameras via the
    InferenceScheduler.  Per-camera state (trackers) is managed internally.

    Usage::

        pipeline = InferencePipeline(
            vehicle_detector=vd,
            plate_detector=pd,
            ocr=ocr,
            classifier=clf,
            tracker_config=tracker_cfg,
            fusion_engine=fusion,
            event_publisher=publisher,
        )
        result = pipeline.process_frame(frame_packet, night_mode=False)
        # result is a PipelineResult (backward-compatible with scheduler API)
    """

    def __init__(
        self,
        vehicle_detector: VehicleDetector,
        plate_detector: PlateDetector,
        ocr: PlateOCR,
        classifier: VehicleClassifier,
        tracker_config: dict,
        fusion_engine: "DetectionFusionEngine",
        event_publisher: "EventPublisher",
    ):
        self.vehicle_detector = vehicle_detector
        self.plate_detector   = plate_detector
        self.ocr              = ocr
        self.classifier       = classifier
        self._tracker_config  = tracker_config
        self._fusion          = fusion_engine
        self._publisher       = event_publisher

        # Per-camera DeepSORT trackers
        self.trackers: dict[str, Tracker] = {}

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def process_frame(
        self,
        packet: FramePacket,
        night_mode: bool = False,
    ) -> PipelineResult:
        """
        Run all inference stages on a single frame.

        Args:
            packet:     Frame captured by CameraCapture (includes frame array,
                        camera_id, timestamp, frame_number).
            night_mode: Whether the camera reports low-light conditions;
                        enables CLAHE plate enhancement.

        Returns:
            PipelineResult — same structure the InferenceScheduler returned
            before the pipeline refactor, so main.py is unchanged.
        """
        t_start = time.monotonic()
        cam_id = packet.camera_id
        frame  = packet.frame

        result = PipelineResult(
            camera_id=cam_id,
            timestamp=packet.timestamp,
            frame_number=packet.frame_number,
            night_mode=night_mode,
        )

        # ── Stage 1: Vehicle detection ─────────────────────────────────
        t0 = time.monotonic()
        if self.vehicle_detector is not None and self.vehicle_detector.is_loaded:
            result.vehicles = self.vehicle_detector.detect(frame)
        t_vd = (time.monotonic() - t0) * 1000

        # ── Stage 2: Tracking ──────────────────────────────────────────
        tracker = self._get_tracker(cam_id)
        if result.vehicles:
            det_arrays = [
                np.array([v.x1, v.y1, v.x2, v.y2, v.confidence])
                for v in result.vehicles
            ]
            result.tracks = tracker.update(det_arrays)
        else:
            result.tracks = tracker.update([])

        # ── Stage 3: Vehicle classification ───────────────────────────
        t0 = time.monotonic()
        if (
            self.classifier is not None
            and self.classifier.is_loaded
            and not self.classifier.is_suspended
        ):
            for track in result.tracks:
                if track.confirmed and not track.classified:
                    crop = _crop_track(frame, track)
                    if crop is not None:
                        clf_result = self.classifier.classify(crop)
                        if clf_result is not None:
                            result.classifications[track.track_id] = clf_result
                            track.classified = True
                            if hasattr(clf_result, "vehicle_class"):
                                track.class_name = clf_result.vehicle_class
        t_clf = (time.monotonic() - t0) * 1000

        # ── Stage 4: Plate detection (vehicle crops only) ─────────────
        t0 = time.monotonic()
        if (
            self.plate_detector is not None
            and self.plate_detector.is_loaded
            and result.vehicles
        ):
            result.plates = self.plate_detector.detect(frame, result.vehicles)
        t_pd = (time.monotonic() - t0) * 1000

        # ── Stage 5: OCR (plates above confidence threshold) ──────────
        t0 = time.monotonic()
        if self.ocr is not None and self.ocr.is_loaded and result.plates:
            result.ocr_results = self.ocr.recognize(
                frame, result.plates, night_mode=night_mode
            )
        t_ocr = (time.monotonic() - t0) * 1000

        # ── Stage 5a: Associate OCR results back to tracks (IoU) ──────
        self._associate_plates_to_tracks(result)

        # ── Stage 6: Build Detection objects → fusion engine ──────────
        for track in result.tracks:
            if not track.confirmed:
                continue
            clf = result.classifications.get(track.track_id)
            detection = Detection(
                track_id=track.track_id,
                camera_id=cam_id,
                bbox=track.bbox.tolist(),
                vehicle_class=track.class_name or (clf.vehicle_class if clf else ""),
                vehicle_conf=float(track.bbox[4]) if len(track.bbox) > 4 else 0.0,
                plate_text=track.plate_text,
                plate_conf=track.plate_confidence,
                timestamp=packet.timestamp,
            )
            self._fusion.add_detection(detection)

        result.processing_time_ms = (time.monotonic() - t_start) * 1000

        if result.vehicles:
            logger.debug(
                "cam=%s vehicles=%d plates=%d ocr=%d tracks=%d "
                "vd=%.1fms pd=%.1fms ocr=%.1fms clf=%.1fms total=%.1fms",
                cam_id,
                len(result.vehicles),
                len(result.plates),
                len(result.ocr_results),
                len(result.tracks),
                t_vd, t_pd, t_ocr, t_clf,
                result.processing_time_ms,
            )

        return result

    # ------------------------------------------------------------------
    # Tracker management
    # ------------------------------------------------------------------

    def _get_tracker(self, camera_id: str) -> Tracker:
        if camera_id not in self.trackers:
            self.trackers[camera_id] = Tracker(self._tracker_config)
        return self.trackers[camera_id]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _associate_plates_to_tracks(self, result: PipelineResult):
        """Assign OCR results to the nearest track by IoU, keeping best conf."""
        for ocr_result in result.ocr_results:
            plate = ocr_result.plate_detection
            vehicle = plate.vehicle_box
            vbox = np.array([vehicle.x1, vehicle.y1, vehicle.x2, vehicle.y2])

            best_track = None
            best_iou   = 0.0

            for track in result.tracks:
                iou = _iou(vbox, track.bbox)
                if iou > best_iou:
                    best_iou  = iou
                    best_track = track

            if best_track is not None and best_iou > 0.3:
                if ocr_result.confidence > best_track.plate_confidence:
                    best_track.plate_text       = ocr_result.text
                    best_track.plate_confidence = ocr_result.confidence


# ---------------------------------------------------------------------------
# Module-level helpers (no state)
# ---------------------------------------------------------------------------

def _crop_track(frame: np.ndarray, track) -> np.ndarray | None:
    """Crop the tracked vehicle region from a frame with bounds clamping."""
    h, w = frame.shape[:2]
    x1 = max(0, int(track.bbox[0]))
    y1 = max(0, int(track.bbox[1]))
    x2 = min(w, int(track.bbox[2]))
    y2 = min(h, int(track.bbox[3]))
    crop = frame[y1:y2, x1:x2]
    return crop if crop.size > 0 else None


def _iou(box_a: np.ndarray, box_b: np.ndarray) -> float:
    """Compute IoU between two [x1, y1, x2, y2] boxes."""
    x1 = max(box_a[0], box_b[0])
    y1 = max(box_a[1], box_b[1])
    x2 = min(box_a[2], box_b[2])
    y2 = min(box_a[3], box_b[3])
    inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    area_a = (box_a[2] - box_a[0]) * (box_a[3] - box_a[1])
    area_b = (box_b[2] - box_b[0]) * (box_b[3] - box_b[1])
    union = area_a + area_b - inter
    return inter / (union + 1e-6)
