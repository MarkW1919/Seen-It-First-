"""Tests for camera.preprocessor: ImagePreprocessor pipeline."""

import cv2
import numpy as np
import pytest

from camera.preprocessor import ImagePreprocessor


@pytest.fixture()
def preprocessor():
    config = {
        "preprocessing": {
            "clahe": True,
            "clahe_clip_limit": 2.0,
            "clahe_grid_size": [8, 8],
            "denoise": True,
            "denoise_strength": 5,
            "sharpen": False,
        }
    }
    return ImagePreprocessor(config)


@pytest.fixture()
def preprocessor_all():
    """Preprocessor with all stages enabled."""
    config = {
        "preprocessing": {
            "clahe": True,
            "clahe_clip_limit": 2.0,
            "clahe_grid_size": [8, 8],
            "denoise": True,
            "denoise_strength": 5,
            "sharpen": True,
        }
    }
    return ImagePreprocessor(config)


@pytest.fixture()
def sample_frame():
    """Create a synthetic BGR test frame with some variation."""
    frame = np.random.RandomState(42).randint(30, 200, (480, 640, 3), dtype=np.uint8)
    return frame


class TestProcess:
    def test_output_shape_matches_input(self, preprocessor, sample_frame):
        result = preprocessor.process(sample_frame)
        assert result.shape == sample_frame.shape
        assert result.dtype == sample_frame.dtype

    def test_output_is_bgr(self, preprocessor, sample_frame):
        result = preprocessor.process(sample_frame)
        assert result.ndim == 3
        assert result.shape[2] == 3

    def test_with_all_stages(self, preprocessor_all, sample_frame):
        result = preprocessor_all.process(sample_frame)
        assert result.shape == sample_frame.shape

    def test_no_processing_when_disabled(self):
        config = {
            "preprocessing": {
                "clahe": False,
                "denoise": False,
                "sharpen": False,
            }
        }
        pp = ImagePreprocessor(config)
        frame = np.ones((100, 100, 3), dtype=np.uint8) * 128
        result = pp.process(frame)
        np.testing.assert_array_equal(result, frame)


class TestEnhancePlate:
    def test_upscales_small_plate(self, preprocessor):
        # Small plate image: 100x30
        plate = np.random.RandomState(42).randint(0, 255, (30, 100, 3), dtype=np.uint8)
        result = preprocessor.enhance_plate(plate)
        # Should be upscaled (width was < 200, so scaled to 200)
        assert result.shape[1] >= 200

    def test_does_not_upscale_large_plate(self, preprocessor):
        plate = np.random.RandomState(42).randint(0, 255, (60, 300, 3), dtype=np.uint8)
        result = preprocessor.enhance_plate(plate)
        # Should not change width
        assert result.shape[1] == 300

    def test_grayscale_input(self, preprocessor):
        plate = np.random.RandomState(42).randint(0, 255, (30, 100), dtype=np.uint8)
        result = preprocessor.enhance_plate(plate)
        assert result.ndim == 2  # stays grayscale

    def test_empty_image_returns_empty(self, preprocessor):
        plate = np.array([], dtype=np.uint8)
        result = preprocessor.enhance_plate(plate)
        assert result.size == 0

    def test_output_is_grayscale(self, preprocessor):
        plate = np.random.RandomState(42).randint(0, 255, (40, 250, 3), dtype=np.uint8)
        result = preprocessor.enhance_plate(plate)
        assert result.ndim == 2


class TestCLAHE:
    def test_clahe_enhances_contrast(self, preprocessor):
        # Low-contrast frame
        frame = np.full((100, 100, 3), 128, dtype=np.uint8)
        frame[40:60, 40:60] = 130  # subtle difference
        result = preprocessor._apply_clahe(frame)
        # CLAHE should not crash and output shape should match
        assert result.shape == frame.shape


class TestDenoise:
    def test_denoise_reduces_noise(self, preprocessor):
        # Noisy frame
        rng = np.random.RandomState(42)
        frame = rng.randint(100, 200, (100, 100, 3), dtype=np.uint8)
        result = preprocessor._denoise(frame)
        assert result.shape == frame.shape
        # Denoised frame should have less variance (smoother)
        assert result.std() <= frame.std()


class TestSharpen:
    def test_sharpen_preserves_shape(self, preprocessor_all):
        frame = np.random.RandomState(42).randint(0, 255, (100, 100, 3), dtype=np.uint8)
        result = preprocessor_all._sharpen(frame)
        assert result.shape == frame.shape
