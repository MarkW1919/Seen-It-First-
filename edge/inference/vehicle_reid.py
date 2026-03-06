"""
Vehicle re-identification embedding model.

Model: vehicle_embedding_model.onnx
  Input:  [1, 3, 128, 128]  float32  (ImageNet normalisation)
  Output: [1, 128]          float32  L2-normalised embedding vector

The embedding is used by VehicleFingerprintGenerator to produce the
hash suffix that makes fingerprints vehicle-instance-specific.  It is also
available for future cross-camera re-ID and duplicate suppression.

When the model is not loaded, embed() returns None and the fingerprint
generator falls back to a text-only hash.
"""

import logging
import time
from pathlib import Path

import cv2
import numpy as np

from edge.inference.onnx_utils import OnnxEngine

logger = logging.getLogger(__name__)

_IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
_IMAGENET_STD  = np.array([0.229, 0.224, 0.225], dtype=np.float32)

# Expected embedding length
EMBEDDING_DIM = 128


class VehicleReID:
    """
    Generates a 128-dimensional L2-normalised embedding for a vehicle crop.

    Usage::

        reid = VehicleReID({"model_path": "edge/models/vehicle_embedding_model.onnx"})
        reid.load()
        vec = reid.embed(vehicle_crop)   # np.ndarray shape (128,) or None
    """

    def __init__(self, config: dict):
        self.model_path  = config.get("model_path", "")
        self.input_size  = config.get("input_size", 128)
        self.engine      = OnnxEngine(self.model_path) if self.model_path else None
        self._infer_ms   = 0.0

    def load(self) -> bool:
        if self.engine is None:
            return False
        return self.engine.load()

    @property
    def is_loaded(self) -> bool:
        return self.engine is not None and self.engine.is_loaded

    def embed(self, crop: np.ndarray) -> "np.ndarray | None":
        """
        Compute a 128-dim L2-normalised embedding for the given crop.

        Returns:
            numpy array of shape (128,) or None if model not loaded / inference fails.
        """
        if not self.is_loaded or crop is None or crop.size == 0:
            return None

        blob = self._preprocess(crop)

        t0 = time.monotonic()
        try:
            outputs = self.engine.infer(blob)
        except Exception:
            logger.exception("VehicleReID inference failed")
            return None
        self._infer_ms = (time.monotonic() - t0) * 1000

        embedding = outputs[0].flatten()

        # Ensure correct dimension
        if embedding.shape[0] != EMBEDDING_DIM:
            logger.warning(
                "VehicleReID unexpected output dim %d (expected %d)",
                embedding.shape[0], EMBEDDING_DIM,
            )

        # L2-normalise
        norm = np.linalg.norm(embedding)
        if norm > 1e-8:
            embedding = embedding / norm

        return embedding.astype(np.float32)

    def _preprocess(self, crop: np.ndarray) -> np.ndarray:
        resized = cv2.resize(crop, (self.input_size, self.input_size))
        rgb     = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        blob    = rgb.astype(np.float32) / 255.0
        blob    = (blob - _IMAGENET_MEAN) / _IMAGENET_STD
        blob    = blob.transpose(2, 0, 1)
        return np.expand_dims(blob, axis=0)

    def release(self):
        if self.engine is not None:
            self.engine.release()

    @property
    def inference_time_ms(self) -> float:
        return self._infer_ms
