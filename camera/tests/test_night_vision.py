"""Tests for camera.night_vision: lux estimation, mode switching."""

from unittest.mock import MagicMock, patch

import cv2
import numpy as np
import pytest

from camera.night_vision import NightVisionController


@pytest.fixture()
def nv_controller():
    """Create NightVisionController with GPIO mocked out."""
    with patch.dict("sys.modules", {"Jetson": MagicMock(), "Jetson.GPIO": MagicMock()}):
        config = {
            "auto_switch": False,  # Don't start monitor thread in tests
            "lux_threshold": 10.0,
            "ir_led_gpio": 18,
            "ir_cut_gpio": 23,
            "transition_delay": 0.1,
        }
        ctrl = NightVisionController(config)
        ctrl._gpio_available = False  # Skip actual GPIO calls
        return ctrl


class TestLuxEstimation:
    def test_bright_frame_high_lux(self, nv_controller):
        # Bright white frame (255 everywhere)
        frame = np.full((480, 640, 3), 255, dtype=np.uint8)
        lux = nv_controller.estimate_lux(frame)
        assert lux > 50  # Should be bright

    def test_dark_frame_low_lux(self, nv_controller):
        # Very dark frame (5 everywhere)
        frame = np.full((480, 640, 3), 5, dtype=np.uint8)
        # Reset EMA to get more accurate reading
        nv_controller._ema_lux = 0.0
        for _ in range(20):  # Run multiple iterations to let EMA converge
            lux = nv_controller.estimate_lux(frame)
        assert lux < 1.0

    def test_none_frame_returns_ema(self, nv_controller):
        nv_controller._ema_lux = 42.0
        assert nv_controller.estimate_lux(None) == 42.0

    def test_grayscale_frame(self, nv_controller):
        frame = np.full((480, 640), 128, dtype=np.uint8)
        lux = nv_controller.estimate_lux(frame)
        assert lux > 0

    def test_ema_smoothing(self, nv_controller):
        nv_controller._ema_lux = 100.0
        dark_frame = np.full((480, 640, 3), 5, dtype=np.uint8)
        lux = nv_controller.estimate_lux(dark_frame)
        # EMA should not jump immediately to 0; should be between 0 and 100
        assert 0 < lux < 100


class TestModeControl:
    def test_enable_night_mode(self, nv_controller):
        nv_controller.enable_night_mode()
        assert nv_controller.is_night_mode
        assert nv_controller.is_ir_enabled

    def test_disable_night_mode(self, nv_controller):
        nv_controller.enable_night_mode()
        nv_controller.disable_night_mode()
        assert not nv_controller.is_night_mode
        assert not nv_controller.is_ir_enabled

    def test_initial_state_day_mode(self, nv_controller):
        assert not nv_controller.is_night_mode
        assert not nv_controller.is_ir_enabled


class TestHysteresis:
    def test_hysteresis_thresholds(self, nv_controller):
        # Hysteresis high should be 2.5x lux_threshold
        assert nv_controller._hysteresis_low == 10.0
        assert nv_controller._hysteresis_high == 25.0
