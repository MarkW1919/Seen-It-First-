"""Shared utilities for the AI pipeline.

Consolidates duplicate implementations of softmax, letterbox preprocessing,
and IoU computation that were previously copied across multiple modules.
"""

from __future__ import annotations

import time
from collections import OrderedDict

import cv2
import numpy as np


def softmax(x: np.ndarray) -> np.ndarray:
    """Apply softmax to normalize logits to probabilities."""
    e = np.exp(x - np.max(x))
    return e / e.sum()


def compute_iou(box_a: list[int], box_b: list[int]) -> float:
    """Compute Intersection over Union between two [x, y, w, h] boxes."""
    ax1, ay1, aw, ah = box_a
    bx1, by1, bw, bh = box_b
    ax2, ay2 = ax1 + aw, ay1 + ah
    bx2, by2 = bx1 + bw, by1 + bh

    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)

    inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
    union = aw * ah + bw * bh - inter
    return inter / max(union, 1e-6)


class LetterboxPreprocessor:
    """Reusable letterbox preprocessing for YOLO-style detectors.

    Pre-allocates buffers for zero per-frame allocation during inference.
    """

    def __init__(self, input_size: tuple[int, int], pad_color: int = 114):
        self.input_h, self.input_w = input_size
        self._padded = np.full((self.input_h, self.input_w, 3), pad_color, dtype=np.uint8)
        self._blob = np.empty((1, 3, self.input_h, self.input_w), dtype=np.float32)
        self._pad_color = pad_color

    def preprocess(self, frame: np.ndarray) -> tuple[np.ndarray, float, tuple[int, int]]:
        """Letterbox preprocess with channel-separated normalization.

        Returns:
            blob: NCHW float32 tensor normalized to [0, 1]
            scale: resize scale factor
            pad: (pad_w, pad_h) pixel offsets
        """
        h, w = frame.shape[:2]
        scale = min(self.input_w / w, self.input_h / h)
        new_w, new_h = int(w * scale), int(h * scale)
        pad_w, pad_h = (self.input_w - new_w) // 2, (self.input_h - new_h) // 2

        resized = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_LINEAR)

        self._padded[:] = self._pad_color
        self._padded[pad_h : pad_h + new_h, pad_w : pad_w + new_w] = resized

        self._blob[0, 0] = self._padded[:, :, 0]
        self._blob[0, 1] = self._padded[:, :, 1]
        self._blob[0, 2] = self._padded[:, :, 2]
        self._blob *= 1.0 / 255.0

        return self._blob, scale, (pad_w, pad_h)


class TTLCache:
    """Generic LRU cache with TTL expiration.

    Used by both plate OCR (duplicate suppression) and vehicle classifier
    (per-track classification caching).
    """

    def __init__(self, maxsize: int = 128, ttl: float = 10.0):
        self._cache: OrderedDict = OrderedDict()
        self._timestamps: dict = {}
        self._maxsize = maxsize
        self._ttl = ttl

    def get(self, key):
        """Get value if present and not expired, else None."""
        if key not in self._cache:
            return None
        if time.monotonic() - self._timestamps[key] > self._ttl:
            del self._cache[key]
            del self._timestamps[key]
            return None
        self._cache.move_to_end(key)
        return self._cache[key]

    def put(self, key, value):
        """Store value, evicting oldest if over capacity."""
        self._cache[key] = value
        self._timestamps[key] = time.monotonic()
        self._cache.move_to_end(key)
        while len(self._cache) > self._maxsize:
            old_key, _ = self._cache.popitem(last=False)
            self._timestamps.pop(old_key, None)

    def contains(self, key) -> bool:
        """Check if key exists and is not expired."""
        return self.get(key) is not None

    def __contains__(self, key) -> bool:
        return self.contains(key)
