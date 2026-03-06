"""
Vehicle intelligence orchestrator.

VehicleClassifier coordinates four dedicated sub-models to produce a
complete VehicleClassification for each confirmed tracked vehicle:

  1. VehicleClassifierModel  — ONNX make/model/year classifier
  2. VehicleColorDetector    — ONNX or HSV-fallback color detection
  3. VehicleReID             — ONNX 128-dim embedding for fingerprinting
  4. VehicleFingerprintGenerator — combines all outputs into a fingerprint

Sub-models are injected at construction time from edge/main.py so they can
be individually configured, loaded, and tested.  When a sub-model is absent
or not loaded, the corresponding field falls back to "unknown" / "".

Phase 1 performance budget per vehicle (Jetson Orin Nano Super):
  • ONNX classifier:  ~4 ms
  • ONNX color:       ~2 ms
  • ONNX reid:        ~3 ms
  • HSV fallback:     ~0.5 ms
  • Fingerprint gen:  ~0.1 ms
  Total target:       ≤ 35 ms (well within budget when using GPU ONNX session)
"""

import logging
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import cv2
import numpy as np

from edge.inference.vehicle_fingerprint import VehicleFingerprintGenerator

if TYPE_CHECKING:
    from edge.inference.vehicle_classifier import VehicleClassifierModel, ClassifierResult
    from edge.inference.vehicle_color import VehicleColorDetector
    from edge.inference.vehicle_reid import VehicleReID

logger = logging.getLogger(__name__)

# ImageNet normalisation for the TRT-based fallback path
_IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
_IMAGENET_STD  = np.array([0.229, 0.224, 0.225], dtype=np.float32)

# Minimum pixel fraction for HSV color to be declared dominant (fallback)
_HSV_THRESHOLD = 0.12

# ImageNet class index → vehicle type (TRT fallback when ONNX clf not loaded)
_IMAGENET_TO_VEHICLE_TYPE: dict[int, str] = {
    407: "ambulance",   436: "station_wagon", 468: "cab",
    511: "convertible", 555: "fire_truck",    609: "jeep",
    627: "limousine",   656: "minibus",       661: "minivan",
    665: "motorcycle",  675: "moving_van",    717: "pickup",
    734: "police_van",  757: "sports_car",    779: "recreational_vehicle",
    817: "sports_car",  820: "streetcar",     864: "tow_truck",
    867: "semi_truck",  873: "bus",           897: "van",
}


@dataclass
class VehicleClassification:
    """
    Complete vehicle intelligence result for a single tracked vehicle.

    Produced by VehicleClassifier.classify() and stored in the pipeline's
    per-track classification cache.
    """
    vehicle_type: str
    make:         str
    model:        str
    color:        str
    year_range:   str
    confidence:   float
    fingerprint:  str = ""

    # ── Backward-compat properties ──
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
            "fingerprint":  self.fingerprint,
        }


