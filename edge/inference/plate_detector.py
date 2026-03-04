"""
License plate detection using YOLOv8s TensorRT engine.

Runs ONLY on cropped vehicle bounding boxes from vehicle_detector.
Outputs plate bounding boxes relative to the original frame.
"""

import logging
import time
from dataclasses import dataclass

import cv2
import numpy as np

from edge.inference.tensorrt_utils import TRTEngine
from edge.inference.vehicle_detector import VehicleDetection

logger = logging.getLogger(__name__)


@dataclass
class PlateDetection:
    """A detected license plate."""
    x1: int
    y1: int
    x2: int
    y2: int
    confidence: float
    vehicle_box: VehicleDetection  # parent vehicle


class PlateDetector:
    """
    YOLOv8s plate detector.

    Model: YOLOv8s fine-tuned on US license plate datasets → TensorRT FP16
    Input: 640x640 RGB (vehicle crop)
    Engine size: ~45 MB
    VRAM footprint: ~90 MB
    """

    def __init__(self, config: dict):
        self.model_path = config["model_path"]
        self.input_size = config.get("input_size", 640)
        self.conf_threshold = config.get("confidence_threshold", 0.50)
        self.nms_threshold = config.get("nms_threshold", 0.4)
        self.engine = TRTEngine(self.model_path)
        self._inference_time_ms = 0.0

    def load(self) -> bool:
        return self.engine.load()

    def detect(
        self, frame: np.ndarray, vehicles: list[VehicleDetection]
    ) -> list[PlateDetection]:
        """
        Detect plates within each vehicle bounding box.

        Args:
            frame: Full BGR frame.
            vehicles: Vehicle detections from VehicleDetector.

        Returns:
            List of PlateDetection with coordinates in original frame space.
        """
        all_plates = []

        for vehicle in vehicles:
            # Crop vehicle region with padding
            crop, offset_x, offset_y = self._crop_vehicle(frame, vehicle)
            if crop is None:
                continue

            blob = self._preprocess(crop)

            t0 = time.monotonic()
            outputs = self.engine.infer(blob)
            self._inference_time_ms = (time.monotonic() - t0) * 1000

            plates = self._postprocess(
                outputs, crop.shape[1], crop.shape[0],
                offset_x, offset_y, vehicle,
            )
            all_plates.extend(plates)

        return all_plates

    def _crop_vehicle(
        self, frame: np.ndarray, vehicle: VehicleDetection
    ) -> tuple:
        """Crop vehicle region with 10% padding."""
        h, w = frame.shape[:2]
        vw = vehicle.x2 - vehicle.x1
        vh = vehicle.y2 - vehicle.y1
        pad_x = int(vw * 0.1)
        pad_y = int(vh * 0.1)

        x1 = max(0, vehicle.x1 - pad_x)
        y1 = max(0, vehicle.y1 - pad_y)
        x2 = min(w, vehicle.x2 + pad_x)
        y2 = min(h, vehicle.y2 + pad_y)

        crop = frame[y1:y2, x1:x2]
        if crop.size == 0:
            return None, 0, 0

        return crop, x1, y1

    def _preprocess(self, crop: np.ndarray) -> np.ndarray:
        """Resize, normalize, NCHW RGB."""
        resized = cv2.resize(crop, (self.input_size, self.input_size))
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        blob = rgb.astype(np.float32) / 255.0
        blob = blob.transpose(2, 0, 1)
        blob = np.expand_dims(blob, axis=0)
        return np.ascontiguousarray(blob)

    def _postprocess(
        self,
        outputs: list[np.ndarray],
        crop_w: int,
        crop_h: int,
        offset_x: int,
        offset_y: int,
        vehicle: VehicleDetection,
    ) -> list[PlateDetection]:
        """Parse YOLOv8 output for single-class plate detection."""
        raw = outputs[0]

        # Single-class: shape [1, 5, N] → cx, cy, w, h, conf
        if raw.ndim == 3:
            if raw.shape[1] == 5:
                predictions = raw[0].T
            elif raw.shape[2] == 5:
                predictions = raw[0]
            else:
                # Multi-class format [1, 4+C, N]
                predictions = raw[0].T
        else:
            return []

        if predictions.shape[0] == 0:
            return []

        cx = predictions[:, 0]
        cy = predictions[:, 1]
        w = predictions[:, 2]
        h = predictions[:, 3]

        # For single-class, confidence is column 4
        # For multi-class, take max of class scores
        if predictions.shape[1] == 5:
            confidences = predictions[:, 4]
        else:
            confidences = np.max(predictions[:, 4:], axis=1)

        mask = confidences > self.conf_threshold
        if not np.any(mask):
            return []

        cx, cy, w, h = cx[mask], cy[mask], w[mask], h[mask]
        confidences = confidences[mask]

        # Scale from input_size to crop size, then offset to frame coords
        scale_x = crop_w / self.input_size
        scale_y = crop_h / self.input_size

        x1 = ((cx - w / 2) * scale_x + offset_x).astype(int)
        y1 = ((cy - h / 2) * scale_y + offset_y).astype(int)
        x2 = ((cx + w / 2) * scale_x + offset_x).astype(int)
        y2 = ((cy + h / 2) * scale_y + offset_y).astype(int)

        # NMS
        boxes = np.stack([x1, y1, x2, y2], axis=1).tolist()
        confs = confidences.tolist()
        indices = cv2.dnn.NMSBoxes(
            [(b[0], b[1], b[2] - b[0], b[3] - b[1]) for b in boxes],
            confs,
            self.conf_threshold,
            self.nms_threshold,
        )

        plates = []
        if len(indices) > 0:
            for idx in indices.flatten():
                plates.append(PlateDetection(
                    x1=boxes[idx][0],
                    y1=boxes[idx][1],
                    x2=boxes[idx][2],
                    y2=boxes[idx][3],
                    confidence=confs[idx],
                    vehicle_box=vehicle,
                ))

        return plates

    @property
    def inference_time_ms(self) -> float:
        return self._inference_time_ms

    def release(self):
        self.engine.release()
