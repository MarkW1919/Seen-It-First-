"""YOLOv8-based vehicle detection optimized for Jetson Orin Nano Super."""
import logging

import cv2
import numpy as np

from ai.tensorrt_utils import TRTEngine

logger = logging.getLogger(__name__)

VEHICLE_CLASSES = ["car", "truck", "suv", "van", "motorcycle", "bus"]


class VehicleDetector:
    def __init__(self, config: dict):
        self.config = config
        self.input_size = tuple(config.get("input_size", [640, 640]))
        self.conf_thresh = config.get("confidence_threshold", 0.5)
        self.nms_thresh = config.get("nms_threshold", 0.45)
        self.classes = config.get("classes", VEHICLE_CLASSES)

        self.engine = TRTEngine(
            engine_path=config["model_path"],
            onnx_path=config.get("onnx_path"),
        )

    def preprocess(self, frame: np.ndarray) -> tuple[np.ndarray, float, tuple[int, int]]:
        """Preprocess frame for YOLO input.

        Returns:
            Preprocessed tensor, scale factor, and padding offset
        """
        h, w = frame.shape[:2]
        target_h, target_w = self.input_size

        # Compute scale and padding (letterbox)
        scale = min(target_w / w, target_h / h)
        new_w, new_h = int(w * scale), int(h * scale)
        pad_w, pad_h = (target_w - new_w) // 2, (target_h - new_h) // 2

        resized = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
        padded = np.full((target_h, target_w, 3), 114, dtype=np.uint8)
        padded[pad_h : pad_h + new_h, pad_w : pad_w + new_w] = resized

        # HWC -> NCHW, normalize to [0, 1]
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
        """Postprocess YOLO outputs to detection dicts."""
        # YOLOv8 output: [1, 4+num_classes, num_boxes] (transposed)
        preds = outputs[0]
        if preds.ndim == 3:
            preds = preds.squeeze(0)
        if preds.shape[0] < preds.shape[1]:
            preds = preds.T  # [num_boxes, 4+num_classes]

        boxes = preds[:, :4]
        scores = preds[:, 4:]

        # Get best class per box
        class_ids = np.argmax(scores, axis=1)
        max_scores = scores[np.arange(len(scores)), class_ids]

        # Filter by confidence
        mask = max_scores >= self.conf_thresh
        boxes = boxes[mask]
        max_scores = max_scores[mask]
        class_ids = class_ids[mask]

        if len(boxes) == 0:
            return []

        # Convert from center format to corner format
        x1 = boxes[:, 0] - boxes[:, 2] / 2
        y1 = boxes[:, 1] - boxes[:, 3] / 2
        x2 = boxes[:, 0] + boxes[:, 2] / 2
        y2 = boxes[:, 1] + boxes[:, 3] / 2

        # Remove padding and scale back
        pad_w, pad_h = pad
        x1 = (x1 - pad_w) / scale
        y1 = (y1 - pad_h) / scale
        x2 = (x2 - pad_w) / scale
        y2 = (y2 - pad_h) / scale

        # Clip to frame
        orig_h, orig_w = orig_shape
        x1 = np.clip(x1, 0, orig_w)
        y1 = np.clip(y1, 0, orig_h)
        x2 = np.clip(x2, 0, orig_w)
        y2 = np.clip(y2, 0, orig_h)

        # NMS
        indices = cv2.dnn.NMSBoxes(
            bboxes=np.column_stack([x1, y1, x2 - x1, y2 - y1]).tolist(),
            scores=max_scores.tolist(),
            score_threshold=self.conf_thresh,
            nms_threshold=self.nms_thresh,
        )

        detections = []
        for i in indices:
            idx = i[0] if isinstance(i, (list, np.ndarray)) else i
            cls_id = class_ids[idx]
            if cls_id < len(self.classes):
                detections.append(
                    {
                        "class": self.classes[cls_id],
                        "confidence": float(max_scores[idx]),
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
        """Run vehicle detection on a frame.

        Args:
            frame: BGR image as numpy array

        Returns:
            List of detection dicts with class, confidence, bbox
        """
        if not self.engine.is_loaded:
            return []

        blob, scale, pad = self.preprocess(frame)
        outputs = self.engine.infer(blob)
        return self.postprocess(outputs, scale, pad, frame.shape[:2])
