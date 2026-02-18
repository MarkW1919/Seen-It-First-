"""EfficientNet-based vehicle Year/Make/Model/Color classifier."""
import json
import logging
import os

import cv2
import numpy as np

from ai.tensorrt_utils import TRTEngine

logger = logging.getLogger(__name__)

# Common vehicle colors (fallback if no label file provided)
COLORS = [
    "black", "white", "silver", "gray", "red", "blue", "brown",
    "green", "beige", "gold", "orange", "yellow", "purple", "maroon",
]


def _load_labels(path: str | None) -> list[str]:
    """Load labels from a JSON file.

    Args:
        path: Path to a JSON file containing a list of label strings.

    Returns:
        List of label strings, or empty list if path is None or load fails.
    """
    if not path:
        return []
    try:
        with open(path) as f:
            labels = json.load(f)
        if isinstance(labels, list) and all(isinstance(l, str) for l in labels):
            logger.info("Loaded %d labels from %s", len(labels), path)
            return labels
        logger.warning("Label file %s does not contain a list of strings", path)
        return []
    except FileNotFoundError:
        logger.warning("Label file not found: %s", path)
        return []
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Failed to load labels from %s: %s", path, e)
        return []


class VehicleClassifier:
    def __init__(self, config: dict):
        self.config = config
        self.input_h, self.input_w = config.get("input_size", [224, 224])
        self.conf_thresh = config.get("confidence_threshold", 0.5)

        self.engine = TRTEngine(
            engine_path=config["model_path"],
            onnx_path=config.get("onnx_path"),
        )

        # Load labels from config-specified JSON files
        self.make_labels = _load_labels(config.get("make_labels_path"))
        self.model_labels = _load_labels(config.get("model_labels_path"))
        self.year_labels = _load_labels(config.get("year_labels_path"))
        self.color_labels = _load_labels(config.get("color_labels_path")) or COLORS

    def preprocess(self, vehicle_img: np.ndarray) -> np.ndarray:
        """Preprocess vehicle image for EfficientNet."""
        resized = cv2.resize(
            vehicle_img,
            (self.input_w, self.input_h),
            interpolation=cv2.INTER_LINEAR,
        )

        # Normalize with ImageNet statistics
        blob = resized.astype(np.float32) / 255.0
        mean = np.array([0.485, 0.456, 0.406])
        std = np.array([0.229, 0.224, 0.225])
        blob = (blob - mean) / std

        # HWC -> NCHW
        blob = blob.transpose(2, 0, 1)[np.newaxis, ...]
        return blob

    def classify(self, vehicle_img: np.ndarray) -> dict | None:
        """Classify vehicle year, make, model, and color.

        Args:
            vehicle_img: Cropped vehicle image (BGR)

        Returns:
            Dict with make, model, year, color, confidence, or None
        """
        if not self.engine.is_loaded:
            return None

        if vehicle_img.size == 0:
            return None

        blob = self.preprocess(vehicle_img)
        outputs = self.engine.infer(blob)

        # Expected outputs: [make_logits, model_logits, year_logits, color_logits]
        result = {"confidence": 0.0}

        if len(outputs) >= 1 and self.make_labels:
            probs = self._softmax(outputs[0].squeeze())
            idx = int(np.argmax(probs))
            if probs[idx] >= self.conf_thresh and idx < len(self.make_labels):
                result["make"] = self.make_labels[idx]
                result["confidence"] = float(probs[idx])

        if len(outputs) >= 2 and self.model_labels:
            probs = self._softmax(outputs[1].squeeze())
            idx = int(np.argmax(probs))
            if probs[idx] >= self.conf_thresh and idx < len(self.model_labels):
                result["model"] = self.model_labels[idx]

        if len(outputs) >= 3 and self.year_labels:
            probs = self._softmax(outputs[2].squeeze())
            idx = int(np.argmax(probs))
            if probs[idx] >= self.conf_thresh and idx < len(self.year_labels):
                result["year"] = int(self.year_labels[idx])

        if len(outputs) >= 4:
            probs = self._softmax(outputs[3].squeeze())
            idx = int(np.argmax(probs))
            if idx < len(self.color_labels):
                result["color"] = self.color_labels[idx]

        return result if result.get("make") or result.get("color") else None

    @staticmethod
    def _softmax(x: np.ndarray) -> np.ndarray:
        e = np.exp(x - np.max(x))
        return e / e.sum()
