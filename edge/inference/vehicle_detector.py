"""
Vehicle detection using YOLOv8n TensorRT engine.

Runs at 12-15 FPS on full frames. Outputs bounding boxes for vehicles
(car, truck, bus, motorcycle) to feed into plate detection.
"""

import logging
import time
from dataclasses import dataclass

import cv2
import numpy as np

from edge.inference.tensorrt_utils import TRTEngine

logger = logging.getLogger(__name__)

# COCO class IDs for vehicles
VEHICLE_CLASS_IDS = {2, 3, 5, 7}  # car, motorcycle, bus, truck
VEHICLE_CLASS_NAMES = {2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}


@dataclass
class VehicleDetection:
    """A detected vehicle bounding box."""
    x1: int
    y1: int
    x2: int
    y2: int
    confidence: float
    class_id: int
    class_name: str


class VehicleDetector:
    """
    YOLOv8n vehicle detector.

    Phase 1: Uses pretrained YOLOv8n (COCO). No custom training required.
    Fine-tuning pipeline deferred to Phase 3.

    Model: YOLOv8n (COCO pretrained) → TensorRT FP16
    Input: 640x640 RGB
    Engine size: ~12 MB
    VRAM footprint: ~45 MB
    """

    def __init__(self, config: dict):
        self.model_path = config["model_path"]
        self.input_size = config.get("input_size", 640)
        self.conf_threshold = config.get("confidence_threshold", 0.45)
        self.nms_threshold = config.get("nms_threshold", 0.5)
        self.engine = TRTEngine(self.model_path)
        self._inference_time_ms = 0.0

    def load(self) -> bool:
        """Load the TensorRT engine."""
        return self.engine.load()

    @property
    def is_loaded(self) -> bool:
        return self.engine.is_loaded

    def detect(self, frame: np.ndarray) -> list[VehicleDetection]:
        """
        Detect vehicles in a frame.

        Args:
            frame: BGR image from camera (HWC format).

        Returns:
            List of VehicleDetection objects for vehicles only.
        """
        orig_h, orig_w = frame.shape[:2]

        # Preprocess: resize, normalize, NCHW, RGB
        blob = self._preprocess(frame)

        # Inference
        t0 = time.monotonic()
        outputs = self.engine.infer(blob)
        self._inference_time_ms = (time.monotonic() - t0) * 1000

        # Postprocess: extract vehicle boxes
        detections = self._postprocess(outputs, orig_w, orig_h)
        return detections

    def _preprocess(self, frame: np.ndarray) -> np.ndarray:
        """Resize, normalize, convert to NCHW RGB float32."""
        resized = cv2.resize(frame, (self.input_size, self.input_size))
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        blob = rgb.astype(np.float32) / 255.0
        blob = blob.transpose(2, 0, 1)  # HWC → CHW
        blob = np.expand_dims(blob, axis=0)  # add batch dim
        return np.ascontiguousarray(blob)

    def _postprocess(
        self, outputs: list[np.ndarray], orig_w: int, orig_h: int
    ) -> list[VehicleDetection]:
        """
        Parse YOLOv8 output tensor and apply NMS.

        YOLOv8 output shape: [1, 84, 8400] (transposed to [8400, 84])
        Columns: cx, cy, w, h, class_scores[80]
        """
        raw = outputs[0]

        # Handle both [1, 84, 8400] and [1, 8400, 84]
        if raw.shape[1] == 84:
            predictions = raw[0].T  # [8400, 84]
        else:
            predictions = raw[0]

        # Extract boxes and class scores
        cx = predictions[:, 0]
        cy = predictions[:, 1]
        w = predictions[:, 2]
        h = predictions[:, 3]
        class_scores = predictions[:, 4:]

        # Get best class per detection
        class_ids = np.argmax(class_scores, axis=1)
        confidences = np.max(class_scores, axis=1)

        # Filter: confidence threshold + vehicle classes only
        mask = confidences > self.conf_threshold
        vehicle_mask = np.isin(class_ids, list(VEHICLE_CLASS_IDS))
        keep = mask & vehicle_mask

        if not np.any(keep):
            return []

        cx, cy, w, h = cx[keep], cy[keep], w[keep], h[keep]
        confidences = confidences[keep]
        class_ids = class_ids[keep]

        # Convert center-wh to xyxy, scale to original image
        scale_x = orig_w / self.input_size
        scale_y = orig_h / self.input_size

        x1 = ((cx - w / 2) * scale_x).astype(int)
        y1 = ((cy - h / 2) * scale_y).astype(int)
        x2 = ((cx + w / 2) * scale_x).astype(int)
        y2 = ((cy + h / 2) * scale_y).astype(int)

        # Clip to image bounds
        x1 = np.clip(x1, 0, orig_w)
        y1 = np.clip(y1, 0, orig_h)
        x2 = np.clip(x2, 0, orig_w)
        y2 = np.clip(y2, 0, orig_h)

        # NMS
        boxes = np.stack([x1, y1, x2, y2], axis=1).tolist()
        confs = confidences.tolist()
        indices = cv2.dnn.NMSBoxes(
            [(b[0], b[1], b[2] - b[0], b[3] - b[1]) for b in boxes],
            confs,
            self.conf_threshold,
            self.nms_threshold,
        )

        detections = []
        if len(indices) > 0:
            for idx in indices.flatten():
                det = VehicleDetection(
                    x1=boxes[idx][0],
                    y1=boxes[idx][1],
                    x2=boxes[idx][2],
                    y2=boxes[idx][3],
                    confidence=confs[idx],
                    class_id=int(class_ids[idx]),
                    class_name=VEHICLE_CLASS_NAMES.get(int(class_ids[idx]), "vehicle"),
                )
                detections.append(det)

        return detections

    @property
    def inference_time_ms(self) -> float:
        return self._inference_time_ms

    def release(self):
        self.engine.release()
