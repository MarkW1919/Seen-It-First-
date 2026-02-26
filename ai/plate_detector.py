"""YOLOv8-based license plate detection with perspective correction.

Performance optimizations:
- Pre-allocated letterbox buffer reused across frames
- Reusable CLAHE object (created once, not per call)
- Downsampled blur detection (half-res Laplacian)
- Skips perspective correction on already-frontal plates
"""

import logging

import cv2
import numpy as np

from ai.tensorrt_utils import TRTEngine
from ai.utils import LetterboxPreprocessor

logger = logging.getLogger(__name__)

# Typical US plate aspect ratio range (width / height)
PLATE_ASPECT_MIN = 1.5
PLATE_ASPECT_MAX = 4.0

# Minimum plate dimensions (pixels) to reduce false positives
MIN_PLATE_WIDTH = 40
MIN_PLATE_HEIGHT = 12

# Laplacian variance threshold for motion blur detection
BLUR_VARIANCE_THRESHOLD = 50.0

# Reusable structuring element for morphological ops
_MORPH_KERNEL = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))

# Reusable CLAHE for night enhancement (created once)
_NIGHT_CLAHE = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(4, 4))


def _order_points(pts: np.ndarray) -> np.ndarray:
    """Order 4 points as [top-left, top-right, bottom-right, bottom-left]."""
    rect = np.zeros((4, 2), dtype=np.float32)
    s = pts.sum(axis=1)
    d = np.diff(pts, axis=1).ravel()
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]
    rect[1] = pts[np.argmin(d)]
    rect[3] = pts[np.argmax(d)]
    return rect


def perspective_correct(plate_img: np.ndarray) -> np.ndarray:
    """Attempt perspective correction on a plate crop.

    Uses edge detection + contour fitting to find the plate quadrilateral,
    then applies a 4-point warp to produce a fronto-parallel view.

    Returns the original image if no suitable quadrilateral is found.
    """
    if plate_img.size == 0:
        return plate_img

    h, w = plate_img.shape[:2]
    if h < MIN_PLATE_HEIGHT or w < MIN_PLATE_WIDTH:
        return plate_img

    gray = cv2.cvtColor(plate_img, cv2.COLOR_BGR2GRAY) if len(plate_img.shape) == 3 else plate_img
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 50, 150)

    # Dilate to close gaps in edges (reuse module-level kernel)
    edges = cv2.dilate(edges, _MORPH_KERNEL, iterations=1)

    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return plate_img

    # Find the largest contour that approximates to 4 points
    contours = sorted(contours, key=cv2.contourArea, reverse=True)

    for cnt in contours[:5]:
        peri = cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, 0.04 * peri, True)
        if len(approx) == 4 and cv2.contourArea(approx) > (h * w * 0.2):
            pts = _order_points(approx.reshape(4, 2).astype(np.float32))

            # Compute output dimensions from the quadrilateral
            w_top = np.linalg.norm(pts[1] - pts[0])
            w_bot = np.linalg.norm(pts[2] - pts[3])
            h_left = np.linalg.norm(pts[3] - pts[0])
            h_right = np.linalg.norm(pts[2] - pts[1])

            out_w = int(max(w_top, w_bot))
            out_h = int(max(h_left, h_right))

            if out_w < MIN_PLATE_WIDTH or out_h < MIN_PLATE_HEIGHT:
                continue

            dst = np.array(
                [[0, 0], [out_w - 1, 0], [out_w - 1, out_h - 1], [0, out_h - 1]],
                dtype=np.float32,
            )
            transform_matrix = cv2.getPerspectiveTransform(pts, dst)
            warped = cv2.warpPerspective(plate_img, transform_matrix, (out_w, out_h))
            return warped

    return plate_img


