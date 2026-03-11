"""
Vehicle make / model / year classifier using ONNX Runtime.

Model: vehicle_make_model_classifier.onnx
  Input:  [1, 3, 224, 224]  float32  (ImageNet normalisation)
  Output: [1, N_classes]    float32  softmax probabilities

The model is expected to output joint make-model-year labels that are
decoded via a JSON label map stored next to the model file:

    models/onnx/vehicle_make_model_labels.json

Label file format::

    {
      "0": {"vehicle_type": "car",    "make": "Toyota",    "model": "Camry",     "year_range": "2018-2022"},
      "1": {"vehicle_type": "pickup", "make": "Chevrolet", "model": "Silverado", "year_range": "2019-2022"},
      ...
    }

When the model or label file is absent the classifier returns "unknown" for
all fields and logs a warning.  The pipeline continues with colour and
fingerprint generation.
"""

import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from edge.inference.onnx_utils import OnnxEngine

logger = logging.getLogger(__name__)

# Minimum softmax probability to trust a classification result
_MIN_CONFIDENCE = 0.50

_IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
_IMAGENET_STD  = np.array([0.229, 0.224, 0.225], dtype=np.float32)


@dataclass
class ClassifierResult:
    """Raw output from VehicleClassifierModel before fingerprint generation."""
    vehicle_type: str
    make:         str
    model:        str
    year_range:   str
    confidence:   float


class VehicleClassifierModel:
    """
    ONNX-backed make / model / year estimator.

    Usage::

        clf = VehicleClassifierModel({"model_path": "models/onnx/vehicle_make_model_classifier.onnx"})
        clf.load()
        result = clf.classify(vehicle_crop)  # → ClassifierResult or None
    """

    def __init__(self, config: dict):
        self.model_path   = config.get("model_path", "")
        self.input_size   = config.get("input_size", 224)
        self.engine       = OnnxEngine(self.model_path)
        self._labels: dict[int, dict] = {}
        self._inference_ms = 0.0

    def load(self) -> bool:
        if not self.engine.load():
            return False
        self._load_labels()
        return True

    def _load_labels(self):
        label_path = Path(self.model_path).parent / "vehicle_make_model_labels.json"
        if not label_path.exists():
            logger.warning("Label map not found: %s — classification will return unknown", label_path)
            return
        try:
            with open(label_path, "r") as f:
                raw = json.load(f)
            self._labels = {int(k): v for k, v in raw.items()}
            logger.info("Loaded %d vehicle class labels from %s", len(self._labels), label_path)
        except Exception:
            logger.exception("Failed to load label map: %s", label_path)

    @property
    def is_loaded(self) -> bool:
        return self.engine.is_loaded

    def classify(self, crop: np.ndarray) -> ClassifierResult:
        """
        Classify a vehicle crop.

        Returns ClassifierResult with all fields set to "unknown" and
        confidence 0.0 if the model is not loaded or confidence is below
        the threshold.
        """
        _unknown = ClassifierResult("vehicle", "unknown", "unknown", "unknown", 0.0)

        if crop is None or crop.size == 0:
            return _unknown

        blob = self._preprocess(crop)

        t0 = time.monotonic()
        try:
            outputs = self.engine.infer(blob)
        except Exception:
            logger.exception("VehicleClassifierModel inference failed")
            return _unknown
        self._inference_ms = (time.monotonic() - t0) * 1000

        probs = outputs[0].flatten()
        # Apply softmax if not already applied by the model
        if probs.max() > 1.0 or probs.min() < 0.0:
            e = np.exp(probs - probs.max())
            probs = e / e.sum()

        top_idx  = int(np.argmax(probs))
        top_conf = float(probs[top_idx])

        if top_conf < _MIN_CONFIDENCE:
            return ClassifierResult("vehicle", "unknown", "unknown", "unknown", top_conf)

        label = self._labels.get(top_idx, {})
        return ClassifierResult(
            vehicle_type=label.get("vehicle_type", "vehicle"),
            make=label.get("make",       "unknown"),
            model=label.get("model",     "unknown"),
            year_range=label.get("year_range", "unknown"),
            confidence=top_conf,
        )

    def _preprocess(self, crop: np.ndarray) -> np.ndarray:
        resized = cv2.resize(crop, (self.input_size, self.input_size))
        rgb     = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        blob    = rgb.astype(np.float32) / 255.0
        blob    = (blob - _IMAGENET_MEAN) / _IMAGENET_STD
        blob    = blob.transpose(2, 0, 1)
        return np.expand_dims(blob, axis=0)

    def release(self):
        self.engine.release()

    @property
    def inference_time_ms(self) -> float:
        return self._inference_ms
