"""CRNN-based license plate OCR with state-specific validation."""
import logging
import re

import cv2
import numpy as np

from ai.tensorrt_utils import TRTEngine

logger = logging.getLogger(__name__)

CHARSET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
BLANK_IDX = len(CHARSET)

# State plate format patterns (simplified - covers common formats)
STATE_PATTERNS: dict[str, list[str]] = {
    "AL": [r"^[A-Z0-9]{7}$"],
    "AK": [r"^[A-Z]{3}\d{3}$"],
    "AZ": [r"^[A-Z]{3}\d{4}$"],
    "AR": [r"^[A-Z0-9]{7}$"],
    "CA": [r"^\d[A-Z]{3}\d{3}$"],
    "CO": [r"^[A-Z]{3}\d{3}$"],
    "CT": [r"^[A-Z0-9]{7}$"],
    "DE": [r"^\d{6}$"],
    "FL": [r"^[A-Z0-9]{7}$"],
    "GA": [r"^[A-Z]{3}\d{4}$"],
    "HI": [r"^[A-Z]{3}\d{3}$"],
    "ID": [r"^[A-Z0-9]{7}$"],
    "IL": [r"^[A-Z0-9]{7}$"],
    "IN": [r"^[A-Z0-9]{7}$"],
    "IA": [r"^[A-Z0-9]{7}$"],
    "KS": [r"^[A-Z0-9]{7}$"],
    "KY": [r"^[A-Z0-9]{7}$"],
    "LA": [r"^[A-Z0-9]{7}$"],
    "ME": [r"^[A-Z0-9]{7}$"],
    "MD": [r"^[A-Z0-9]{7}$"],
    "MA": [r"^[A-Z0-9]{7}$"],
    "MI": [r"^[A-Z0-9]{7}$"],
    "MN": [r"^[A-Z0-9]{7}$"],
    "MS": [r"^[A-Z0-9]{7}$"],
    "MO": [r"^[A-Z0-9]{7}$"],
    "MT": [r"^[A-Z0-9]{7}$"],
    "NE": [r"^[A-Z0-9]{7}$"],
    "NV": [r"^[A-Z0-9]{7}$"],
    "NH": [r"^[A-Z0-9]{7}$"],
    "NJ": [r"^[A-Z0-9]{7}$"],
    "NM": [r"^[A-Z0-9]{7}$"],
    "NY": [r"^[A-Z]{3}\d{4}$"],
    "NC": [r"^[A-Z0-9]{7}$"],
    "ND": [r"^[A-Z0-9]{7}$"],
    "OH": [r"^[A-Z]{3}\d{4}$"],
    "OK": [r"^[A-Z0-9]{7}$"],
    "OR": [r"^[A-Z0-9]{7}$"],
    "PA": [r"^[A-Z]{3}\d{4}$"],
    "RI": [r"^[A-Z0-9]{6}$"],
    "SC": [r"^[A-Z0-9]{7}$"],
    "SD": [r"^[A-Z0-9]{7}$"],
    "TN": [r"^[A-Z0-9]{7}$"],
    "TX": [r"^[A-Z]{3}\d{4}$", r"^[A-Z0-9]{7}$"],
    "UT": [r"^[A-Z0-9]{7}$"],
    "VT": [r"^[A-Z0-9]{7}$"],
    "VA": [r"^[A-Z]{3}\d{4}$"],
    "WA": [r"^[A-Z]{3}\d{4}$"],
    "WV": [r"^[A-Z0-9]{7}$"],
    "WI": [r"^[A-Z0-9]{7}$"],
    "WY": [r"^[A-Z0-9]{7}$"],
}


class PlateOCR:
    def __init__(self, config: dict):
        self.config = config
        self.input_w, self.input_h = config.get("input_size", [200, 48])
        self.conf_thresh = config.get("confidence_threshold", 0.7)
        self.validate = config.get("validate_format", True)
        self.max_length = config.get("max_plate_length", 8)

        self.engine = TRTEngine(
            engine_path=config["model_path"],
            onnx_path=config.get("onnx_path"),
        )

    def preprocess(self, plate_img: np.ndarray) -> np.ndarray:
        """Preprocess plate image for CRNN.

        Converts to grayscale, resizes, and normalizes.
        """
        if len(plate_img.shape) == 3:
            gray = cv2.cvtColor(plate_img, cv2.COLOR_BGR2GRAY)
        else:
            gray = plate_img

        # CLAHE for contrast enhancement
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)

        # Resize to fixed input size
        resized = cv2.resize(
            enhanced, (self.input_w, self.input_h), interpolation=cv2.INTER_LINEAR
        )

        # Normalize to [0, 1] and add batch + channel dims
        blob = resized.astype(np.float32) / 255.0
        blob = blob[np.newaxis, np.newaxis, ...]  # [1, 1, H, W]

        return blob

    def ctc_decode(self, output: np.ndarray) -> tuple[str, float]:
        """CTC greedy decode with confidence.

        Args:
            output: CRNN output [T, C] or [1, T, C]

        Returns:
            Decoded text and average confidence
        """
        if output.ndim == 3:
            output = output.squeeze(0)

        # Softmax
        exp = np.exp(output - np.max(output, axis=1, keepdims=True))
        probs = exp / exp.sum(axis=1, keepdims=True)

        # Greedy decode
        indices = np.argmax(probs, axis=1)
        max_probs = np.max(probs, axis=1)

        chars = []
        confidences = []
        prev_idx = -1

        for t in range(len(indices)):
            idx = indices[t]
            if idx != BLANK_IDX and idx != prev_idx:
                if idx < len(CHARSET):
                    chars.append(CHARSET[idx])
                    confidences.append(max_probs[t])
            prev_idx = idx

        text = "".join(chars)
        avg_conf = float(np.mean(confidences)) if confidences else 0.0

        return text, avg_conf

    def validate_plate(self, text: str, state: str | None = None) -> bool:
        """Validate plate text against known formats."""
        if len(text) < 2 or len(text) > self.max_length:
            return False

        # Must contain at least one letter and one digit (most US plates)
        if not re.search(r"[A-Z]", text) or not re.search(r"\d", text):
            return False

        if state and state in STATE_PATTERNS and self.validate:
            return any(re.match(pat, text) for pat in STATE_PATTERNS[state])

        return True

    def read(self, plate_img: np.ndarray) -> dict | None:
        """Read text from a plate image.

        Args:
            plate_img: Cropped plate image (BGR or grayscale)

        Returns:
            Dict with plate_text, confidence, raw_ocr, or None if failed
        """
        if not self.engine.is_loaded:
            return None

        if plate_img.size == 0:
            return None

        blob = self.preprocess(plate_img)
        outputs = self.engine.infer(blob)
        text, confidence = self.ctc_decode(outputs[0])

        if not text or confidence < self.conf_thresh:
            return None

        return {
            "plate_text": text,
            "confidence": confidence,
            "raw_ocr": text,
        }
