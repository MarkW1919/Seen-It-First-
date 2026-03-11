"""
Thermal monitoring and adaptive throttling for Jetson Orin Nano.

Reads GPU temperature from sysfs thermal zone.
Implements two-level throttling:
  Level 1: Reduce detection FPS
  Level 2: Further reduce FPS + suspend classifier
"""

import logging
import time
from pathlib import Path

logger = logging.getLogger(__name__)


class ThermalMonitor:
    """
    GPU thermal monitor with adaptive throttling.

    Reads temperature from /sys/devices/virtual/thermal/thermal_zoneX/temp
    (value in millidegrees Celsius on Jetson).

    Throttle levels:
        0: Normal operation (target FPS)
        1: temp > threshold_1 → reduce to cooldown_fps_1
        2: temp > threshold_2 → reduce to cooldown_fps_2 + suspend classifier
    """

    def __init__(self, config: dict):
        self.threshold_1 = float(config.get("threshold_1", 80))
        self.threshold_2 = float(config.get("threshold_2", 90))
        if self.threshold_2 < self.threshold_1:
            logger.warning(
                "thermal config invalid: threshold_2 (%.1f) < threshold_1 (%.1f); normalizing",
                self.threshold_2,
                self.threshold_1,
            )
            self.threshold_2 = self.threshold_1

        self.cooldown_fps_1 = max(1, int(config.get("cooldown_fps_1", 10)))
        self.cooldown_fps_2 = max(1, int(config.get("cooldown_fps_2", 8)))
        if self.cooldown_fps_2 > self.cooldown_fps_1:
            logger.warning(
                "thermal config unexpected: cooldown_fps_2 (%d) > cooldown_fps_1 (%d)",
                self.cooldown_fps_2,
                self.cooldown_fps_1,
            )

        self.poll_interval = max(0.1, float(config.get("poll_interval_sec", 5)))
        self.zone_path = Path(config.get(
            "zone_path",
            "/sys/devices/virtual/thermal/thermal_zone0/temp",
        ))

        self._current_temp: float = 0.0
        self._throttle_level: int = 0
        self._last_poll: float = 0.0

    def read_temperature(self) -> float:
        """Read GPU temperature in Celsius."""
        try:
            raw = self.zone_path.read_text().strip()
            # Jetson reports in millidegrees
            temp_c = int(raw) / 1000.0
            self._current_temp = temp_c
            return temp_c
        except FileNotFoundError:
            logger.debug("Thermal zone not found: %s (not on Jetson?)", self.zone_path)
            return 0.0
        except (ValueError, OSError) as e:
            logger.warning("Failed to read thermal zone: %s", e)
            return self._current_temp

    def check(self) -> tuple[int, float]:
        """
        Check temperature and return (throttle_level, temperature).

        Call this periodically. Returns the current throttle level:
            0 = normal
            1 = moderate throttle
            2 = aggressive throttle
        """
        now = time.monotonic()
        if (now - self._last_poll) < self.poll_interval:
            return self._throttle_level, self._current_temp

        self._last_poll = now
        temp = self.read_temperature()

        prev_level = self._throttle_level

        if temp >= self.threshold_2:
            self._throttle_level = 2
        elif temp >= self.threshold_1:
            self._throttle_level = 1
        else:
            self._throttle_level = 0

        if self._throttle_level != prev_level:
            logger.warning(
                "Thermal throttle level changed: %d → %d (GPU temp: %.1f°C)",
                prev_level, self._throttle_level, temp,
            )

        return self._throttle_level, temp

    def get_target_fps(self, normal_fps: int) -> int:
        """Get the FPS target for current throttle level."""
        base_fps = max(1, int(normal_fps))
        if self._throttle_level == 2:
            return min(base_fps, self.cooldown_fps_2)
        if self._throttle_level == 1:
            return min(base_fps, self.cooldown_fps_1)
        return base_fps

    @property
    def should_suspend_classifier(self) -> bool:
        return self._throttle_level >= 2

    @property
    def throttle_level(self) -> int:
        return self._throttle_level

    @property
    def temperature(self) -> float:
        return self._current_temp
