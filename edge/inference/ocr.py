"""
License plate OCR using lightweight CRNN TensorRT engine.

Runs ONLY when plate confidence exceeds threshold.
Includes rule-based post-processing for US plates.
"""

import logging
import re
import time
from dataclasses import dataclass

import cv2
import numpy as np

from edge.inference.tensorrt_utils import TRTEngine
from edge.inference.plate_detector import PlateDetection

logger = logging.getLogger(__name__)

# US plate character set
PLATE_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
CHAR_TO_IDX = {c: i for i, c in enumerate(PLATE_CHARS)}
IDX_TO_CHAR = {i: c for i, c in enumerate(PLATE_CHARS)}

# Common OCR confusions: map wrong → correct
CONFUSION_MAP = {
    "O": "0",  # letter O → digit 0 when in digit context
    "0": "O",  # digit 0 → letter O when in letter context
    "I": "1",
    "1": "I",
    "S": "5",
    "5": "S",
    "B": "8",
    "8": "B",
    "Z": "2",
    "2": "Z",
    "G": "6",
    "6": "G",
}


@dataclass
class OCRResult:
    """OCR result for a single plate."""
    text: str
    raw_text: str
    confidence: float
    plate_detection: PlateDetection


class PlateOCR:
    """
    CRNN-based license plate OCR.

    Model: Lightweight CRNN trained on US plate fonts → TensorRT FP16
    Input: 200x64 grayscale
    Engine size: ~8 MB
    VRAM footprint: ~30 MB
    """

    def __init__(self, config: dict):
        self.model_path = config["model_path"]
        self.input_width = config.get("input_width", 200)
        self.input_height = config.get("input_height", 64)
        self.conf_threshold = config.get("confidence_threshold", 0.60)
        self.min_chars = config.get("min_plate_chars", 5)
        self.max_chars = config.get("max_plate_chars", 8)
        self.engine = TRTEngine(self.model_path)
        self._inference_time_ms = 0.0

    def load(self) -> bool:
        return self.engine.load()

    def recognize(
        self,
        frame: np.ndarray,
        plates: list[PlateDetection],
        night_mode: bool = False,
    ) -> list[OCRResult]:
        """
        Run OCR on detected plate regions.

        Args:
            frame: Full BGR frame.
            plates: Plate detections from PlateDetector.
            night_mode: If True, apply CLAHE enhancement to plate ROI.

        Returns:
            List of OCRResult with cleaned plate text.
        """
        results = []

        for plate in plates:
            crop = self._crop_plate(frame, plate)
            if crop is None:
                continue

            if night_mode:
                crop = self._enhance_night(crop)

            blob = self._preprocess(crop)

            t0 = time.monotonic()
            outputs = self.engine.infer(blob)
            self._inference_time_ms = (time.monotonic() - t0) * 1000

            raw_text, confidence = self._decode_ctc(outputs)
            cleaned = self._postprocess_text(raw_text)

            if (
                confidence >= self.conf_threshold
                and self.min_chars <= len(cleaned) <= self.max_chars
            ):
                results.append(OCRResult(
                    text=cleaned,
                    raw_text=raw_text,
                    confidence=confidence,
                    plate_detection=plate,
                ))
            else:
                logger.debug(
                    "OCR rejected: '%s' (conf=%.2f, len=%d)",
                    cleaned, confidence, len(cleaned),
                )

        return results

    def _crop_plate(
        self, frame: np.ndarray, plate: PlateDetection
    ) -> np.ndarray | None:
        """Extract plate region from frame."""
        h, w = frame.shape[:2]
        x1 = max(0, plate.x1)
        y1 = max(0, plate.y1)
        x2 = min(w, plate.x2)
        y2 = min(h, plate.y2)

        crop = frame[y1:y2, x1:x2]
        if crop.size == 0 or crop.shape[0] < 8 or crop.shape[1] < 20:
            return None
        return crop

    def _enhance_night(self, crop: np.ndarray) -> np.ndarray:
        """Apply CLAHE to plate ROI only (not full frame)."""
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)
        return cv2.cvtColor(enhanced, cv2.COLOR_GRAY2BGR)

    def _preprocess(self, crop: np.ndarray) -> np.ndarray:
        """Convert to grayscale, resize, normalize for CRNN input."""
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        resized = cv2.resize(gray, (self.input_width, self.input_height))
        blob = resized.astype(np.float32) / 255.0
        # CRNN expects [1, 1, H, W]
        blob = blob[np.newaxis, np.newaxis, :, :]
        return np.ascontiguousarray(blob)

    def _decode_ctc(self, outputs: list[np.ndarray]) -> tuple[str, float]:
        """
        CTC greedy decode.

        CRNN output: [T, 1, num_classes] where T = sequence length.
        """
        raw = outputs[0]

        # Reshape to [T, num_classes]
        if raw.ndim == 3:
            logits = raw[:, 0, :]
        elif raw.ndim == 2:
            logits = raw
        else:
            return "", 0.0

        # Softmax
        exp_logits = np.exp(logits - np.max(logits, axis=1, keepdims=True))
        probs = exp_logits / np.sum(exp_logits, axis=1, keepdims=True)

        # Greedy decode with CTC blank removal
        char_indices = np.argmax(probs, axis=1)
        char_probs = np.max(probs, axis=1)

        chars = []
        confidences = []
        blank_idx = len(PLATE_CHARS)  # blank is last class
        prev_idx = -1

        for t in range(len(char_indices)):
            idx = int(char_indices[t])
            if idx != blank_idx and idx != prev_idx:
                if idx < len(PLATE_CHARS):
                    chars.append(PLATE_CHARS[idx])
                    confidences.append(float(char_probs[t]))
            prev_idx = idx

        text = "".join(chars)
        avg_conf = float(np.mean(confidences)) if confidences else 0.0

        return text, avg_conf

    def _postprocess_text(self, text: str) -> str:
        """
        Rule-based cleaning for US license plates.

        - Uppercase normalization
        - Strip spaces and special characters
        - Enforce 5-8 character constraint
        """
        # Uppercase and strip
        cleaned = text.upper().strip()

        # Remove anything that isn't alphanumeric
        cleaned = re.sub(r"[^A-Z0-9]", "", cleaned)

        return cleaned

    @property
    def inference_time_ms(self) -> float:
        return self._inference_time_ms

    def release(self):
        self.engine.release()
