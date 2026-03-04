"""
SEEN IT FIRST - GPU Thermal Monitor for Jetson Orin Nano Super

Continuously monitors GPU temperature and exposes the current thermal
state in a thread-safe manner.  Other modules query the monitor to
decide whether to drop frames or throttle inference.

Primary temp source : /sys/devices/gpu.0/temp  (Jetson thermal zone)
Fallback            : nvidia-smi  (for development on desktop GPUs)
Last resort         : returns -1.0 (unknown)

Usage:
    from edge.utils.thermal import ThermalMonitor, ThermalState

    monitor = ThermalMonitor(settings.system.thermal)
    monitor.start()

    state  = monitor.get_thermal_state()
    skip   = monitor.get_throttle_skip_rate()
    temp_c = monitor.get_gpu_temperature()

    monitor.stop()
"""

from __future__ import annotations

import enum
import os
import re
import subprocess
import threading
import time
from pathlib import Path
from typing import Optional

from edge.utils.logging import get_logger

logger = get_logger("utils.thermal")

# ---------------------------------------------------------------------------
# Jetson sysfs paths for thermal zones.  We try multiple locations because
# the exact path varies across JetPack versions.
# ---------------------------------------------------------------------------
_JETSON_THERMAL_PATHS = [
    Path("/sys/devices/gpu.0/temp"),
    Path("/sys/devices/virtual/thermal/thermal_zone1/temp"),
    Path("/sys/devices/virtual/thermal/thermal_zone2/temp"),
]


# ---------------------------------------------------------------------------
# Thermal state enum
# ---------------------------------------------------------------------------

class ThermalState(enum.Enum):
    """GPU thermal states ordered by severity."""
    NORMAL = "normal"
    WARNING = "warning"
    HIGH = "high"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


# Mapping from ThermalState -> frames to skip between inference runs.
_THROTTLE_SKIP_MAP = {
    ThermalState.NORMAL: 2,
    ThermalState.WARNING: 3,
    ThermalState.HIGH: 4,
    ThermalState.CRITICAL: 6,
    ThermalState.EMERGENCY: 6,  # same as CRITICAL; pipeline should be paused
}


# ---------------------------------------------------------------------------
# Temperature reading helpers (module-level, stateless)
# ---------------------------------------------------------------------------

def _read_jetson_sysfs() -> Optional[float]:
    """
    Try to read the GPU temperature from Jetson sysfs thermal zones.

    The sysfs file contains the temperature in millidegrees Celsius
    (e.g. ``75000`` means 75.0 C).

    Returns None if no readable sysfs path is found.
    """
    for path in _JETSON_THERMAL_PATHS:
        try:
            raw = path.read_text().strip()
            value = int(raw)
            # Jetson sysfs reports millidegrees; convert
            if value > 1000:
                return value / 1000.0
            return float(value)
        except (FileNotFoundError, PermissionError, ValueError):
            continue
    return None


def _read_nvidia_smi() -> Optional[float]:
    """
    Fallback: read GPU temperature via ``nvidia-smi``.

    Returns None if nvidia-smi is unavailable or fails.
    """
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=temperature.gpu", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            temp_str = result.stdout.strip().split("\n")[0].strip()
            return float(temp_str)
    except (FileNotFoundError, subprocess.TimeoutExpired, ValueError, IndexError):
        pass
    return None


def read_gpu_temperature() -> float:
    """
    Read the current GPU temperature in degrees Celsius.

    Attempts Jetson sysfs first, then falls back to nvidia-smi.
    Returns ``-1.0`` if the temperature cannot be determined.
    """
    temp = _read_jetson_sysfs()
    if temp is not None:
        return temp

    temp = _read_nvidia_smi()
    if temp is not None:
        return temp

    logger.warning("Unable to read GPU temperature from any source")
    return -1.0


# ---------------------------------------------------------------------------
# ThermalMonitor
# ---------------------------------------------------------------------------

