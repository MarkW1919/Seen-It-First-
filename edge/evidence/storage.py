"""
Evidence storage: persists detection metadata and snapshot paths to SQLite.

EvidenceStorage wraps DetectionRepository so the fusion engine can record
confirmed detections (with evidence image paths) without importing the full
PipelineResult type.
"""

import logging
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from edge.storage.repository import DetectionRepository

logger = logging.getLogger(__name__)


class EvidenceStorage:
    """
    Thin wrapper around DetectionRepository for evidence-triggered DB writes.

    Usage::

        storage = EvidenceStorage(repo)
        storage.store_detection(
            vehicle_path="data/evidence/vehicles/…/vehicle_…jpg",
            plate_path="data/evidence/plates/…/plate_ABC123_….jpg",
            composite_path="data/evidence/composite/…/detect_….jpg",
            plate_text="ABC123",
            vehicle_class="car",
            confidence=0.94,
            camera_id="cam1",
            track_id=7,
            bbox=[120, 200, 640, 580],
        )
    """

    def __init__(self, repo: "DetectionRepository"):
        self._repo = repo

    def store_detection(
        self,
        vehicle_path:   str,
        plate_path:     str,
        composite_path: str,
        plate_text:     str,
        vehicle_class:  str,
        confidence:     float,
        camera_id:      str,
        track_id:       int | None = None,
        bbox:           list[float] | None = None,
        night_mode:     bool = False,
        make:           str = "",
        model:          str = "",
        color:          str = "",
        year_range:     str = "",
        latitude:       float = 0.0,
        longitude:      float = 0.0,
    ) -> int:
        """
        Insert a confirmed detection record into the database.

        Args:
            vehicle_path:   Path to the vehicle crop JPEG.
            plate_path:     Path to the plate crop JPEG.
            composite_path: Path to the composite (annotated) JPEG.
            plate_text:     Confirmed plate text.
            vehicle_class:  Vehicle type string (car, truck, …).
            confidence:     Plate OCR confidence (0–1).
            camera_id:      Camera that produced the detection.
            track_id:       DeepSORT track ID (optional).
            bbox:           Vehicle bounding box [x1, y1, x2, y2] (optional).
            night_mode:     Whether night enhancement was applied.

        Returns:
            Row ID of the inserted detections record.
        """
        bbox_i = tuple(int(v) for v in bbox[:4]) if bbox else (0, 0, 0, 0)

        try:
            row_id = self._repo.save_evidence_detection(
                timestamp=time.time(),
                camera_id=camera_id,
                track_id=track_id,
                plate_text=plate_text,
                plate_confidence=confidence,
                vehicle_class=vehicle_class,
                bbox=bbox_i,
                vehicle_path=vehicle_path,
                plate_path=plate_path,
                composite_path=composite_path,
                night_mode=night_mode,
                make=make,
                model=model,
                color=color,
                year_range=year_range,
                confidence=confidence,
                latitude=latitude,
                longitude=longitude,
            )
            logger.debug(
                "Evidence stored: row=%d plate=%s cam=%s vehicle=%s",
                row_id, plate_text, camera_id, vehicle_path,
            )
            return row_id
        except Exception:
            logger.exception(
                "Failed to store evidence detection: plate=%s cam=%s",
                plate_text, camera_id,
            )
            return -1
