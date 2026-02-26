from pydantic import BaseModel


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


class ScanSessionSummary(BaseModel):
    total_sessions: int = 0
    total_detections: int = 0
    total_plates: int = 0
    total_alerts: int = 0
