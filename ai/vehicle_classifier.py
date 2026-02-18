"""EfficientNet-based vehicle Year/Make/Model/Color classifier.

Fixes applied:
- BGR→RGB conversion before ImageNet normalization
- Aspect-ratio-preserving center crop (no stretching)
- INTER_AREA for downsizing quality
- Per-head confidence thresholds
- Label count validation against model output shape
- Color confidence thresholding (was missing)
- Year label parsing error handling
- Classification caching per track ID for stability
"""
import json
import logging
import time
from collections import OrderedDict

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


class _ClassificationCache:
    """LRU cache for per-track classification results.

    Stores the best classification seen for each track ID, avoiding
    redundant GPU inference on already-classified vehicles. Results
    are evicted after `ttl` seconds or when the cache is full.
    """

    def __init__(self, maxsize: int = 128, ttl: float = 10.0):
        self._cache: OrderedDict[int, dict] = OrderedDict()
        self._timestamps: dict[int, float] = {}
        self._maxsize = maxsize
        self._ttl = ttl

    def get(self, track_id: int) -> dict | None:
        """Get cached classification for a track ID, or None if expired/missing."""
        if track_id not in self._cache:
            return None
        if time.monotonic() - self._timestamps[track_id] > self._ttl:
            del self._cache[track_id]
            del self._timestamps[track_id]
            return None
        self._cache.move_to_end(track_id)
        return self._cache[track_id]

    def put(self, track_id: int, result: dict):
        """Store or update classification for a track ID.

        Keeps the higher-confidence result if one already exists.
        """
        now = time.monotonic()

        existing = self._cache.get(track_id)
        if existing and existing.get("confidence", 0) >= result.get("confidence", 0):
            # Existing is better; just refresh timestamp
            self._timestamps[track_id] = now
            return

        self._cache[track_id] = result
        self._timestamps[track_id] = now
        self._cache.move_to_end(track_id)

        # Evict oldest if over capacity
        while len(self._cache) > self._maxsize:
            old_key, _ = self._cache.popitem(last=False)
            self._timestamps.pop(old_key, None)


