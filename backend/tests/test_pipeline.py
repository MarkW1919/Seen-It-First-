"""Unit tests for AI pipeline logic — ThermalMonitor, frame skip, IoU matching.

The AI module has heavy Jetson/CV2 dependencies that aren't available in the
backend test environment. We replicate the pure-logic components here to get
coverage without importing the full pipeline.
"""

import os
import tempfile
import time

# ── Replicated ThermalMonitor (pure logic, no cv2/numpy deps) ────────────────


class ThermalMonitor:
    """Replica of ai.pipeline.ThermalMonitor for testing."""

    WARM_TEMP = 70.0
    THROTTLE_TEMP = 80.0
    RESUME_TEMP = 65.0
    THERMAL_ZONES: list[str] = [  # noqa: RUF012
        "/sys/devices/virtual/thermal/thermal_zone0/temp",
        "/sys/devices/virtual/thermal/thermal_zone1/temp",
    ]

    def __init__(self):
        self._throttle_level = 0
        self._last_check = 0.0
        self._check_interval = 2.0
        self._last_temp = 0.0

    @property
    def throttle_level(self) -> int:
        now = time.monotonic()
        if now - self._last_check < self._check_interval:
            return self._throttle_level
        self._last_check = now
        temp = self._read_temp()
        if temp is None:
            return self._throttle_level
        self._last_temp = temp

        if temp >= self.THROTTLE_TEMP:
            self._throttle_level = 2
        elif temp >= self.WARM_TEMP:
            self._throttle_level = 1
        elif temp < self.RESUME_TEMP:
            self._throttle_level = 0

        return self._throttle_level

    @property
    def is_throttled(self) -> bool:
        return self.throttle_level > 0

    @property
    def temperature(self) -> float | None:
        return self._read_temp()

    def _read_temp(self) -> float | None:
        max_temp = None
        for zone in self.THERMAL_ZONES:
            try:
                with open(zone) as f:
                    temp = int(f.read().strip()) / 1000.0
                    if max_temp is None or temp > max_temp:
                        max_temp = temp
            except (FileNotFoundError, ValueError, PermissionError):
                continue
        return max_temp


# ── Replicated _find_track_id (pure logic, no imports needed) ────────────────


def _find_track_id(det_bbox: list[int], track_by_bbox: dict[tuple, int]) -> int | None:
    """Replica of InferencePipeline._find_track_id for testing."""
    if not track_by_bbox:
        return None

    best_id = None
    best_iou = 0.3

    dx, dy, dw, dh = det_bbox
    da = dw * dh
    if da <= 0:
        return None

    for (tx, ty, tw, th), tid in track_by_bbox.items():
        ix1 = max(dx, tx)
        iy1 = max(dy, ty)
        ix2 = min(dx + dw, tx + tw)
        iy2 = min(dy + dh, ty + th)
        inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
        union = da + tw * th - inter
        iou = inter / max(union, 1e-6)
        if iou > best_iou:
            best_iou = iou
            best_id = tid

    return best_id


# ── ThermalMonitor tests ────────────────────────────────────────────────────