class ThermalMonitor:
    """
    Background-thread GPU thermal monitor.

    Parameters
    ----------
    thresholds : object
        An object (typically ``ThermalConfig`` from settings) exposing:
          - ``thresholds.warning``  (int, Celsius)
          - ``thresholds.high``    (int, Celsius)
          - ``thresholds.critical``(int, Celsius)
          - ``thresholds.emergency``(int, Celsius)
          - ``recovery_hysteresis``(int, degrees below threshold to recover)
          - ``check_interval_sec`` (int, seconds between polls)
    """

    def __init__(self, thermal_config) -> None:  # noqa: ANN001 -- avoids circular import
        self._warning: int = int(thermal_config.thresholds.warning)
        self._high: int = int(thermal_config.thresholds.high)
        self._critical: int = int(thermal_config.thresholds.critical)
        self._emergency: int = int(thermal_config.thresholds.emergency)
        self._hysteresis: int = int(thermal_config.recovery_hysteresis)
        self._interval: int = int(thermal_config.check_interval_sec)

        # Thread-safe state
        self._lock = threading.Lock()
        self._state: ThermalState = ThermalState.NORMAL
        self._temperature: float = -1.0
        self._running = False

        self._thread: Optional[threading.Thread] = None

        logger.info(
            "ThermalMonitor created",
            extra={
                "warning": self._warning,
                "high": self._high,
                "critical": self._critical,
                "emergency": self._emergency,
                "hysteresis": self._hysteresis,
                "interval_sec": self._interval,
            },
        )

    # ---- public API -------------------------------------------------------

    def start(self) -> None:
        """Start the background monitoring thread."""
        if self._running:
            logger.warning("ThermalMonitor is already running")
            return

        self._running = True
        self._thread = threading.Thread(
            target=self._monitor_loop,
            name="sif-thermal-monitor",
            daemon=True,
        )
        self._thread.start()
        logger.info("ThermalMonitor started")

    def stop(self) -> None:
        """Signal the background thread to stop and wait for it to finish."""
        if not self._running:
            return
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=self._interval + 2)
            self._thread = None
        logger.info("ThermalMonitor stopped")

    def get_gpu_temperature(self) -> float:
        """Return the last-read GPU temperature in Celsius (thread-safe)."""
        with self._lock:
            return self._temperature

    def get_thermal_state(self) -> ThermalState:
        """Return the current thermal state (thread-safe)."""
        with self._lock:
            return self._state

    def get_throttle_skip_rate(self) -> int:
        """
        Return the recommended number of frames to skip based on thermal
        state (thread-safe).

        Mapping:
            NORMAL   -> 2
            WARNING  -> 3
            HIGH     -> 4
            CRITICAL -> 6
            EMERGENCY-> 6
        """
        with self._lock:
            return _THROTTLE_SKIP_MAP.get(self._state, 2)

    # ---- internals --------------------------------------------------------

    def _classify_temperature(self, temp_c: float) -> ThermalState:
        """
        Determine the thermal state for a given temperature, applying
        hysteresis on the cooling side to prevent rapid state flapping.
        """
        current_state = self._state

        # --- Heating: move UP immediately when threshold is exceeded -------
        if temp_c >= self._emergency:
            return ThermalState.EMERGENCY
        if temp_c >= self._critical:
            return ThermalState.CRITICAL
        if temp_c >= self._high:
            return ThermalState.HIGH
        if temp_c >= self._warning:
            return ThermalState.WARNING

        # --- Cooling: require hysteresis below the threshold to step DOWN --
        if current_state == ThermalState.EMERGENCY:
            if temp_c < self._emergency - self._hysteresis:
                return ThermalState.CRITICAL
            return ThermalState.EMERGENCY

        if current_state == ThermalState.CRITICAL:
            if temp_c < self._critical - self._hysteresis:
                return ThermalState.HIGH
            return ThermalState.CRITICAL

        if current_state == ThermalState.HIGH:
            if temp_c < self._high - self._hysteresis:
                return ThermalState.WARNING
            return ThermalState.HIGH

        if current_state == ThermalState.WARNING:
            if temp_c < self._warning - self._hysteresis:
                return ThermalState.NORMAL
            return ThermalState.WARNING

        return ThermalState.NORMAL

    def _monitor_loop(self) -> None:
        """Background thread main loop."""
        logger.info("Thermal monitor loop started")
        while self._running:
            try:
                temp_c = read_gpu_temperature()
                new_state = self._classify_temperature(temp_c)

                with self._lock:
                    old_state = self._state
                    self._temperature = temp_c
                    self._state = new_state

                if new_state != old_state:
                    log_fn = logger.info
                    if new_state in (ThermalState.CRITICAL, ThermalState.EMERGENCY):
                        log_fn = logger.error
                    elif new_state == ThermalState.HIGH:
                        log_fn = logger.warning

                    log_fn(
                        "Thermal state transition",
                        extra={
                            "from": old_state.value,
                            "to": new_state.value,
                            "temperature_c": round(temp_c, 1),
                            "skip_rate": _THROTTLE_SKIP_MAP.get(new_state, 2),
                        },
                    )

                logger.debug(
                    "Thermal check",
                    extra={
                        "temperature_c": round(temp_c, 1),
                        "state": new_state.value,
                    },
                )

            except Exception:
                logger.exception("Error in thermal monitor loop")

            # Sleep in small increments so stop() is responsive
            deadline = time.monotonic() + self._interval
            while self._running and time.monotonic() < deadline:
                time.sleep(0.5)

        logger.info("Thermal monitor loop exited")