class VehicleClassifier:
    """
    Orchestrates the full vehicle intelligence pipeline for one crop.

    Accepted sub-model kwargs (all optional — system works without any):
      • classifier_model  — VehicleClassifierModel  (ONNX make/model/year)
      • color_detector    — VehicleColorDetector    (ONNX or HSV color)
      • reid_model        — VehicleReID             (ONNX 128-dim embedding)
      • fingerprint_gen   — VehicleFingerprintGenerator (always provided)

    When a sub-model is None or not loaded, its output falls back to
    "unknown" / 0.0 and the rest of the pipeline continues normally.
    """

    def __init__(
        self,
        config:           dict,
        classifier_model: "VehicleClassifierModel | None" = None,
        color_detector:   "VehicleColorDetector | None"   = None,
        reid_model:       "VehicleReID | None"             = None,
        fingerprint_gen:  "VehicleFingerprintGenerator | None" = None,
    ):
        # TRT engine path kept for backward-compat (used in TRT-only fallback)
        self.model_path   = config.get("model_path", "")
        self.input_size   = config.get("input_size", 224)

        # Sub-models
        self._clf         = classifier_model
        self._color       = color_detector
        self._reid        = reid_model
        self._fp_gen      = fingerprint_gen or VehicleFingerprintGenerator()

        # TRT fallback engine (only loaded when TRT available and no ONNX clf)
        self._trt_engine  = None
        self._trt_loaded  = False

        self._suspended   = False
        self._inference_ms = 0.0

    def load(self) -> bool:
        """
        Load available sub-models.

        The method returns True when at least one sub-model loads successfully,
        or when the TRT fallback is available.  A False return means nothing
        is loaded and classify() will return "unknown" for all fields.
        """
        loaded_any = False

        if self._clf is not None and self._clf.load():
            logger.info("VehicleClassifierModel loaded")
            loaded_any = True
        else:
            # Try TRT fallback
            loaded_any = self._load_trt_fallback() or loaded_any

        if self._color is not None:
            self._color.load()   # non-fatal; HSV fallback always works

        if self._reid is not None and self._reid.load():
            logger.info("VehicleReID model loaded")
            loaded_any = True

        return loaded_any

    def _load_trt_fallback(self) -> bool:
        """Load the legacy TRT engine when the ONNX classifier is absent."""
        if not self.model_path:
            return False
        try:
            from edge.inference.tensorrt_utils import TRTEngine
            self._trt_engine = TRTEngine(self.model_path)
            if self._trt_engine.load():
                self._trt_loaded = True
                logger.info("VehicleClassifier TRT fallback loaded: %s", self.model_path)
                return True
        except Exception:
            pass
        return False

    @property
    def is_loaded(self) -> bool:
        clf_ready = self._clf is not None and self._clf.is_loaded
        trt_ready = self._trt_loaded
        color_ready = self._color is not None  # HSV always works
        return clf_ready or trt_ready or color_ready

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def classify(self, vehicle_crop: np.ndarray) -> "VehicleClassification | None":
        """
        Run the full vehicle intelligence pipeline on one crop.

        Pipeline:
          1. Make/model/year classification (ONNX or TRT fallback)
          2. Color detection (ONNX or HSV fallback)
          3. ReID embedding generation
          4. Fingerprint string generation

        Args:
            vehicle_crop: BGR image of the vehicle bounding box.

        Returns:
            VehicleClassification with all available fields, or None when
            suspended or crop is empty.
        """
        if self._suspended:
            return None
        if vehicle_crop is None or vehicle_crop.size == 0:
            return None

        t_start = time.monotonic()

        # ── Stage A: Make / model / year ──────────────────────────────
        vehicle_type = "vehicle"
        make         = "unknown"
        model_name   = "unknown"
        year_range   = "unknown"
        conf         = 0.0

        if self._clf is not None and self._clf.is_loaded:
            clf_result = self._clf.classify(vehicle_crop)
            if clf_result is not None:
                vehicle_type = clf_result.vehicle_type
                make         = clf_result.make
                model_name   = clf_result.model
                year_range   = clf_result.year_range
                conf         = clf_result.confidence
        elif self._trt_loaded and self._trt_engine is not None:
            vehicle_type, conf = self._classify_trt(vehicle_crop)

        # ── Stage B: Color ────────────────────────────────────────────
        if self._color is not None:
            color_result = self._color.detect(vehicle_crop)
            color = color_result.color
        else:
            color = _detect_color_hsv(vehicle_crop)

        # ── Stage C: ReID embedding ───────────────────────────────────
        embedding = None
        if self._reid is not None and self._reid.is_loaded:
            embedding = self._reid.embed(vehicle_crop)

        # ── Stage D: Fingerprint ──────────────────────────────────────
        fingerprint = self._fp_gen.generate(
            vehicle_type=vehicle_type,
            make=make,
            model=model_name,
            year_range=year_range,
            color=color,
            embedding=embedding,
        )

        self._inference_ms = (time.monotonic() - t_start) * 1000

        return VehicleClassification(
            vehicle_type=vehicle_type,
            make=make,
            model=model_name,
            color=color,
            year_range=year_range,
            confidence=conf,
            fingerprint=fingerprint,
        )

    # ------------------------------------------------------------------
    # TRT fallback path
    # ------------------------------------------------------------------

    def _classify_trt(self, crop: np.ndarray) -> tuple[str, float]:
        """ImageNet TRT engine → coarse vehicle type string."""
        blob = self._preprocess_imagenet(crop)
        try:
            outputs = self._trt_engine.infer(blob)
        except Exception:
            return "vehicle", 0.0
        logits = outputs[0].flatten()
        probs  = _softmax(logits)
        top_idx  = int(np.argmax(probs))
        top_conf = float(probs[top_idx])
        vtype = _IMAGENET_TO_VEHICLE_TYPE.get(top_idx, "vehicle")
        return vtype, top_conf

    def _preprocess_imagenet(self, crop: np.ndarray) -> np.ndarray:
        resized = cv2.resize(crop, (self.input_size, self.input_size))
        rgb     = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        blob    = rgb.astype(np.float32) / 255.0
        blob    = (blob - _IMAGENET_MEAN) / _IMAGENET_STD
        blob    = blob.transpose(2, 0, 1)
        return np.expand_dims(blob, axis=0)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def suspend(self):
        if not self._suspended:
            logger.warning("VehicleClassifier SUSPENDED (thermal)")
            self._suspended = True

    def resume(self):
        if self._suspended:
            logger.info("VehicleClassifier RESUMED")
            self._suspended = False

    @property
    def is_suspended(self) -> bool:
        return self._suspended

    @property
    def inference_time_ms(self) -> float:
        return self._inference_ms

    def release(self):
        if self._clf is not None:
            self._clf.release()
        if self._color is not None:
            self._color.release()
        if self._reid is not None:
            self._reid.release()
        if self._trt_engine is not None:
            self._trt_engine.release()


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

