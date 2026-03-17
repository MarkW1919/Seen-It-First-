"""
License plate OCR using a PaddleOCR PP-OCRv4 TensorRT engine.

This module focuses on US plate recognition with lightweight post-processing:
- PP-OCRv4 TensorRT inference
- CTC greedy decoding
- US-format cleanup and validation
- Optional ambiguity correction for common OCR confusions
"""

import logging
import re
import time
from dataclasses import dataclass

import cv2
import numpy as np

from edge.inference.plate_detector import PlateDetection
from edge.inference.tensorrt_utils import TRTEngine

logger = logging.getLogger(__name__)

PLATE_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
US_PLATE_REGEX = re.compile(r"^[A-Z0-9]{2,8}$")

CONFUSION_MAP = {
    "O": "0",
    "0": "O",
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

PADDLE_OCR_CHARS = (
    " !\"#$%&'()*+,-./"
    "0123456789"
    ":;<=>?@"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "[\\]^_`"
    "abcdefghijklmnopqrstuvwxyz"
    "{|}~"
)
_BLANK_IDX = len(PADDLE_OCR_CHARS)


@dataclass
class OCRResult:
    """OCR result for a single detected plate."""

    text: str
    raw_text: str
    confidence: float
    plate_detection: PlateDetection

    def to_dict(self) -> dict:
        return {
            "plate": self.text,
            "confidence": round(self.confidence, 4),
        }


class PlateOCR:
    """
    PaddleOCR PP-OCRv4 English recognition for US license plates.

    Model: PP-OCRv4 English rec -> ONNX -> TensorRT FP16
    Input: [1, 3, 48, 320] RGB, normalized mean=0.5 std=0.5
    """

    _MEAN = np.array([0.5, 0.5, 0.5], dtype=np.float32)
    _STD = np.array([0.5, 0.5, 0.5], dtype=np.float32)

    def __init__(self, config: dict):
        self.model_path = config["model_path"]
        self.input_width = int(config.get("input_width", 320))
        self.input_height = int(config.get("input_height", 48))
        self.conf_threshold = float(config.get("confidence_threshold", 0.60))
        self.min_chars = int(config.get("min_plate_chars", 2))
        self.max_chars = int(config.get("max_plate_chars", 8))
        self.enable_ambiguity_correction = bool(
            config.get("enable_ambiguity_correction", False)
        )
        self.clahe_clip_limit = float(config.get("clahe_clip_limit", 3.0))
        grid = int(config.get("clahe_grid_size", 8))
        self.clahe_grid_size = (grid, grid)
        self.gamma = float(config.get("gamma", 0.7))
        self.engine = TRTEngine(self.model_path)
        self._inference_time_ms = 0.0

    def load(self) -> bool:
        return self.engine.load()

    @property
    def is_loaded(self) -> bool:
        return self.engine.is_loaded

    def recognize(
        self,
        frame: np.ndarray,
        plates: list[PlateDetection],
        night_mode: bool = False,
    ) -> list[OCRResult]:
        """Run OCR on detected plate regions."""
        results: list[OCRResult] = []

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
            if self.enable_ambiguity_correction:
                cleaned = self._resolve_ambiguities(cleaned)

            if confidence >= self.conf_threshold and self.validate_plate(cleaned):
                results.append(
                    OCRResult(
                        text=cleaned,
                        raw_text=raw_text,
                        confidence=confidence,
                        plate_detection=plate,
                    )
                )
            else:
                logger.debug(
                    "OCR rejected: '%s' (conf=%.2f, len=%d)",
                    cleaned,
                    confidence,
                    len(cleaned),
                )

        return results

    def _crop_plate(
        self, frame: np.ndarray, plate: PlateDetection
    ) -> np.ndarray | None:
        """Extract the plate region from the frame."""
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
        """Apply CLAHE and gamma correction to a low-light plate crop."""
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        clahe = cv2.createCLAHE(
            clipLimit=self.clahe_clip_limit,
            tileGridSize=self.clahe_grid_size,
        )
        enhanced = clahe.apply(gray)

        gamma = max(0.1, self.gamma)
        table = np.array(
            [(i / 255.0) ** gamma * 255 for i in range(256)],
            dtype=np.uint8,
        )
        corrected = cv2.LUT(enhanced, table)
        return cv2.cvtColor(corrected, cv2.COLOR_GRAY2BGR)

    def _preprocess(self, crop: np.ndarray) -> np.ndarray:
        """
        Prepare a plate crop for PP-OCRv4 recognition.

        - Convert BGR -> RGB
        - Resize to the model input size
        - Normalize to roughly [-1, 1]
        - Return NCHW float32
        """
        rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
        resized = cv2.resize(rgb, (self.input_width, self.input_height))
        blob = resized.astype(np.float32) / 255.0
        blob = (blob - self._MEAN) / self._STD
        blob = blob.transpose(2, 0, 1)
        blob = np.expand_dims(blob, axis=0)
        return np.ascontiguousarray(blob)

    def _decode_ctc(self, outputs: list[np.ndarray]) -> tuple[str, float]:
        """
        Greedy CTC decode for PP-OCRv4 outputs.

        Expected output shape: [1, T, num_chars + 1], with the blank token last.
        """
        if not outputs:
            return "", 0.0

        raw = outputs[0]
        if raw.ndim == 3:
            logits = raw[0]
        elif raw.ndim == 2:
            logits = raw
        else:
            return "", 0.0

        exp_logits = np.exp(logits - np.max(logits, axis=1, keepdims=True))
        probs = exp_logits / np.sum(exp_logits, axis=1, keepdims=True)

        char_indices = np.argmax(probs, axis=1)
        char_probs = np.max(probs, axis=1)

        chars: list[str] = []
        confidences: list[float] = []
        prev_idx = -1

        for idx, prob in zip(char_indices, char_probs):
            idx_int = int(idx)
            if idx_int != _BLANK_IDX and idx_int != prev_idx:
                if idx_int < len(PADDLE_OCR_CHARS):
                    chars.append(PADDLE_OCR_CHARS[idx_int])
                    confidences.append(float(prob))
            prev_idx = idx_int

        text = "".join(chars)
        avg_conf = float(np.mean(confidences)) if confidences else 0.0
        return text, avg_conf

    def _postprocess_text(self, text: str) -> str:
        """Normalize OCR output to a US-plate-friendly alphanumeric string."""
        cleaned = text.upper().strip()
        cleaned = re.sub(r"[^A-Z0-9]", "", cleaned)
        if len(cleaned) > self.max_chars:
            cleaned = cleaned[: self.max_chars]
        return cleaned

    def _resolve_ambiguities(self, text: str) -> str:
        """Correct ambiguous OCR characters using neighbor context."""
        if len(text) < self.min_chars:
            return text

        chars = list(text)
        source_chars = list(text)
        digit_like = {"O": "0", "I": "1", "Z": "2", "S": "5", "B": "8"}
        alpha_like = {"0": "O", "1": "I", "2": "Z", "5": "S", "8": "B"}

        for idx, ch in enumerate(source_chars):
            prev_c = source_chars[idx - 1] if idx > 0 else ""
            next_c = source_chars[idx + 1] if idx < len(source_chars) - 1 else ""
            neighbor_digits = sum([prev_c.isdigit(), next_c.isdigit()])
            neighbor_alpha = sum([prev_c.isalpha(), next_c.isalpha()])

            if ch in digit_like and neighbor_digits > neighbor_alpha:
                chars[idx] = digit_like[ch]
            elif ch in alpha_like and neighbor_alpha > neighbor_digits:
                is_edge_single_alpha = (
                    idx in (0, len(source_chars) - 1) and neighbor_alpha == 1
                )
                if not is_edge_single_alpha:
                    chars[idx] = alpha_like[ch]

        return "".join(chars)

    @staticmethod
    def validate_plate(text: str) -> bool:
        """Validate a US-style plate string."""
        return bool(US_PLATE_REGEX.match(text))

    @property
    def inference_time_ms(self) -> float:
        return self._inference_time_ms

    def release(self):
        self.engine.release()
