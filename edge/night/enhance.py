"""
SEEN IT FIRST - Edge AI Vehicle LPR System
ROI-only night-time image enhancement for the Jetson Orin Nano Super.

All enhancement is performed exclusively on cropped ROIs (plate or vehicle)
to minimise compute overhead.  Full-frame processing is deliberately avoided.

Techniques used:
  * CLAHE on the L channel (LAB colour space) for contrast enhancement
  * Gamma correction for underexposed plate ROIs
"""

from __future__ import annotations

import numpy as np

from edge.utils.logging import get_logger

logger = get_logger("night.enhance")

# ---------------------------------------------------------------------------
# OpenCV import
# ---------------------------------------------------------------------------
try:
    import cv2
except ImportError:
    cv2 = None  # type: ignore[assignment]
    logger.error(
        "OpenCV (cv2) is not installed -- night enhancement functions will "
        "return unmodified images"
    )


# ---------------------------------------------------------------------------
# Plate ROI enhancement
# ---------------------------------------------------------------------------

def enhance_plate_roi(plate_image: np.ndarray) -> np.ndarray:
    """Enhance a cropped license-plate ROI for improved OCR in low light.

    Processing pipeline (ROI only -- never applied full-frame):
      1. Convert BGR -> LAB colour space.
      2. Apply CLAHE (clipLimit=3.0, tileGridSize=(4, 4)) to the L channel.
      3. Apply gamma correction (gamma=0.6) to brighten underexposed plates.
      4. Convert LAB -> BGR.

    Parameters
    ----------
    plate_image :
        Cropped BGR image of the license plate region.

    Returns
    -------
    np.ndarray
        Enhanced BGR plate image.  If OpenCV is unavailable or the input
        is invalid, the original image is returned unmodified.
    """
    if cv2 is None:
        return plate_image

    if plate_image is None or plate_image.size == 0:
        logger.debug("enhance_plate_roi called with empty image -- skipping")
        return plate_image

    try:
        # 1. BGR -> LAB
        lab = cv2.cvtColor(plate_image, cv2.COLOR_BGR2LAB)
        l_channel, a_channel, b_channel = cv2.split(lab)

        # 2. CLAHE on L channel
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(4, 4))
        l_enhanced = clahe.apply(l_channel)

        # 3. Gamma correction (gamma < 1 brightens the image)
        l_gamma = _apply_gamma(l_enhanced, gamma=0.6)

        # 4. Merge and convert back to BGR
        lab_enhanced = cv2.merge([l_gamma, a_channel, b_channel])
        result = cv2.cvtColor(lab_enhanced, cv2.COLOR_LAB2BGR)

        logger.debug(
            "Plate ROI enhanced | shape=%s  clahe_clip=3.0  gamma=0.6",
            plate_image.shape,
        )
        return result

    except Exception:
        logger.exception("Failed to enhance plate ROI -- returning original")
        return plate_image


# ---------------------------------------------------------------------------
# Vehicle ROI enhancement
# ---------------------------------------------------------------------------

def enhance_vehicle_roi(vehicle_image: np.ndarray) -> np.ndarray:
    """Lightly enhance a cropped vehicle ROI for better colour/feature visibility.

    Uses a gentler CLAHE configuration than the plate enhancement to
    preserve accurate colour for downstream vehicle classification.  No
    gamma correction is applied so that colour accuracy is maintained.

    Processing pipeline (ROI only -- never applied full-frame):
      1. Convert BGR -> LAB colour space.
      2. Apply CLAHE (clipLimit=2.0, tileGridSize=(8, 8)) to the L channel.
      3. Convert LAB -> BGR.

    Parameters
    ----------
    vehicle_image :
        Cropped BGR image of the vehicle region.

    Returns
    -------
    np.ndarray
        Enhanced BGR vehicle image.  If OpenCV is unavailable or the input
        is invalid, the original image is returned unmodified.
    """
    if cv2 is None:
        return vehicle_image

    if vehicle_image is None or vehicle_image.size == 0:
        logger.debug("enhance_vehicle_roi called with empty image -- skipping")
        return vehicle_image

    try:
        # 1. BGR -> LAB
        lab = cv2.cvtColor(vehicle_image, cv2.COLOR_BGR2LAB)
        l_channel, a_channel, b_channel = cv2.split(lab)

        # 2. Lighter CLAHE on L channel (preserves colour information)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        l_enhanced = clahe.apply(l_channel)

        # 3. Merge and convert back to BGR -- NO gamma correction
        lab_enhanced = cv2.merge([l_enhanced, a_channel, b_channel])
        result = cv2.cvtColor(lab_enhanced, cv2.COLOR_LAB2BGR)

        logger.debug(
            "Vehicle ROI enhanced | shape=%s  clahe_clip=2.0  no_gamma",
            vehicle_image.shape,
        )
        return result

    except Exception:
        logger.exception("Failed to enhance vehicle ROI -- returning original")
        return vehicle_image


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _apply_gamma(image: np.ndarray, gamma: float = 0.6) -> np.ndarray:
    """Apply gamma correction to a single-channel uint8 image.

    Parameters
    ----------
    image :
        Single-channel uint8 image (e.g. L channel from LAB).
    gamma :
        Gamma value.  Values < 1 brighten; values > 1 darken.

    Returns
    -------
    np.ndarray
        Gamma-corrected uint8 image.
    """
    # Build a lookup table for speed (avoids per-pixel floating-point math)
    inv_gamma = 1.0 / gamma
    table = np.array(
        [(i / 255.0) ** inv_gamma * 255.0 for i in range(256)],
        dtype=np.uint8,
    )

    if cv2 is not None:
        return cv2.LUT(image, table)

    # Pure NumPy fallback (slower but functional)
    return table[image]
