"""Best-evidence selector for multi-camera OCR detections.

Selects the highest-quality detection candidate among cameras for the same
plate text in a short time window.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import cv2
import numpy as np


@dataclass
class EvidenceCandidate:
    camera_id: str
    plate_text: str
    plate_confidence: float
    vehicle_confidence: float
    plate_bbox: tuple[int, int, int, int]
    frame: np.ndarray
    night_mode: bool = False


class BestEvidenceSelector:
    """Ranks candidates and returns one best candidate per plate text."""

    def __init__(self, config: dict | None = None):
        cfg = config or {}
        self.weight_ocr = float(cfg.get("weight_ocr", 0.45))
        self.weight_plate_area = float(cfg.get("weight_plate_area", 0.20))
        self.weight_sharpness = float(cfg.get("weight_sharpness", 0.20))
        self.weight_exposure = float(cfg.get("weight_exposure", 0.10))
        self.night_bonus = float(cfg.get("night_bonus", 0.05))

    def choose_best(self, candidates: Iterable[EvidenceCandidate]) -> dict[str, EvidenceCandidate]:
        grouped: dict[str, list[EvidenceCandidate]] = {}
        for c in candidates:
            key = c.plate_text.upper().strip()
            if not key:
                continue
            grouped.setdefault(key, []).append(c)

        winners: dict[str, EvidenceCandidate] = {}
        for plate_text, items in grouped.items():
            winners[plate_text] = max(items, key=self._score)
        return winners

    def _score(self, c: EvidenceCandidate) -> float:
        x1, y1, x2, y2 = c.plate_bbox
        h, w = c.frame.shape[:2]

        # Plate area score (relative to frame)
        plate_area = max(1, (x2 - x1) * (y2 - y1))
        frame_area = max(1, h * w)
        area_score = min(1.0, plate_area / (frame_area * 0.08))

        crop = c.frame[max(0, y1):min(h, y2), max(0, x1):min(w, x2)]
        if crop.size == 0:
            sharpness = 0.0
            exposure = 0.0
        else:
            gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
            lap_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
            sharpness = min(1.0, lap_var / 500.0)
            mean_luma = float(np.mean(gray))
            # ideal-ish plate luminance center ~120, penalize extremes
            exposure = max(0.0, 1.0 - abs(mean_luma - 120.0) / 120.0)

        score = (
            self.weight_ocr * c.plate_confidence
            + self.weight_plate_area * area_score
            + self.weight_sharpness * sharpness
            + self.weight_exposure * exposure
            + (self.night_bonus if c.night_mode else 0.0)
        )
        return float(score)
