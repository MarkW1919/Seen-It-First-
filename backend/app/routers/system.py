import os
import platform
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.middleware.auth import get_current_user, require_admin
from app.models.user import User

router = APIRouter(prefix="/api/system", tags=["system"])


class SystemInfo(BaseModel):
    version: str = "1.0.0"
    hostname: str = ""
    platform: str = ""
    uptime_seconds: float = 0
    timestamp: str = ""


class SystemStats(BaseModel):
    cpu_percent: float = 0.0
    memory_used_mb: float = 0.0
    memory_total_mb: float = 0.0
    disk_used_gb: float = 0.0
    disk_total_gb: float = 0.0
    gpu_temp_c: float | None = None
    gpu_utilization: float | None = None


@router.get("/info", response_model=SystemInfo)
async def get_system_info(_user: User = Depends(get_current_user)):
    return SystemInfo(
        version="1.0.0",
        hostname=platform.node(),
        platform=platform.platform(),
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@router.get("/stats", response_model=SystemStats)
async def get_system_stats(_user: User = Depends(require_admin)):
    stats = SystemStats()
    try:
        import psutil

        stats.cpu_percent = psutil.cpu_percent(interval=0.1)
        mem = psutil.virtual_memory()
        stats.memory_used_mb = mem.used / (1024 * 1024)
        stats.memory_total_mb = mem.total / (1024 * 1024)
        disk = psutil.disk_usage("/")
        stats.disk_used_gb = disk.used / (1024**3)
        stats.disk_total_gb = disk.total / (1024**3)
    except ImportError:
        pass

    # Jetson GPU temp
    try:
        with open("/sys/devices/virtual/thermal/thermal_zone0/temp") as f:
            stats.gpu_temp_c = int(f.read().strip()) / 1000.0
    except (FileNotFoundError, ValueError):
        pass

    return stats


class ScanSessionSummary(BaseModel):
    total_sessions: int = 0
    total_detections: int = 0
    total_plates: int = 0
    total_alerts: int = 0


@router.get("/sessions", response_model=list)
async def list_scan_sessions(
    _user: User = Depends(get_current_user),
):
    # Placeholder - would query scan_sessions table
    return []