class VehicleClassifier:
    def __init__(self, config: dict):
        self.config = config
        self.input_h, self.input_w = config.get("input_size", [224, 224])

        # Per-head confidence thresholds (fall back to global threshold)
        global_thresh = config.get("confidence_threshold", 0.5)
        self.make_conf_thresh = config.get("make_confidence_threshold", global_thresh)
        self.model_conf_thresh = config.get("model_confidence_threshold", global_thresh)
        self.year_conf_thresh = config.get("year_confidence_threshold", global_thresh)
        self.color_conf_thresh = config.get("color_confidence_threshold", 0.3)

        self.engine = TRTEngine(
            engine_path=config["model_path"],
            onnx_path=config.get("onnx_path"),
        )

        # Load labels from config-specified JSON files
        self.make_labels = _load_labels(config.get("make_labels_path"))
        self.model_labels = _load_labels(config.get("model_labels_path"))
        self.year_labels = _load_labels(config.get("year_labels_path"))
        self.color_labels = _load_labels(config.get("color_labels_path")) or COLORS

        self._labels_validated = False

        # Per-track classification cache
        cache_ttl = config.get("cache_ttl", 10.0)
        cache_size = config.get("cache_size", 128)
        self.cache = _ClassificationCache(maxsize=cache_size, ttl=cache_ttl)

    def _validate_labels_once(self, outputs: list[np.ndarray]):
        """Validate label counts against model output shapes on first inference."""
        if self._labels_validated:
            return
        self._labels_validated = True

        head_names = ["make", "model", "year", "color"]
        label_lists = [self.make_labels, self.model_labels, self.year_labels, self.color_labels]

        for i, (name, labels) in enumerate(zip(head_names, label_lists)):
            if i < len(outputs) and labels:
                out_size = outputs[i].squeeze().shape[0] if outputs[i].squeeze().ndim > 0 else 1
                if len(labels) != out_size:
                    logger.warning(
                        "Label count mismatch for %s head: model outputs %d classes "
                        "but label file has %d entries",
                        name, out_size, len(labels),
                    )

    def preprocess(self, vehicle_img: np.ndarray) -> np.ndarray:
        """Preprocess vehicle image for EfficientNet.

        1. BGR → RGB conversion (EfficientNet trained on RGB)
        2. Aspect-ratio-preserving center crop to square
        3. Resize to model input size using INTER_AREA for downsizing
        4. ImageNet normalization (RGB channel order)
        """
        # BGR → RGB
        rgb = cv2.cvtColor(vehicle_img, cv2.COLOR_BGR2RGB)

        # Aspect-ratio-preserving center crop to square
        h, w = rgb.shape[:2]
        if h != w:
            side = min(h, w)
            y_start = (h - side) // 2
            x_start = (w - side) // 2
            rgb = rgb[y_start:y_start + side, x_start:x_start + side]

        # Resize to model input — INTER_AREA for downsizing, INTER_LINEAR for upsizing
        current_h, current_w = rgb.shape[:2]
        interp = cv2.INTER_AREA if current_h > self.input_h else cv2.INTER_LINEAR
        resized = cv2.resize(rgb, (self.input_w, self.input_h), interpolation=interp)

        # Normalize with ImageNet statistics (RGB order)
        blob = resized.astype(np.float32) / 255.0
        mean = np.array([0.485, 0.456, 0.406])
        std = np.array([0.229, 0.224, 0.225])
        blob = (blob - mean) / std

        # HWC -> NCHW
        blob = blob.transpose(2, 0, 1)[np.newaxis, ...]
        return blob

    def classify(self, vehicle_img: np.ndarray, track_id: int | None = None) -> dict | None:
        """Classify vehicle year, make, model, and color.

        Args:
            vehicle_img: Cropped vehicle image (BGR)
            track_id: Optional tracker ID for classification caching

        Returns:
            Dict with make, model, year, color, confidence, or None
        """
        # Check cache first (skip GPU inference for already-classified vehicles)
        if track_id is not None:
            cached = self.cache.get(track_id)
            if cached is not None:
                return cached

        if not self.engine.is_loaded:
            return None

        if vehicle_img.size == 0:
            return None

        blob = self.preprocess(vehicle_img)
        outputs = self.engine.infer(blob)

        # Validate label counts on first run
        self._validate_labels_once(outputs)

        # Expected outputs: [make_logits, model_logits, year_logits, color_logits]
        # Also supports single concatenated output tensor
        if len(outputs) == 1 and outputs[0].squeeze().ndim == 1:
            # Single concatenated output — split by label counts
            flat = outputs[0].squeeze()
            outputs = self._split_concatenated_output(flat)

        result = {"confidence": 0.0}

        # Make classification
        if len(outputs) >= 1 and self.make_labels:
            probs = self._softmax(outputs[0].squeeze())
            idx = int(np.argmax(probs))
            if probs[idx] >= self.make_conf_thresh and idx < len(self.make_labels):
                result["make"] = self.make_labels[idx]
                result["confidence"] = round(float(probs[idx]), 4)

        # Model classification
        if len(outputs) >= 2 and self.model_labels:
            probs = self._softmax(outputs[1].squeeze())
            idx = int(np.argmax(probs))
            if probs[idx] >= self.model_conf_thresh and idx < len(self.model_labels):
                result["model"] = self.model_labels[idx]

        # Year classification
        if len(outputs) >= 3 and self.year_labels:
            probs = self._softmax(outputs[2].squeeze())
            idx = int(np.argmax(probs))
            if probs[idx] >= self.year_conf_thresh and idx < len(self.year_labels):
                try:
                    result["year"] = int(self.year_labels[idx])
                except (ValueError, TypeError):
                    logger.debug("Non-integer year label at index %d: %s", idx, self.year_labels[idx])

        # Color classification (with confidence threshold — was missing)
        if len(outputs) >= 4:
            probs = self._softmax(outputs[3].squeeze())
            idx = int(np.argmax(probs))
            if probs[idx] >= self.color_conf_thresh and idx < len(self.color_labels):
                result["color"] = self.color_labels[idx]

        final = result if result.get("make") or result.get("color") else None

        # Cache result for this track
        if track_id is not None and final is not None:
            self.cache.put(track_id, final)

        return final

    def _split_concatenated_output(self, flat: np.ndarray) -> list[np.ndarray]:
        """Split a single concatenated output tensor into per-head arrays.

        Uses label list lengths to determine split points. If lengths don't
        sum to the output size, falls back to returning the flat tensor as-is.
        """
        sizes = []
        for labels in [self.make_labels, self.model_labels, self.year_labels, self.color_labels]:
            if labels:
                sizes.append(len(labels))

        if sum(sizes) == flat.shape[0]:
            splits = []
            offset = 0
            for s in sizes:
                splits.append(flat[offset:offset + s])
                offset += s
            return splits

        logger.debug(
            "Cannot split concatenated output (size=%d) by label sizes %s",
            flat.shape[0], sizes,
        )
        return [flat]

    @staticmethod
    def _softmax(x: np.ndarray) -> np.ndarray:
        e = np.exp(x - np.max(x))
        return e / e.sum()
