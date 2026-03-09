"""License plate OCR using PaddleOCR PP-OCRv4 TensorRT engine.

This module is production-focused around pretrained models with lightweight
post-processing for US plate constraints. It provides:

- PP-OCRv4 TensorRT inference.
- CTC greedy decoding.
- US-format cleanup and validation.
- Optional ambiguity correction for OCR confusions (e.g. ``O`` vs ``0``).
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

# ---------------------------------------------------------------------------
# PaddleOCR PP-OCRv4 English character set
# Standard en_dict.txt: 96 printable ASCII chars (space … ~), blank = index 96
# ---------------------------------------------------------------------------
PADDLE_OCR_CHARS = (
    " !\"#$%&'()*+,-./"
    "0123456789"
    ":;<=>?@"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "[\\]^_`"
    "abcdefghijklmnopqrstuvwxyz"
    "{|}~"
)
# blank token index for CTC (last class)
_BLANK_IDX = len(PADDLE_OCR_CHARS)

# US plate validation: 2-8 alphanumeric characters
US_PLATE_REGEX = re.compile(r"^[A-Z0-9]{2,8}$")


@dataclass
class OCRResult:
    """OCR result for a single plate."""
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

    Model: PP-OCRv4 English rec → ONNX → TensorRT FP16
    Input: [1, 3, 48, 320] RGB, normalised mean=0.5 std=0.5
    Engine size: ~8 MB
    VRAM footprint: ~30 MB
    """

    # PP-OCRv4 normalisation constants
    _MEAN = np.array([0.5, 0.5, 0.5], dtype=np.float32)
    _STD  = np.array([0.5, 0.5, 0.5], dtype=np.float32)

    def __init__(self, config: dict):
        self.model_path = config["model_path"]
        self.input_width  = config.get("input_width",  320)
        self.input_height = config.get("input_height",  48)
        self.conf_threshold = config.get("confidence_threshold", 0.60)
        self.min_chars = config.get("min_plate_chars", 2)
        self.max_chars = config.get("max_plate_chars", 8)
        self.enable_ambiguity_correction = config.get(
            "enable_ambiguity_correction", True
        )
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
        """
        Run OCR on detected plate regions.

        Args:
            frame: Full BGR frame.
            plates: Plate detections from PlateDetector.
            night_mode: If True, apply CLAHE enhancement to plate ROI.

        Returns:
            List of OCRResult with cleaned, validated plate text.
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
            if self.enable_ambiguity_correction:
                cleaned = self._resolve_ambiguities(cleaned)

            if confidence >= self.conf_threshold and self.validate_plate(cleaned):
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
        """
        Prepare plate crop for PP-OCRv4 recognition.

        - Convert BGR → RGB
        - Resize to (input_width, input_height) = (320, 48)
        - Normalise: (pixel/255 - 0.5) / 0.5  → range [-1, 1]
        - Layout: [1, 3, H, W] float32
        """
        rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
        resized = cv2.resize(rgb, (self.input_width, self.input_height))
        blob = resized.astype(np.float32) / 255.0
        blob = (blob - self._MEAN) / self._STD          # normalise
        blob = blob.transpose(2, 0, 1)                  # HWC → CHW
        blob = np.expand_dims(blob, axis=0)             # add batch dim → NCHW
        return np.ascontiguousarray(blob)

    def _decode_ctc(self, outputs: list[np.ndarray]) -> tuple[str, float]:
        """
        CTC greedy decode for PP-OCRv4 output.

        PP-OCRv4 rec output shape: [1, T, num_chars+1]
        where T ≈ input_width/4 and the last class is the CTC blank.
        """
        raw = outputs[0]

        # Normalise to [T, num_chars+1]
        if raw.ndim == 3:
            logits = raw[0]          # [T, num_chars+1]
        elif raw.ndim == 2:
            logits = raw
        else:
            return "", 0.0

        # Softmax
        exp_l = np.exp(logits - np.max(logits, axis=1, keepdims=True))
        probs = exp_l / np.sum(exp_l, axis=1, keepdims=True)

        char_indices = np.argmax(probs, axis=1)
        char_probs   = np.max(probs, axis=1)

        chars: list[str] = []
        confidences: list[float] = []
        prev_idx = -1

        for t in range(len(char_indices)):
            idx = int(char_indices[t])
            if idx != _BLANK_IDX and idx != prev_idx:
                if idx < len(PADDLE_OCR_CHARS):
                    chars.append(PADDLE_OCR_CHARS[idx])
                    confidences.append(float(char_probs[t]))
            prev_idx = idx

        text = "".join(chars)
        avg_conf = float(np.mean(confidences)) if confidences else 0.0
        return text, avg_conf

    def _postprocess_text(self, text: str) -> str:
        """
        Rule-based cleaning for US license plates.

        - Uppercase normalization.
        - Strip spaces and non-alphanumeric characters.
        """
        cleaned = text.upper().strip()
        cleaned = re.sub(r"[^A-Z0-9]", "", cleaned)
        if len(cleaned) > self.max_chars:
            cleaned = cleaned[:self.max_chars]
        return cleaned

    def _resolve_ambiguities(self, text: str) -> str:
        """Correct common OCR confusions for mixed alphanumeric plates.

        The heuristic preserves mixed letter/digit structure while correcting
        obvious runs: long digit runs use number-safe replacements and long
        alpha runs use letter-safe replacements.
        """
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
                is_edge_single_alpha = idx in (0, len(source_chars) - 1) and neighbor_alpha == 1
                if not is_edge_single_alpha:
                    chars[idx] = alpha_like[ch]

        return "".join(chars)

    @staticmethod
    def validate_plate(text: str) -> bool:
        """Validate a plate string against US plate format.

        US plates only: 2-8 uppercase alphanumeric characters.
        No EU/International formats supported in Phase 1.
        """
        return bool(US_PLATE_REGEX.match(text))

    @property
    def inference_time_ms(self) -> float:
        return self._inference_time_ms

    def release(self):
        self.engine.release()
