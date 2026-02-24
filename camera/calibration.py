"""Camera calibration and lens distortion correction."""

import json
import logging
from pathlib import Path

import cv2
import numpy as np

logger = logging.getLogger(__name__)


class CameraCalibration:
    """Handles camera calibration for distortion correction."""

    def __init__(self, calibration_file: str | None = None):
        self.camera_matrix: np.ndarray | None = None
        self.dist_coeffs: np.ndarray | None = None
        self._map1: np.ndarray | None = None
        self._map2: np.ndarray | None = None
        self._calibrated = False

        if calibration_file and Path(calibration_file).exists():
            self.load(calibration_file)

    @property
    def is_calibrated(self) -> bool:
        return self._calibrated

    def calibrate_from_checkerboard(
        self,
        images: list[np.ndarray],
        board_size: tuple[int, int] = (9, 6),
        square_size: float = 25.0,
    ) -> bool:
        """Calibrate camera from checkerboard images.

        Args:
            images: List of BGR images containing checkerboard
            board_size: Number of inner corners (cols, rows)
            square_size: Size of each square in mm

        Returns:
            True if calibration succeeded
        """
        obj_points = []
        img_points = []

        objp = np.zeros((board_size[0] * board_size[1], 3), np.float32)
        objp[:, :2] = np.mgrid[0 : board_size[0], 0 : board_size[1]].T.reshape(-1, 2)
        objp *= square_size

        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)

        for img in images:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            ret, corners = cv2.findChessboardCorners(gray, board_size, None)

            if ret:
                corners_refined = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)
                obj_points.append(objp)
                img_points.append(corners_refined)

        if len(obj_points) < 3:
            logger.error("Need at least 3 valid checkerboard images")
            return False

        h, w = images[0].shape[:2]
        ret, mtx, dist, _rvecs, _tvecs = cv2.calibrateCamera(
            obj_points, img_points, (w, h), None, None
        )

        if ret:
            self.camera_matrix = mtx
            self.dist_coeffs = dist
            self._compute_maps(w, h)
            self._calibrated = True
            logger.info(f"Calibration successful, reprojection error: {ret:.4f}")
            return True

        return False

    def _compute_maps(self, width: int, height: int):
        """Precompute undistortion maps for fast correction."""
        new_mtx, _ = cv2.getOptimalNewCameraMatrix(
            self.camera_matrix, self.dist_coeffs, (width, height), 1, (width, height)
        )
        self._map1, self._map2 = cv2.initUndistortRectifyMap(
            self.camera_matrix, self.dist_coeffs, None, new_mtx, (width, height), cv2.CV_16SC2
        )

    def undistort(self, frame: np.ndarray) -> np.ndarray:
        """Apply distortion correction to a frame."""
        if not self._calibrated or self._map1 is None:
            return frame
        return cv2.remap(frame, self._map1, self._map2, cv2.INTER_LINEAR)

    def save(self, filepath: str):
        """Save calibration data to file."""
        data = {
            "camera_matrix": self.camera_matrix.tolist(),
            "dist_coeffs": self.dist_coeffs.tolist(),
        }
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)
        logger.info(f"Calibration saved to {filepath}")

    def load(self, filepath: str):
        """Load calibration data from file."""
        try:
            with open(filepath) as f:
                data = json.load(f)
            self.camera_matrix = np.array(data["camera_matrix"])
            self.dist_coeffs = np.array(data["dist_coeffs"])
            self._calibrated = True
            logger.info(f"Calibration loaded from {filepath}")
        except Exception as e:
            logger.error(f"Failed to load calibration: {e}")
