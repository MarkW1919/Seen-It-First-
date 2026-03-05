"""
Vehicle classifier using YOLOv8n-cls TensorRT FP16 engine.

Runs ONCE per confirmed track to classify vehicle type.
Suspended during thermal throttle level 2.

Model: YOLOv8n-cls (ImageNet pretrained) → ONNX → TensorRT FP16
Input: [1, 3, 224, 224] RGB, ImageNet normalisation
Output: [1, 1000] class probabilities (ImageNet)
Engine size: ~5 MB
VRAM footprint: ~15 MB
"""

import logging
import time
from dataclasses import dataclass, field

import cv2
import numpy as np

from edge.inference.tensorrt_utils import TRTEngine

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# ImageNet class index → vehicle type mapping
# Selected from ImageNet 1000-class taxonomy (vehicle-relevant classes only).
# Non-vehicle or ambiguous classes map to "vehicle" as a safe fallback.
# ---------------------------------------------------------------------------
_IMAGENET_TO_VEHICLE_TYPE: dict[int, str] = {
    407: "ambulance",
    436: "station_wagon",
    468: "cab",
    511: "convertible",
    555: "fire_truck",
    569: "go_kart",
    609: "jeep",
    627: "limousine",
    656: "minibus",
    661: "minivan",
    675: "moving_van",
    717: "pickup_truck",
    734: "police_van",
    757: "sports_car",
    779: "recreational_vehicle",
    817: "sports_car",
    820: "streetcar",
    864: "tow_truck",
    867: "semi_truck",
    873: "bus",
    897: "van",
    # Motorcycles
    665: "motorcycle",
    # Generic car classes
    817: "sports_car",
    # Sedans / coupes fall through to default below
}
_DEFAULT_VEHICLE_TYPE = "vehicle"

# Coarse year buckets — retained for backwards compatibility
YEAR_BUCKETS = ["pre-2000", "2000-2005", "2006-2010", "2011-2015", "2016-2020", "2021+"]

# Basic color classes — retained for backwards compatibility
COLORS = [
    "black", "white", "silver", "gray", "red", "blue",
    "green", "yellow", "brown", "orange", "other",
]

# ImageNet normalisation
_IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
_IMAGENET_STD  = np.array([0.229, 0.224, 0.225], dtype=np.float32)


@dataclass
class VehicleClassification:
    """Classification result for a tracked vehicle."""
    color: str
    color_confidence: float
    year_bucket: str
    year_confidence: float
    vehicle_class: str = field(default="unknown")
    class_confidence: float = field(default=0.0)

    def to_dict(self) -> dict:
        return {
            "class": self.vehicle_class,
            "confidence": round(self.class_confidence, 4),
        }


class VehicleClassifier:
    """
    YOLOv8n-cls vehicle type classifier.

    Phase 1: Uses pretrained YOLOv8n-cls (ImageNet). No custom training.
    ImageNet class indices are mapped to coarse vehicle types at runtime.
    Fine-tuning pipeline deferred to Phase 3.

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

    @property
    def is_loaded(self) -> bool:
        return self.engine.is_loaded

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
        """Resize and apply ImageNet normalisation for YOLOv8n-cls input."""
        resized = cv2.resize(crop, (self.input_size, self.input_size))
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        blob = rgb.astype(np.float32) / 255.0
        blob = (blob - _IMAGENET_MEAN) / _IMAGENET_STD
        blob = blob.transpose(2, 0, 1)      # HWC → CHW
        blob = np.expand_dims(blob, axis=0) # → NCHW
        return np.ascontiguousarray(blob)

    def _postprocess(self, outputs: list[np.ndarray]) -> VehicleClassification:
        """
        Parse YOLOv8n-cls output.

        YOLOv8n-cls output shape: [1, 1000] (ImageNet class logits/probs).
        Maps the top-1 ImageNet class to a vehicle type label.

        color / year_bucket fields are set to "unknown" — YOLOv8n-cls does
        not provide colour or year information in Phase 1.
        """
        logits = outputs[0].flatten()
        probs = self._softmax(logits)
        top_idx = int(np.argmax(probs))
        top_conf = float(probs[top_idx])

        vehicle_type = _IMAGENET_TO_VEHICLE_TYPE.get(top_idx, _DEFAULT_VEHICLE_TYPE)

        return VehicleClassification(
            color="unknown",
            color_confidence=0.0,
            year_bucket="unknown",
            year_confidence=0.0,
            vehicle_class=vehicle_type,
            class_confidence=top_conf,
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
