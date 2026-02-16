"""Image preprocessing pipeline for license plate recognition."""
import cv2
import numpy as np


class ImagePreprocessor:
    """Preprocessing pipeline optimized for LPR in varying conditions."""

    def __init__(self, config: dict):
        cfg = config.get("preprocessing", {})
        self.use_clahe = cfg.get("clahe", True)
        self.clahe_clip = cfg.get("clahe_clip_limit", 2.0)
        self.clahe_grid = tuple(cfg.get("clahe_grid_size", [8, 8]))
        self.use_denoise = cfg.get("denoise", True)
        self.denoise_strength = cfg.get("denoise_strength", 5)
        self.use_sharpen = cfg.get("sharpen", False)

        if self.use_clahe:
            self._clahe = cv2.createCLAHE(
                clipLimit=self.clahe_clip, tileGridSize=self.clahe_grid
            )

    def process(self, frame: np.ndarray) -> np.ndarray:
        """Apply preprocessing pipeline to a frame.

        Args:
            frame: BGR input frame

        Returns:
            Preprocessed BGR frame
        """
        result = frame

        if self.use_clahe:
            result = self._apply_clahe(result)

        if self.use_denoise:
            result = self._denoise(result)

        if self.use_sharpen:
            result = self._sharpen(result)

        return result

    def _apply_clahe(self, frame: np.ndarray) -> np.ndarray:
        """Apply CLAHE contrast enhancement to each channel."""
        lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
        channels = list(cv2.split(lab))
        channels[0] = self._clahe.apply(channels[0])
        lab = cv2.merge(channels)
        return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)

    def _denoise(self, frame: np.ndarray) -> np.ndarray:
        """Apply fast non-local means denoising."""
        return cv2.fastNlMeansDenoisingColored(
            frame,
            None,
            self.denoise_strength,
            self.denoise_strength,
            7,
            21,
        )

    def _sharpen(self, frame: np.ndarray) -> np.ndarray:
        """Apply unsharp mask sharpening."""
        blurred = cv2.GaussianBlur(frame, (0, 0), 3)
        return cv2.addWeighted(frame, 1.5, blurred, -0.5, 0)

    def enhance_plate(self, plate_img: np.ndarray) -> np.ndarray:
        """Enhanced preprocessing specifically for plate images.

        Applies more aggressive enhancement for better OCR results.
        """
        if plate_img.size == 0:
            return plate_img

        # Convert to grayscale
        if len(plate_img.shape) == 3:
            gray = cv2.cvtColor(plate_img, cv2.COLOR_BGR2GRAY)
        else:
            gray = plate_img

        # Upscale if too small
        h, w = gray.shape[:2]
        if w < 200:
            scale = 200 / w
            gray = cv2.resize(
                gray,
                None,
                fx=scale,
                fy=scale,
                interpolation=cv2.INTER_CUBIC,
            )

        # CLAHE on grayscale
        enhanced = self._clahe.apply(gray)

        # Bilateral filter (edge-preserving denoise)
        enhanced = cv2.bilateralFilter(enhanced, 9, 75, 75)

        # Adaptive threshold for better OCR
        # (return both enhanced grayscale and binary for OCR options)
        return enhanced
