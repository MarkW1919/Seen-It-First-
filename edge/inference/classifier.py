"""
Vehicle classifier using YOLOv8n-cls TensorRT FP16 engine.

Returns a rich VehicleClassification with vehicle_type, make, model, color,
year_range, and confidence.  Color is detected via HSV histogram analysis on
the vehicle crop.  Make, model, and year_range are "unknown" in Phase 1
(ImageNet pretrained model only — custom training deferred to Phase 3).

Model: YOLOv8n-cls (ImageNet pretrained) → ONNX → TensorRT FP16
Input: [1, 3, 224, 224] RGB, ImageNet normalisation
Output: [1, 1000] class probabilities (ImageNet)
Engine size: ~5 MB
VRAM footprint: ~15 MB
"""

import logging
import time
from dataclasses import dataclass

import cv2
import numpy as np

from edge.inference.tensorrt_utils import TRTEngine

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# ImageNet class index → vehicle type mapping
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
    665: "motorcycle",
    675: "moving_van",
    717: "pickup",
    734: "police_van",
    757: "sports_car",
    779: "recreational_vehicle",
    817: "sports_car",
    820: "streetcar",
    864: "tow_truck",
    867: "semi_truck",
    873: "bus",
    897: "van",
}
_DEFAULT_VEHICLE_TYPE = "vehicle"

# ImageNet normalisation
_IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
_IMAGENET_STD  = np.array([0.229, 0.224, 0.225], dtype=np.float32)

# Minimum pixel fraction for a color to be considered dominant
_COLOR_THRESHOLD = 0.12


@dataclass
class VehicleClassification:
    """Rich classification result for a tracked vehicle."""
    vehicle_type: str
    make:         str
    model:        str
    color:        str
    year_range:   str
    confidence:   float

    # ── Backward-compat properties used by existing pipeline/scheduler code ──
    @property
    def vehicle_class(self) -> str:
        return self.vehicle_type

    @property
    def class_confidence(self) -> float:
        return self.confidence

    def to_dict(self) -> dict:
        return {
            "vehicle_type": self.vehicle_type,
            "make":         self.make,
            "model":        self.model,
            "color":        self.color,
            "year_range":   self.year_range,
            "confidence":   round(self.confidence, 4),
        }


class VehicleClassifier:
    """
    YOLOv8n-cls vehicle type classifier with HSV color detection.

    Phase 1: ImageNet pretrained YOLOv8n-cls maps top-1 class to a coarse
    vehicle type.  Color is derived from HSV histograms on the vehicle crop.
    Make, model, and year_range are "unknown" until Phase 3 fine-tuning.

    Runs once per confirmed track; result cached by InferencePipeline.
    Suspended during thermal throttle level 2.
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

    def classify(self, vehicle_crop: np.ndarray) -> "VehicleClassification | None":
        """
        Classify a vehicle crop.

        Runs the TRT engine for vehicle type, and HSV analysis for color.

        Args:
            vehicle_crop: BGR image of the vehicle region.

        Returns:
            VehicleClassification or None if suspended/failed.
        """
        if self._suspended:
            return None
        if vehicle_crop is None or vehicle_crop.size == 0:
            return None

        # Detect color from the raw crop before normalisation
        color = _detect_color(vehicle_crop)

        blob = self._preprocess(vehicle_crop)

        t0 = time.monotonic()
        outputs = self.engine.infer(blob)
        self._inference_time_ms = (time.monotonic() - t0) * 1000

        return self._postprocess(outputs, color)

    def _preprocess(self, crop: np.ndarray) -> np.ndarray:
        resized = cv2.resize(crop, (self.input_size, self.input_size))
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        blob = rgb.astype(np.float32) / 255.0
        blob = (blob - _IMAGENET_MEAN) / _IMAGENET_STD
        blob = blob.transpose(2, 0, 1)
        blob = np.expand_dims(blob, axis=0)
        return np.ascontiguousarray(blob)

    def _postprocess(self, outputs: list[np.ndarray], color: str) -> VehicleClassification:
        logits = outputs[0].flatten()
        probs = _softmax(logits)
        top_idx = int(np.argmax(probs))
        top_conf = float(probs[top_idx])
        vehicle_type = _IMAGENET_TO_VEHICLE_TYPE.get(top_idx, _DEFAULT_VEHICLE_TYPE)

        return VehicleClassification(
            vehicle_type=vehicle_type,
            make="unknown",
            model="unknown",
            color=color,
            year_range="unknown",
            confidence=top_conf,
        )

    def suspend(self):
        if not self._suspended:
            logger.warning("Vehicle classifier SUSPENDED (thermal)")
            self._suspended = True

    def resume(self):
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


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

def _detect_color(crop: np.ndarray) -> str:
    """
    Estimate dominant vehicle color from a BGR crop using HSV histograms.

    Uses the centre 50 % of the crop to reduce background influence.
    Returns a color name or "unknown" if no color meets the threshold.
    """
    if crop.size == 0:
        return "unknown"

    h, w = crop.shape[:2]
    # Centre 50 % horizontally and vertically
    cy1, cy2 = h // 4, 3 * h // 4
    cx1, cx2 = w // 4, 3 * w // 4
    center = crop[cy1:cy2, cx1:cx2]
    if center.size == 0:
        center = crop

    hsv = cv2.cvtColor(center, cv2.COLOR_BGR2HSV)
    h_ch = hsv[:, :, 0].astype(np.float32)   # [0, 179]
    s_ch = hsv[:, :, 1].astype(np.float32)   # [0, 255]
    v_ch = hsv[:, :, 2].astype(np.float32)   # [0, 255]
    total = float(h_ch.size)

    # Achromatic pixels (low saturation)
    achromatic = s_ch < 50
    chromatic  = s_ch >= 50

    scores: dict[str, float] = {
        "black":  float(np.sum(achromatic & (v_ch < 50)))  / total,
        "white":  float(np.sum(achromatic & (v_ch > 200))) / total,
        "silver": float(np.sum(achromatic & (v_ch >= 150) & (v_ch <= 200))) / total,
        "gray":   float(np.sum(achromatic & (v_ch >= 50)  & (v_ch < 150))) / total,
        # Chromatic — hue ranges in HSV (0-179 scale in OpenCV)
        "red":    float(np.sum(chromatic & ((h_ch < 10) | (h_ch > 170)))) / total,
        "orange": float(np.sum(chromatic & (h_ch >= 10) & (h_ch < 20)))   / total,
        "yellow": float(np.sum(chromatic & (h_ch >= 20) & (h_ch < 35)))   / total,
        "green":  float(np.sum(chromatic & (h_ch >= 35) & (h_ch < 85)))   / total,
        "blue":   float(np.sum(chromatic & (h_ch >= 85) & (h_ch < 130)))  / total,
        "purple": float(np.sum(chromatic & (h_ch >= 130) & (h_ch < 150))) / total,
        "brown":  float(np.sum(chromatic & (h_ch >= 10)  & (h_ch < 20) & (v_ch < 150))) / total,
    }

    best_color = max(scores, key=scores.__getitem__)
    return best_color if scores[best_color] >= _COLOR_THRESHOLD else "unknown"


def _softmax(x: np.ndarray) -> np.ndarray:
    e = np.exp(x - np.max(x))
    return e / e.sum()
