"""
System resource monitoring for Jetson Orin Nano.

Tracks GPU utilization, memory usage, and system health.
Logs periodic stats to SQLite.
"""

import logging
import os
import time
from pathlib import Path

logger = logging.getLogger(__name__)


class SystemMonitor:
    """
    Monitors Jetson system resources.

    Reads from:
    - /sys/devices/gpu.0/load (GPU utilization)
    - /proc/meminfo (memory usage)
    - Thermal monitor (temperature)
    """

    def __init__(self):
        self._gpu_load_path = Path("/sys/devices/gpu.0/load")
        self._last_stats: dict = {}

    def get_gpu_utilization(self) -> float:
        """Read GPU utilization percentage (0-100)."""
        try:
            raw = self._gpu_load_path.read_text().strip()
            # Jetson reports GPU load as 0-1000 (permille)
            return int(raw) / 10.0
        except FileNotFoundError:
            return 0.0
        except (ValueError, OSError):
            return 0.0

    def get_memory_info(self) -> tuple[float, float]:
        """Read system memory usage. Returns (used_mb, total_mb)."""
        try:
            with open("/proc/meminfo", "r") as f:
                lines = f.readlines()

            mem_info = {}
            for line in lines:
                parts = line.split()
                if len(parts) >= 2:
                    key = parts[0].rstrip(":")
                    val_kb = int(parts[1])
                    mem_info[key] = val_kb

            total_kb = mem_info.get("MemTotal", 0)
            available_kb = mem_info.get("MemAvailable", 0)
            used_kb = total_kb - available_kb

            return used_kb / 1024.0, total_kb / 1024.0
        except (FileNotFoundError, ValueError, OSError):
            return 0.0, 0.0

    def get_stats(self, gpu_temp: float = 0.0) -> dict:
        """Collect all system stats into a dict."""
        gpu_util = self.get_gpu_utilization()
        mem_used, mem_total = self.get_memory_info()

        stats = {
            "timestamp": time.time(),
            "gpu_temp_c": gpu_temp,
            "gpu_util_pct": gpu_util,
            "mem_used_mb": round(mem_used, 1),
            "mem_total_mb": round(mem_total, 1),
            "mem_used_pct": round(mem_used / mem_total * 100, 1) if mem_total > 0 else 0,
        }
        self._last_stats = stats
        return stats

    @property
    def last_stats(self) -> dict:
        return self._last_stats