def _detect_color_hsv(crop: np.ndarray) -> str:
    """
    HSV histogram color detection — used when VehicleColorDetector is absent.
    """
    if crop is None or crop.size == 0:
        return "unknown"

    h, w = crop.shape[:2]
    cy1, cy2 = h // 4, 3 * h // 4
    cx1, cx2 = w // 4, 3 * w // 4
    center = crop[cy1:cy2, cx1:cx2]
    if center.size == 0:
        center = crop

    hsv    = cv2.cvtColor(center, cv2.COLOR_BGR2HSV)
    h_ch   = hsv[:, :, 0].astype(np.float32)
    s_ch   = hsv[:, :, 1].astype(np.float32)
    v_ch   = hsv[:, :, 2].astype(np.float32)
    total  = float(h_ch.size)

    achromatic = s_ch < 50
    chromatic  = s_ch >= 50

    scores: dict[str, float] = {
        "black":  float(np.sum(achromatic & (v_ch < 50)))           / total,
        "white":  float(np.sum(achromatic & (v_ch > 200)))          / total,
        "silver": float(np.sum(achromatic & (v_ch >= 150) & (v_ch <= 200))) / total,
        "gray":   float(np.sum(achromatic & (v_ch >= 50)  & (v_ch < 150))) / total,
        "red":    float(np.sum(chromatic  & ((h_ch < 10) | (h_ch > 170)))) / total,
        "orange": float(np.sum(chromatic  & (h_ch >= 10) & (h_ch < 20)))   / total,
        "yellow": float(np.sum(chromatic  & (h_ch >= 20) & (h_ch < 35)))   / total,
        "green":  float(np.sum(chromatic  & (h_ch >= 35) & (h_ch < 85)))   / total,
        "blue":   float(np.sum(chromatic  & (h_ch >= 85) & (h_ch < 130)))  / total,
        "brown":  float(np.sum(chromatic  & (h_ch >= 10) & (h_ch < 20)
                               & (v_ch < 150)))                     / total,
        "gold":   float(np.sum(chromatic  & (h_ch >= 20) & (h_ch < 30)
                               & (v_ch >= 150)))                    / total,
    }

    best = max(scores, key=scores.__getitem__)
    return best if scores[best] >= _HSV_THRESHOLD else "unknown"


def _softmax(x: np.ndarray) -> np.ndarray:
    e = np.exp(x - np.max(x))
    return e / e.sum()
