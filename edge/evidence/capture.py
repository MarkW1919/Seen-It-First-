"""
Snapshot capture for vehicle evidence images.

All three capture methods return the target file path immediately (< 5 ms).
The actual JPEG write is dispatched to a background ThreadPoolExecutor so
the inference pipeline is never blocked on disk I/O.

Directory layout::

    data/evidence/
        vehicles/YYYY/MM/DD/vehicle_{ts}_{camera_id}.jpg
        plates/YYYY/MM/DD/plate_{plate_text}_{ts}.jpg
        composite/YYYY/MM/DD/detect_{ts}.jpg
"""

import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

logger = logging.getLogger(__name__)

_DEFAULT_ROOT = Path("data/evidence")
_JPEG_QUALITY  = [cv2.IMWRITE_JPEG_QUALITY, 85]


class SnapshotCapture:
    """
    Crops and saves JPEG evidence images without blocking the inference thread.

    Usage::

        snap = SnapshotCapture()
        vehicle_path  = snap.capture_vehicle(frame, [x1,y1,x2,y2], "cam1")
        plate_path    = snap.capture_plate(frame, [px1,py1,px2,py2], "ABC123", "cam1")
        composite_path = snap.capture_composite(frame, vehicle_bbox, plate_bbox)
        snap.shutdown()     # at exit — drain pending writes
    """

    def __init__(
        self,
        evidence_root: str | Path | None = None,
        jpeg_quality: int = 85,
        max_workers: int = 2,
    ):
        self._root = Path(evidence_root) if evidence_root else _DEFAULT_ROOT
        self._quality = [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality]
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="evidence-write",
        )

    # ------------------------------------------------------------------
    # Public capture methods (return path, schedule write in background)
    # ------------------------------------------------------------------

    def capture_vehicle(
        self,
        frame: np.ndarray,
        bbox: list[float],
        camera_id: str,
    ) -> str:
        """
        Crop the vehicle region from frame and save to disk.

        Args:
            frame:     Full camera frame (H×W×3 BGR numpy array).
            bbox:      Vehicle bounding box [x1, y1, x2, y2] in pixel coords.
            camera_id: Camera identifier for the filename.

        Returns:
            Absolute path string where the JPEG will be written.
        """
        crop = _safe_crop(frame, bbox)
        path = self._make_path("vehicles", f"vehicle_{_ts()}_{camera_id}.jpg")
        self._executor.submit(_write_jpeg, crop, path, self._quality)
        return str(path)

    def capture_plate(
        self,
        frame: np.ndarray,
        plate_bbox: list[float],
        plate_text: str,
        camera_id: str,
    ) -> str:
        """
        Crop the plate region from frame and save to disk.

        Args:
            frame:      Full camera frame.
            plate_bbox: Plate bounding box [x1, y1, x2, y2] in pixel coords.
            plate_text: Detected plate text (used in filename; sanitised).
            camera_id:  Camera identifier (unused in filename, kept for parity).

        Returns:
            Absolute path string where the JPEG will be written.
        """
        crop = _safe_crop(frame, plate_bbox)
        safe_text = re.sub(r"[^A-Z0-9]", "", plate_text.upper())[:12] or "UNKNOWN"
        path = self._make_path("plates", f"plate_{safe_text}_{_ts()}.jpg")
        self._executor.submit(_write_jpeg, crop, path, self._quality)
        return str(path)

    def capture_composite(
        self,
        frame: np.ndarray,
        vehicle_bbox: list[float],
        plate_bbox: list[float] | None,
    ) -> str:
        """
        Draw bounding boxes on a copy of the frame and save to disk.

        Vehicle box is drawn in blue (BGR 255,0,0).
        Plate box is drawn in green (BGR 0,255,0).

        Args:
            frame:       Full camera frame.
            vehicle_bbox: Vehicle box [x1,y1,x2,y2].
            plate_bbox:   Plate box [x1,y1,x2,y2] or None.

        Returns:
            Absolute path string where the composite JPEG will be written.
        """
        composite = frame.copy()
        vx1, vy1, vx2, vy2 = (int(v) for v in vehicle_bbox[:4])
        cv2.rectangle(composite, (vx1, vy1), (vx2, vy2), (255, 0, 0), 2)  # blue

        if plate_bbox is not None:
            px1, py1, px2, py2 = (int(v) for v in plate_bbox[:4])
            cv2.rectangle(composite, (px1, py1), (px2, py2), (0, 255, 0), 2)  # green

        path = self._make_path("composite", f"detect_{_ts()}.jpg")
        self._executor.submit(_write_jpeg, composite, path, self._quality)
        return str(path)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _make_path(self, category: str, filename: str) -> Path:
        """Build date-partitioned directory and return full file path."""
        today = datetime.now()
        dir_path = self._root / category / today.strftime("%Y/%m/%d")
        dir_path.mkdir(parents=True, exist_ok=True)
        return dir_path / filename

    def shutdown(self, wait: bool = True):
        """Shut down the background write pool."""
        self._executor.shutdown(wait=wait)


# ---------------------------------------------------------------------------
# Module-level helpers (no state, safe to call from any thread)
# ---------------------------------------------------------------------------

def _ts() -> str:
    """Microsecond-precision timestamp string safe for filenames."""
    return f"{time.time():.6f}".replace(".", "_")


def _safe_crop(frame: np.ndarray, bbox: list[float]) -> np.ndarray:
    """Clamp bbox to frame bounds and return a contiguous non-empty crop."""
    h, w = frame.shape[:2]
    x1 = max(0, int(bbox[0]))
    y1 = max(0, int(bbox[1]))
    x2 = min(w, int(bbox[2]))
    y2 = min(h, int(bbox[3]))

    if x2 <= x1 or y2 <= y1:
        # Keep downstream writes stable by returning a 1x1 black pixel.
        return np.zeros((1, 1, 3), dtype=frame.dtype)

    crop = frame[y1:y2, x1:x2]
    return np.ascontiguousarray(crop)  # contiguous copy, safe for background write


def _write_jpeg(image: np.ndarray, path: Path, quality_params: list):
    """Write a JPEG to disk. Runs in a background thread."""
    try:
        ok = cv2.imwrite(str(path), image, quality_params)
        if not ok:
            logger.error("OpenCV returned False while writing evidence image: %s", path)
    except Exception:
        logger.exception("Failed to write evidence image: %s", path)
