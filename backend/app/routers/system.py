import platform
from datetime import UTC, datetime

from fastapi import APIRouter, Depends

from app.middleware.auth import get_current_user, require_admin
from app.models.user import User
from app.schemas.system import SystemInfo, SystemStats


@router.get("/info", response_model=SystemInfo)
async def get_system_info(_user: User = Depends(get_current_user)):
    return SystemInfo(
        version="1.0.0",
        hostname=platform.node(),
        platform=platform.platform(),
        timestamp=datetime.now(UTC).isoformat(),
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


@router.get("/sessions", response_model=list)
async def list_scan_sessions(
    _user: User = Depends(get_current_user),
):
    # Placeholder - would query scan_sessions table
    return []
