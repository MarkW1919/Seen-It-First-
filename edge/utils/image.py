"""
SEEN IT FIRST - Image Utility Functions

OpenCV / NumPy helpers for the edge inference pipeline.  All functions
operate on BGR ``numpy.ndarray`` images (the OpenCV default).

Usage:
    from edge.utils.image import resize_with_pad, crop_roi, save_snapshot
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Sequence, Tuple

import cv2
import numpy as np

from edge.utils.logging import get_logger

logger = get_logger("utils.image")

# Type alias for a bounding-box tuple: (x, y, width, height)
BBox = Tuple[int, int, int, int]


# ---------------------------------------------------------------------------
# Detection dataclass-style dict keys expected by draw_detections()
# ---------------------------------------------------------------------------
# Each detection is a dict with at minimum:
#   bbox: (x, y, w, h)            -- bounding box in pixel coords
#   label: str                     -- text to render (e.g. "car 0.91")
#   color: (B, G, R) | optional   -- box colour, default green


def resize_with_pad(
    image: np.ndarray,
    target_w: int,
    target_h: int,
    pad_color: Tuple[int, int, int] = (114, 114, 114),
) -> np.ndarray:
    """
    Resize *image* to fit inside ``(target_w, target_h)`` while preserving
    aspect ratio, then pad the remaining area with *pad_color*.

    Parameters
    ----------
    image : np.ndarray
        Source BGR image.
    target_w : int
        Target canvas width in pixels.
    target_h : int
        Target canvas height in pixels.
    pad_color : tuple of int
        BGR colour for the padding border.

    Returns
    -------
    np.ndarray
        Padded image of shape ``(target_h, target_w, 3)``.
    """
    if image is None or image.size == 0:
        logger.warning("resize_with_pad received empty image, returning blank canvas")
        return np.full((target_h, target_w, 3), pad_color, dtype=np.uint8)

    src_h, src_w = image.shape[:2]
    scale = min(target_w / src_w, target_h / src_h)
    new_w = int(round(src_w * scale))
    new_h = int(round(src_h * scale))

    resized = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_LINEAR)

    canvas = np.full((target_h, target_w, 3), pad_color, dtype=np.uint8)
    x_offset = (target_w - new_w) // 2
    y_offset = (target_h - new_h) // 2
    canvas[y_offset:y_offset + new_h, x_offset:x_offset + new_w] = resized

    logger.debug(
        "resize_with_pad complete",
        extra={
            "src": f"{src_w}x{src_h}",
            "dst": f"{target_w}x{target_h}",
            "scale": round(scale, 4),
        },
    )
    return canvas


def crop_roi(
    image: np.ndarray,
    bbox: BBox,
) -> np.ndarray:
    """
    Crop a rectangular region of interest from *image*.

    Parameters
    ----------
    image : np.ndarray
        Source BGR image.
    bbox : tuple
        ``(x, y, w, h)`` bounding box in pixel coordinates.

    Returns
    -------
    np.ndarray
        Cropped sub-image.  Returns a 1x1 black pixel array if the crop
        would be degenerate.
    """
    x, y, w, h = bbox
    img_h, img_w = image.shape[:2]

    # Clamp to image boundaries
    x1 = max(0, int(x))
    y1 = max(0, int(y))
    x2 = min(img_w, int(x + w))
    y2 = min(img_h, int(y + h))

    if x2 <= x1 or y2 <= y1:
        logger.warning(
            "crop_roi produced degenerate crop",
            extra={"bbox": bbox, "image_size": f"{img_w}x{img_h}"},
        )
        return np.zeros((1, 1, 3), dtype=np.uint8)

    return image[y1:y2, x1:x2].copy()


def draw_detections(
    image: np.ndarray,
    detections: Sequence[dict],
    thickness: int = 2,
    font_scale: float = 0.6,
) -> np.ndarray:
    """
    Draw bounding boxes and labels onto a copy of *image*.

    Parameters
    ----------
    image : np.ndarray
        Source BGR image (will NOT be modified in place).
    detections : sequence of dict
        Each dict must contain:
          - ``bbox``: ``(x, y, w, h)``
          - ``label``: ``str``
        Optional:
          - ``color``: ``(B, G, R)`` tuple (default: green)
    thickness : int
        Line thickness for bounding boxes.
    font_scale : float
        OpenCV font scale for label text.

    Returns
    -------
    np.ndarray
        Annotated copy of the image.
    """
    annotated = image.copy()

    for det in detections:
        bbox = det.get("bbox")
        label = det.get("label", "")
        color = det.get("color", (0, 255, 0))  # default green

        if bbox is None:
            continue

        x, y, w, h = [int(v) for v in bbox]

        # Bounding box
        cv2.rectangle(annotated, (x, y), (x + w, y + h), color, thickness)

        # Label background
        if label:
            (text_w, text_h), baseline = cv2.getTextSize(
                label, cv2.FONT_HERSHEY_SIMPLEX, font_scale, 1,
            )
            # Draw filled rectangle behind the label text
            label_y = max(y, text_h + baseline + 4)
            cv2.rectangle(
                annotated,
                (x, label_y - text_h - baseline - 4),
                (x + text_w + 4, label_y),
                color,
                cv2.FILLED,
            )
            # Draw label text in contrasting colour
            cv2.putText(
                annotated,
                label,
                (x + 2, label_y - baseline - 2),
                cv2.FONT_HERSHEY_SIMPLEX,
                font_scale,
                (0, 0, 0),
                1,
                cv2.LINE_AA,
            )

    logger.debug(
        "draw_detections complete",
        extra={"detection_count": len(detections)},
    )
    return annotated


def save_snapshot(
    image: np.ndarray,
    path: str,
    quality: int = 85,
) -> bool:
    """
    Save *image* as a JPEG file at *path*.

    Parameters
    ----------
    image : np.ndarray
        BGR image to save.
    path : str
        Destination file path.  Parent directories are created if needed.
    quality : int
        JPEG quality (0-100).

    Returns
    -------
    bool
        ``True`` if the write succeeded.
    """
    try:
        dest = Path(path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        success = cv2.imwrite(
            str(dest),
            image,
            [cv2.IMWRITE_JPEG_QUALITY, quality],
        )
        if success:
            logger.info(
                "Snapshot saved",
                extra={"path": str(dest), "quality": quality},
            )
        else:
            logger.error(
                "cv2.imwrite returned False",
                extra={"path": str(dest)},
            )
        return success
    except Exception:
        logger.exception("Failed to save snapshot", extra={"path": path})
        return False


def generate_thumbnail(
    image: np.ndarray,
    max_dim: int = 128,
) -> np.ndarray:
    """
    Generate a thumbnail that fits within a ``max_dim x max_dim`` box,
    preserving aspect ratio.

    Parameters
    ----------
    image : np.ndarray
        Source BGR image.
    max_dim : int
        Maximum width or height of the thumbnail.

    Returns
    -------
    np.ndarray
        Resized thumbnail image.
    """
    if image is None or image.size == 0:
        logger.warning("generate_thumbnail received empty image")
        return np.zeros((max_dim, max_dim, 3), dtype=np.uint8)

    src_h, src_w = image.shape[:2]
    scale = max_dim / max(src_h, src_w)

    if scale >= 1.0:
        # Image is already smaller than max_dim; return a copy
        return image.copy()

    new_w = max(1, int(round(src_w * scale)))
    new_h = max(1, int(round(src_h * scale)))
    thumbnail = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_AREA)

    logger.debug(
        "Thumbnail generated",
        extra={
            "src": f"{src_w}x{src_h}",
            "thumb": f"{new_w}x{new_h}",
            "max_dim": max_dim,
        },
    )
    return thumbnail
