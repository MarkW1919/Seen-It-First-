"""
Vehicle classifier using EfficientNet-Lite0 TensorRT INT8 engine.

Runs ONCE per confirmed track to classify vehicle make/color/year-bucket.
Suspended during thermal throttle level 2.
"""

import logging
import time
from dataclasses import dataclass

import cv2
import numpy as np

from edge.inference.tensorrt_utils import TRTEngine

logger = logging.getLogger(__name__)

# Coarse year buckets (exact year not feasible at this resolution)
YEAR_BUCKETS = ["pre-2000", "2000-2005", "2006-2010", "2011-2015", "2016-2020", "2021+"]

# Basic color classes
COLORS = [
    "black", "white", "silver", "gray", "red", "blue",
    "green", "yellow", "brown", "orange", "other",
]


@dataclass
class VehicleClassification:
    """Classification result for a tracked vehicle."""
    color: str
    color_confidence: float
    year_bucket: str
    year_confidence: float


class VehicleClassifier:
    """
    EfficientNet-Lite0 vehicle classifier.

    Phase 1: Uses pretrained EfficientNet-Lite0. No custom training required.
    Fine-tuning pipeline deferred to Phase 3.

    Model: EfficientNet-Lite0 pretrained → TensorRT INT8
    Input: 224x224 RGB
    Engine size: ~5 MB
    VRAM footprint: ~15 MB

    Classifies: color, coarse year bucket.
    Runs once per confirmed track (not every frame).
    """

    def __init__(self, config: dict):
        self.model_path = config["model_path"]
        self.input_size = config.get("input_size", 224)
        self.engine = TRTEngine(self.model_path)
        self._inference_time_ms = 0.0
        self._suspended = False

    def load(self) -> bool:
        return self.engine.load()

    def classify(self, vehicle_crop: np.ndarray) -> VehicleClassification | None:
        """
        Classify a vehicle crop.

        Args:
            vehicle_crop: BGR image of the vehicle region.

        Returns:
            VehicleClassification or None if suspended/failed.
        """
        if self._suspended:
            return None

        if vehicle_crop.size == 0:
            return None

        blob = self._preprocess(vehicle_crop)

        t0 = time.monotonic()
        outputs = self.engine.infer(blob)
        self._inference_time_ms = (time.monotonic() - t0) * 1000

        return self._postprocess(outputs)

    def _preprocess(self, crop: np.ndarray) -> np.ndarray:
        """Resize and normalize for EfficientNet input."""
        resized = cv2.resize(crop, (self.input_size, self.input_size))
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        blob = rgb.astype(np.float32) / 255.0
        # ImageNet normalization
        mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
        std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
        blob = (blob - mean) / std
        blob = blob.transpose(2, 0, 1)
        blob = np.expand_dims(blob, axis=0)
        return np.ascontiguousarray(blob)

    def _postprocess(self, outputs: list[np.ndarray]) -> VehicleClassification:
        """
        Parse classifier outputs.

        Expects two output heads:
        - outputs[0]: color logits [1, num_colors]
        - outputs[1]: year bucket logits [1, num_year_buckets]
        """
        # Color prediction
        if len(outputs) >= 1:
            color_logits = outputs[0].flatten()
            color_probs = self._softmax(color_logits)
            color_idx = int(np.argmax(color_probs))
            color = COLORS[color_idx] if color_idx < len(COLORS) else "other"
            color_conf = float(color_probs[color_idx])
        else:
            color, color_conf = "unknown", 0.0

        # Year bucket prediction
        if len(outputs) >= 2:
            year_logits = outputs[1].flatten()
            year_probs = self._softmax(year_logits)
            year_idx = int(np.argmax(year_probs))
            year_bucket = YEAR_BUCKETS[year_idx] if year_idx < len(YEAR_BUCKETS) else "unknown"
            year_conf = float(year_probs[year_idx])
        else:
            year_bucket, year_conf = "unknown", 0.0

        return VehicleClassification(
            color=color,
            color_confidence=color_conf,
            year_bucket=year_bucket,
            year_confidence=year_conf,
        )

    @staticmethod
    def _softmax(x: np.ndarray) -> np.ndarray:
        e = np.exp(x - np.max(x))
        return e / e.sum()

    def suspend(self):
        """Suspend classifier (thermal protection)."""
        if not self._suspended:
            logger.warning("Vehicle classifier SUSPENDED (thermal)")
            self._suspended = True

    def resume(self):
        """Resume classifier after thermal recovery."""
        if self._suspended:
            logger.info("Vehicle classifier RESUMED")
            self._suspended = False

    @property
    def is_suspended(self) -> bool:
        return self._suspended

    @property
    def inference_time_ms(self) -> float:
        return self._inference_time_ms

    def release(self):
        self.engine.release()
