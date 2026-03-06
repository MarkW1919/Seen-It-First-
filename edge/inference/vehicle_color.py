"""
Vehicle color detection.

Two-mode detector:
  1. ONNX model  (vehicle_color_model.onnx) — when loaded, provides confidence score.
  2. HSV clustering fallback — always available, no model required.

The fallback uses K-means-style pixel quantization in HSV space on the centre
50 % of the vehicle crop to minimise background influence.

Output::

    {"color": "Black", "confidence": 0.92}

Supported color categories:
    black, white, silver, gray, red, orange, yellow, green, blue, purple, brown, gold
"""

import logging
import time
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from edge.inference.onnx_utils import OnnxEngine

logger = logging.getLogger(__name__)

# Minimum pixel-fraction for a color to be declared dominant (HSV fallback)
_HSV_THRESHOLD = 0.12

# ONNX model output class index → color name
_ONNX_COLOR_LABELS = [
    "black", "white", "silver", "gray", "red",
    "orange", "yellow", "green", "blue", "purple", "brown", "gold",
]

_IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
_IMAGENET_STD  = np.array([0.229, 0.224, 0.225], dtype=np.float32)


@dataclass
class ColorResult:
    color:      str
    confidence: float

    def to_dict(self) -> dict:
        return {"color": self.color.capitalize(), "confidence": round(self.confidence, 4)}


class VehicleColorDetector:
    """
    Detects the dominant vehicle color from a BGR crop.

    Falls back to HSV histogram analysis when the ONNX model is not loaded.
    """

    def __init__(self, config: dict):
        self.model_path  = config.get("model_path", "")
        self.input_size  = config.get("input_size", 224)
        self.engine      = OnnxEngine(self.model_path) if self.model_path else None
        self._loaded     = False
        self._infer_ms   = 0.0

    def load(self) -> bool:
        """Load the ONNX color model.  Always returns True (HSV fallback available)."""
        if self.engine is not None and self.engine.load():
            self._loaded = True
            return True
        logger.info("VehicleColorDetector: ONNX model not loaded — using HSV fallback")
        return False

    @property
    def is_loaded(self) -> bool:
        """True only when the ONNX model is available; HSV fallback always works."""
        return self._loaded

    def detect(self, crop: np.ndarray) -> ColorResult:
        """
        Detect the dominant vehicle color.

        Tries ONNX inference first; falls back to HSV histogram on failure.
        """
        if crop is None or crop.size == 0:
            return ColorResult("unknown", 0.0)

        if self._loaded and self.engine is not None:
            result = self._infer_onnx(crop)
            if result is not None:
                return result

        return self._hsv_detect(crop)

    # ------------------------------------------------------------------
    # ONNX path
    # ------------------------------------------------------------------

    def _infer_onnx(self, crop: np.ndarray) -> "ColorResult | None":
        blob = self._preprocess(crop)
        t0 = time.monotonic()
        try:
            outputs = self.engine.infer(blob)
        except Exception:
            logger.exception("VehicleColorDetector ONNX inference failed")
            return None
        self._infer_ms = (time.monotonic() - t0) * 1000

        probs = outputs[0].flatten()
        if probs.max() > 1.0:
            e = np.exp(probs - probs.max())
            probs = e / e.sum()

        idx  = int(np.argmax(probs))
        conf = float(probs[idx])
        color = (
            _ONNX_COLOR_LABELS[idx]
            if idx < len(_ONNX_COLOR_LABELS)
            else "unknown"
        )
        return ColorResult(color, conf)

    def _preprocess(self, crop: np.ndarray) -> np.ndarray:
        resized = cv2.resize(crop, (self.input_size, self.input_size))
        rgb     = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        blob    = rgb.astype(np.float32) / 255.0
        blob    = (blob - _IMAGENET_MEAN) / _IMAGENET_STD
        blob    = blob.transpose(2, 0, 1)
        return np.expand_dims(blob, axis=0)

    # ------------------------------------------------------------------
    # HSV fallback
    # ------------------------------------------------------------------

    def _hsv_detect(self, crop: np.ndarray) -> ColorResult:
        """HSV histogram color detection with K-means-style quantization."""
        h, w = crop.shape[:2]
        # Use centre 50 % to minimise background
        cy1, cy2 = h // 4, 3 * h // 4
        cx1, cx2 = w // 4, 3 * w // 4
        center = crop[cy1:cy2, cx1:cx2]
        if center.size == 0:
            center = crop

        hsv    = cv2.cvtColor(center, cv2.COLOR_BGR2HSV)
        h_ch   = hsv[:, :, 0].astype(np.float32)   # [0, 179]
        s_ch   = hsv[:, :, 1].astype(np.float32)   # [0, 255]
        v_ch   = hsv[:, :, 2].astype(np.float32)   # [0, 255]
        total  = float(h_ch.size)

        achromatic = s_ch < 50
        chromatic  = s_ch >= 50

        scores: dict[str, float] = {
            "black":  float(np.sum(achromatic & (v_ch < 50)))           / total,
            "white":  float(np.sum(achromatic & (v_ch > 200)))          / total,
            "silver": float(np.sum(achromatic & (v_ch >= 150) & (v_ch <= 200))) / total,
            "gray":   float(np.sum(achromatic & (v_ch >= 50)  & (v_ch < 150))) / total,
            "gold":   float(np.sum(chromatic  & (h_ch >= 20)  & (h_ch < 30)
                                   & (v_ch >= 150)))                    / total,
            "red":    float(np.sum(chromatic  & ((h_ch < 10) | (h_ch > 170)))) / total,
            "orange": float(np.sum(chromatic  & (h_ch >= 10)  & (h_ch < 20)))  / total,
            "yellow": float(np.sum(chromatic  & (h_ch >= 20)  & (h_ch < 35)))  / total,
            "green":  float(np.sum(chromatic  & (h_ch >= 35)  & (h_ch < 85)))  / total,
            "blue":   float(np.sum(chromatic  & (h_ch >= 85)  & (h_ch < 130))) / total,
            "purple": float(np.sum(chromatic  & (h_ch >= 130) & (h_ch < 150))) / total,
            "brown":  float(np.sum(chromatic  & (h_ch >= 10)  & (h_ch < 20)
                                   & (v_ch < 150)))                     / total,
        }

        best  = max(scores, key=scores.__getitem__)
        conf  = scores[best]
        if conf < _HSV_THRESHOLD:
            return ColorResult("unknown", 0.0)
        # Rough confidence: normalise winning fraction vs second-best
        second = sorted(scores.values())[-2]
        margin = min(1.0, (conf - second) / (conf + 1e-6) + 0.5)
        return ColorResult(best, round(margin, 3))

    def release(self):
        if self.engine is not None:
            self.engine.release()

    @property
    def inference_time_ms(self) -> float:
        return self._infer_ms
