"""Tests for camera.ptz: boundary helpers, PTZController."""

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from camera.ptz import (
    TILT_MAX,
    TILT_MIN,
    ZOOM_MAX,
    ZOOM_MIN,
    MotionState,
    PTZController,
    clamp_speed,
    clamp_tilt,
    clamp_zoom,
    normalize_pan,
)


class TestNormalizePan:
    def test_in_range(self):
        assert normalize_pan(90.0) == 90.0

    def test_wraps_above_180(self):
        assert normalize_pan(190.0) == -170.0

    def test_wraps_below_minus_180(self):
        assert normalize_pan(-200.0) == 160.0

    def test_boundary_180(self):
        assert normalize_pan(180.0) == 180.0

    def test_boundary_minus_180(self):
        assert normalize_pan(-180.0) == -180.0

    def test_zero(self):
        assert normalize_pan(0.0) == 0.0

    def test_full_circle(self):
        assert normalize_pan(360.0) == 0.0

    def test_large_positive(self):
        result = normalize_pan(540.0)
        assert -180.0 <= result <= 180.0
        assert result == 180.0

    def test_large_negative(self):
        result = normalize_pan(-540.0)
        assert -180.0 <= result <= 180.0


class TestClampTilt:
    def test_in_range(self):
        assert clamp_tilt(30.0) == 30.0

    def test_clamps_above_max(self):
        assert clamp_tilt(80.0) == TILT_MAX

    def test_clamps_below_min(self):
        assert clamp_tilt(-80.0) == TILT_MIN

    def test_boundary_max(self):
        assert clamp_tilt(70.0) == 70.0

    def test_boundary_min(self):
        assert clamp_tilt(-70.0) == -70.0

    def test_zero(self):
        assert clamp_tilt(0.0) == 0.0


class TestClampZoom:
    def test_in_range(self):
        assert clamp_zoom(15.0) == 15.0

    def test_clamps_below_min(self):
        assert clamp_zoom(0.5) == ZOOM_MIN

    def test_clamps_above_max(self):
        assert clamp_zoom(50.0) == ZOOM_MAX

    def test_boundary_min(self):
        assert clamp_zoom(1.0) == 1.0

    def test_boundary_max(self):
        assert clamp_zoom(30.0) == 30.0


class TestClampSpeed:
    def test_in_range(self):
        assert clamp_speed(32) == 32

    def test_clamps_below_min(self):
        assert clamp_speed(0) == 1

    def test_clamps_above_max(self):
        assert clamp_speed(100) == 63

    def test_boundary_min(self):
        assert clamp_speed(1) == 1

    def test_boundary_max(self):
        assert clamp_speed(63) == 63


class TestPTZController:
    def make_controller(self, enabled=False, **kwargs):
        config = {"enabled": enabled, "serial_port": "/dev/ttyUSB0", "baud_rate": 9600, "address": 1}
        config.update(kwargs)
        return PTZController(config)

    def test_initial_position(self):
        ctrl = self.make_controller()
        pos = ctrl.position
        assert pos == {"pan": 0.0, "tilt": 0.0, "zoom": 1.0}

    def test_initial_state_idle(self):
        ctrl = self.make_controller()
        assert ctrl.motion_state == MotionState.IDLE
        assert not ctrl.is_moving

    def test_not_connected_when_disabled(self):
        ctrl = self.make_controller(enabled=False)
        assert not ctrl.is_connected

    @patch("camera.ptz.serial", create=True)
    def test_send_command_without_serial_fails_gracefully(self, mock_serial):
        ctrl = self.make_controller(enabled=False)
        result = ctrl._send_command(0x00, 0x02, 32, 0)
        assert result is False

    @pytest.mark.asyncio
    async def test_pan_updates_position(self):
        ctrl = self.make_controller()
        ctrl._serial = MagicMock()
        ctrl._serial.write = MagicMock()
        pos = await ctrl.pan(45.0)
        assert pos["pan"] == 45.0

    @pytest.mark.asyncio
    async def test_tilt_clamps_to_range(self):
        ctrl = self.make_controller()
        ctrl._serial = MagicMock()
        ctrl._serial.write = MagicMock()
        pos = await ctrl.tilt(90.0)  # Should clamp to 70
        assert pos["tilt"] == TILT_MAX

    @pytest.mark.asyncio
    async def test_zoom_clamps_to_range(self):
        ctrl = self.make_controller()
        ctrl._serial = MagicMock()
        ctrl._serial.write = MagicMock()
        pos = await ctrl.zoom(50.0)  # Should clamp to 30
        assert pos["zoom"] == ZOOM_MAX

    @pytest.mark.asyncio
    async def test_home_returns_to_origin(self):
        ctrl = self.make_controller()
        ctrl._serial = MagicMock()
        ctrl._serial.write = MagicMock()
        # Move away first
        await ctrl.pan(45.0)
        await ctrl.tilt(20.0)
        # Return home
        pos = await ctrl.home()
        assert pos["pan"] == 0.0
        assert pos["tilt"] == 0.0
        assert pos["zoom"] == 1.0

    @pytest.mark.asyncio
    async def test_stop_sets_idle(self):
        ctrl = self.make_controller()
        ctrl._serial = MagicMock()
        ctrl._serial.write = MagicMock()
        await ctrl.stop()
        assert ctrl.motion_state == MotionState.IDLE

    def test_close_stops_and_disconnects(self):
        ctrl = self.make_controller()
        mock_serial = MagicMock()
        ctrl._serial = mock_serial
        ctrl.close()
        assert ctrl._serial is None
        assert ctrl.motion_state == MotionState.IDLE