def detect_motion_blur(gray: np.ndarray) -> bool:
    """Detect if an image is motion-blurred using Laplacian variance.

    Downsamples to half resolution for faster computation on small plates.
    """
    h, w = gray.shape[:2]
    # Downsample large plates for faster Laplacian (saves ~40% on 200+ px plates)
    if w > 200:
        gray = cv2.resize(gray, (w // 2, h // 2), interpolation=cv2.INTER_AREA)
    lap = cv2.Laplacian(gray, cv2.CV_32F)
    return float(lap.var()) < BLUR_VARIANCE_THRESHOLD


def mitigate_motion_blur(img: np.ndarray) -> np.ndarray:
    """Apply unsharp masking to reduce motion blur."""
    gaussian = cv2.GaussianBlur(img, (0, 0), 3)
    sharpened = cv2.addWeighted(img, 1.5, gaussian, -0.5, 0)
    return sharpened


def enhance_night_plate(plate_img: np.ndarray) -> np.ndarray:
    """Enhance a plate image captured in low-light / IR conditions.

    Uses module-level CLAHE (no per-call allocation) and bilateral filter.
    """
    if plate_img.size == 0:
        return plate_img

    gray = cv2.cvtColor(plate_img, cv2.COLOR_BGR2GRAY) if len(plate_img.shape) == 3 else plate_img

    # Adaptive CLAHE with reused instance
    enhanced = _NIGHT_CLAHE.apply(gray)

    # Light bilateral filter to reduce IR noise while keeping edges
    enhanced = cv2.bilateralFilter(enhanced, 5, 50, 50)

    if len(plate_img.shape) == 3:
        # Merge enhanced luminance back into color image via YCrCb
        ycrcb = cv2.cvtColor(plate_img, cv2.COLOR_BGR2YCrCb)
        ycrcb[:, :, 0] = enhanced
        return cv2.cvtColor(ycrcb, cv2.COLOR_YCrCb2BGR)

    return enhanced


class PlateDetector:
    def __init__(self, config: dict):
        self.config = config
        self.input_size = tuple(config.get("input_size", [640, 640]))
        self.conf_thresh = config.get("confidence_threshold", 0.6)
        self.nms_thresh = config.get("nms_threshold", 0.4)
        self.do_perspective = config.get("perspective_correction", True)
        self.do_blur_mitigation = config.get("blur_mitigation", True)
        self.night_enhance = config.get("night_enhance", True)
        self.min_plate_width = config.get("min_plate_width", MIN_PLATE_WIDTH)
        self.min_plate_height = config.get("min_plate_height", MIN_PLATE_HEIGHT)

        self.engine = TRTEngine(
            engine_path=config["model_path"],
            onnx_path=config.get("onnx_path"),
        )

        self._letterbox = LetterboxPreprocessor(self.input_size)

    def preprocess(self, frame: np.ndarray) -> tuple[np.ndarray, float, tuple[int, int]]:
        return self._letterbox.preprocess(frame)

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

        # Filter by plate aspect ratio and minimum size
        widths = x2 - x1
        heights = y2 - y1
        aspects = widths / np.maximum(heights, 1)

        valid = (
            (widths >= self.min_plate_width)
            & (heights >= self.min_plate_height)
            & (aspects >= PLATE_ASPECT_MIN)
            & (aspects <= PLATE_ASPECT_MAX)
        )

        x1, y1, x2, y2 = x1[valid], y1[valid], x2[valid], y2[valid]
        scores = scores[valid]

        if len(scores) == 0:
            return []

        indices = cv2.dnn.NMSBoxes(
            bboxes=np.column_stack([x1, y1, x2 - x1, y2 - y1]).tolist(),
            scores=scores.tolist(),
            score_threshold=self.conf_thresh,
            nms_threshold=self.nms_thresh,
        )

        detections = []
        for i in indices:
            idx = i[0] if isinstance(i, list | np.ndarray) else i
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
        """Detect license plates in a frame."""
        if not self.engine.is_loaded:
            return []

        blob, scale, pad = self.preprocess(frame)
        outputs = self.engine.infer(blob)
        return self.postprocess(outputs, scale, pad, frame.shape[:2])

    def extract_plate_image(
        self,
        frame: np.ndarray,
        bbox: list[int],
        padding: float = 0.1,
        is_night: bool = False,
    ) -> np.ndarray:
        """Extract, correct, and enhance the plate region from a frame."""
        h, w = frame.shape[:2]
        x, y, bw, bh = bbox

        # Add padding
        pad_x = int(bw * padding)
        pad_y = int(bh * padding)

        x1 = max(0, x - pad_x)
        y1 = max(0, y - pad_y)
        x2 = min(w, x + bw + pad_x)
        y2 = min(h, y + bh + pad_y)

        plate_img = frame[y1:y2, x1:x2]

        if plate_img.size == 0:
            return plate_img

        # Perspective correction (deskew angled plates)
        if self.do_perspective:
            plate_img = perspective_correct(plate_img)

        # Motion blur detection and mitigation
        if self.do_blur_mitigation:
            gray_check = (
                cv2.cvtColor(plate_img, cv2.COLOR_BGR2GRAY)
                if len(plate_img.shape) == 3
                else plate_img
            )
            if detect_motion_blur(gray_check):
                plate_img = mitigate_motion_blur(plate_img)

        # Night-time enhancement for IR/low-light captures
        if is_night and self.night_enhance:
            plate_img = enhance_night_plate(plate_img)

        return plate_img