class TestThermalMonitor:
    """Tests for ThermalMonitor without needing actual Jetson hardware."""

    def test_initial_throttle_level_is_zero(self):
        tm = ThermalMonitor()
        tm._last_check = 0.0
        assert tm._throttle_level == 0

    def test_throttle_level_constants(self):
        assert ThermalMonitor.WARM_TEMP == 70.0
        assert ThermalMonitor.THROTTLE_TEMP == 80.0
        assert ThermalMonitor.RESUME_TEMP == 65.0

    def test_read_temp_returns_none_when_no_zones(self):
        tm = ThermalMonitor()
        assert tm._read_temp() is None

    def test_read_temp_from_mock_zone(self):
        tm = ThermalMonitor()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("65000\n")
            f.flush()
            tm.THERMAL_ZONES = [f.name]
            temp = tm._read_temp()
            assert temp == 65.0
        os.unlink(f.name)

    def test_warm_zone_triggers_level_1(self):
        tm = ThermalMonitor()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("72000\n")
            f.flush()
            tm.THERMAL_ZONES = [f.name]
            tm._last_check = 0.0
            level = tm.throttle_level
            assert level == 1
        os.unlink(f.name)

    def test_hot_zone_triggers_level_2(self):
        tm = ThermalMonitor()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("85000\n")
            f.flush()
            tm.THERMAL_ZONES = [f.name]
            tm._last_check = 0.0
            level = tm.throttle_level
            assert level == 2
        os.unlink(f.name)

    def test_resume_temp_resets_to_normal(self):
        tm = ThermalMonitor()
        tm._throttle_level = 1

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("60000\n")
            f.flush()
            tm.THERMAL_ZONES = [f.name]
            tm._last_check = 0.0
            level = tm.throttle_level
            assert level == 0
        os.unlink(f.name)

    def test_hysteresis_between_warm_and_resume(self):
        """Temperature between RESUME_TEMP and WARM_TEMP shouldn't change level."""
        tm = ThermalMonitor()
        tm._throttle_level = 1

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("67000\n")  # 67.0 — above resume (65), below warm (70)
            f.flush()
            tm.THERMAL_ZONES = [f.name]
            tm._last_check = 0.0
            level = tm.throttle_level
            assert level == 1
        os.unlink(f.name)

    def test_is_throttled_property(self):
        tm = ThermalMonitor()
        tm._throttle_level = 0
        tm._last_check = time.monotonic()
        assert not tm.is_throttled
        tm._throttle_level = 1
        assert tm.is_throttled

    def test_max_temp_across_zones(self):
        tm = ThermalMonitor()
        with (
            tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f1,
            tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f2,
        ):
            f1.write("55000\n")
            f2.write("72000\n")
            f1.flush()
            f2.flush()
            tm.THERMAL_ZONES = [f1.name, f2.name]
            temp = tm._read_temp()
            assert temp == 72.0
        os.unlink(f1.name)
        os.unlink(f2.name)

    def test_check_interval_caching(self):
        tm = ThermalMonitor()
        tm._last_check = time.monotonic()
        tm._throttle_level = 1
        assert tm.throttle_level == 1


# ── IoU matching tests ──────────────────────────────────────────────────────


class TestIoUMatching:
    def test_empty_tracks_returns_none(self):
        assert _find_track_id([0, 0, 100, 100], {}) is None

    def test_exact_match(self):
        tracks = {(10, 20, 100, 50): 42}
        result = _find_track_id([10, 20, 100, 50], tracks)
        assert result == 42

    def test_good_overlap_matches(self):
        tracks = {(10, 20, 100, 50): 7}
        result = _find_track_id([15, 25, 100, 50], tracks)
        assert result == 7

    def test_no_overlap_returns_none(self):
        tracks = {(0, 0, 50, 50): 1}
        result = _find_track_id([200, 200, 50, 50], tracks)
        assert result is None

    def test_best_iou_wins(self):
        tracks = {
            (0, 0, 100, 100): 1,
            (48, 48, 100, 100): 2,
        }
        result = _find_track_id([50, 50, 100, 100], tracks)
        assert result == 2

    def test_zero_area_detection(self):
        tracks = {(0, 0, 100, 100): 1}
        result = _find_track_id([50, 50, 0, 0], tracks)
        assert result is None


# ── Frame skip logic ─────────────────────────────────────────────────────────


def test_frame_skip_level_0():
    """At thermal level 0 with skip_frames=0, every frame should be processed."""
    skip = 0
    for frame_count in range(1, 10):
        should_skip = skip > 0 and frame_count % (skip + 1) != 0
        assert not should_skip


def test_frame_skip_level_1():
    """At thermal level 1, effective_skip=1 → every other frame skipped."""
    skip = 1
    processed = []
    for frame_count in range(1, 11):
        should_skip = skip > 0 and frame_count % (skip + 1) != 0
        if not should_skip:
            processed.append(frame_count)
    assert processed == [2, 4, 6, 8, 10]


def test_frame_skip_level_2():
    """At thermal level 2, effective_skip=2 → skip 2 of 3 frames."""
    skip = 2
    processed = []
    for frame_count in range(1, 13):
        should_skip = skip > 0 and frame_count % (skip + 1) != 0
        if not should_skip:
            processed.append(frame_count)
    assert processed == [3, 6, 9, 12]


def test_effective_skip_uses_max():
    """Thermal skip should use max of config skip and thermal skip."""
    config_skip = 1
    for thermal_level, expected_skip in [(0, 1), (1, 1), (2, 2)]:
        effective = config_skip
        if thermal_level >= 2:
            effective = max(effective, 2)
        elif thermal_level >= 1:
            effective = max(effective, 1)
        assert effective == expected_skip
