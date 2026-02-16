"""YOLOv8-based license plate detection."""
import logging

import cv2
import numpy as np

from ai.tensorrt_utils import TRTEngine

logger = logging.getLogger(__name__)


class PlateDetector:
    def __init__(self, config: dict):
        self.config = config
        self.input_size = tuple(config.get("input_size", [640, 640]))
        self.conf_thresh = config.get("confidence_threshold", 0.6)
        self.nms_thresh = config.get("nms_threshold", 0.4)

        self.engine = TRTEngine(
            engine_path=config["model_path"],
            onnx_path=config.get("onnx_path"),
        )

    def preprocess(self, frame: np.ndarray) -> tuple[np.ndarray, float, tuple[int, int]]:
        h, w = frame.shape[:2]
        target_h, target_w = self.input_size
        scale = min(target_w / w, target_h / h)
        new_w, new_h = int(w * scale), int(h * scale)
        pad_w, pad_h = (target_w - new_w) // 2, (target_h - new_h) // 2

        resized = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
        padded = np.full((target_h, target_w, 3), 114, dtype=np.uint8)
        padded[pad_h : pad_h + new_h, pad_w : pad_w + new_w] = resized

        blob = padded.astype(np.float32) / 255.0
        blob = blob.transpose(2, 0, 1)[np.newaxis, ...]
        return blob, scale, (pad_w, pad_h)

    def postprocess(
        self,
        outputs: list[np.ndarray],
        scale: float,
        pad: tuple[int, int],
        orig_shape: tuple[int, int],
    ) -> list[dict]:
        preds = outputs[0]
        if preds.ndim == 3:
            preds = preds.squeeze(0)
        if preds.shape[0] < preds.shape[1]:
            preds = preds.T

        boxes = preds[:, :4]
        scores = preds[:, 4] if preds.shape[1] == 5 else np.max(preds[:, 4:], axis=1)

        mask = scores >= self.conf_thresh
        boxes = boxes[mask]
        scores = scores[mask]

        if len(boxes) == 0:
            return []

        x1 = boxes[:, 0] - boxes[:, 2] / 2
        y1 = boxes[:, 1] - boxes[:, 3] / 2
        x2 = boxes[:, 0] + boxes[:, 2] / 2
        y2 = boxes[:, 1] + boxes[:, 3] / 2

        pad_w, pad_h = pad
        x1 = (x1 - pad_w) / scale
        y1 = (y1 - pad_h) / scale
        x2 = (x2 - pad_w) / scale
        y2 = (y2 - pad_h) / scale

        orig_h, orig_w = orig_shape
        x1 = np.clip(x1, 0, orig_w)
        y1 = np.clip(y1, 0, orig_h)
        x2 = np.clip(x2, 0, orig_w)
        y2 = np.clip(y2, 0, orig_h)

        indices = cv2.dnn.NMSBoxes(
            bboxes=np.column_stack([x1, y1, x2 - x1, y2 - y1]).tolist(),
            scores=scores.tolist(),
            score_threshold=self.conf_thresh,
            nms_threshold=self.nms_thresh,
        )

        detections = []
        for i in indices:
            idx = i[0] if isinstance(i, (list, np.ndarray)) else i
            detections.append(
                {
                    "confidence": float(scores[idx]),
                    "bbox": [
                        int(x1[idx]),
                        int(y1[idx]),
                        int(x2[idx] - x1[idx]),
                        int(y2[idx] - y1[idx]),
                    ],
                }
            )

        return detections

    def detect(self, frame: np.ndarray) -> list[dict]:
        """Detect license plates in a frame.

        Args:
            frame: BGR image

        Returns:
            List of plate detection dicts with confidence and bbox
        """
        if not self.engine.is_loaded:
            return []

        blob, scale, pad = self.preprocess(frame)
        outputs = self.engine.infer(blob)
        return self.postprocess(outputs, scale, pad, frame.shape[:2])

    def extract_plate_image(
        self, frame: np.ndarray, bbox: list[int], padding: float = 0.1
    ) -> np.ndarray:
        """Extract and pad the plate region from a frame.

        Args:
            frame: Full frame
            bbox: [x, y, w, h] bounding box
            padding: Fraction of padding to add around plate

        Returns:
            Cropped plate image
        """
        h, w = frame.shape[:2]
        x, y, bw, bh = bbox

        # Add padding
        pad_x = int(bw * padding)
        pad_y = int(bh * padding)

        x1 = max(0, x - pad_x)
        y1 = max(0, y - pad_y)
        x2 = min(w, x + bw + pad_x)
        y2 = min(h, y + bh + pad_y)

        return frame[y1:y2, x1:x2]
