"""
SEEN IT FIRST - Edge Camera Subsystem
Jetson Orin Nano Super :: 4-camera rig (2x IMX462 LPR + 2x IMX327 classifier)
"""

from edge.camera.capture import CameraCapture, Frame, SourceType
from edge.camera.health import CameraHealthMonitor, CameraHealth, CameraStatus
from edge.camera.manager import CameraManager

__all__ = [
    "CameraCapture",
    "CameraManager",
    "CameraHealth",
    "CameraHealthMonitor",
    "CameraStatus",
    "Frame",
    "SourceType",
]
