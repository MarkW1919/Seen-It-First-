"""
GStreamer pipeline string builder for Jetson CSI and RTSP cameras.

All pipelines route through NVMM memory for hardware-accelerated
decode and zero-copy conversion on the Jetson Orin Nano Super.
"""


def build_csi_pipeline(
    sensor_id: int,
    width: int = 1920,
    height: int = 1080,
    fps: int = 30,
) -> str:
    """
    Build a GStreamer pipeline string for a CSI camera via nvarguscamerasrc.

    The pipeline stays in NVMM (GPU) memory through decode and conversion,
    exiting to system RAM only at the appsink boundary.

    Args:
        sensor_id: CSI sensor port (0–3 on Jetson Orin Nano Super).
        width:     Capture width in pixels.
        height:    Capture height in pixels.
        fps:       Target frame rate.

    Returns:
        GStreamer pipeline string suitable for cv2.VideoCapture(..., cv2.CAP_GSTREAMER).
    """
    return (
        f"nvarguscamerasrc sensor-id={sensor_id} ! "
        f"video/x-raw(memory:NVMM),width={width},height={height},"
        f"framerate={fps}/1 ! "
        f"nvvidconv ! "
        f"video/x-raw,format=BGRx ! "
        f"videoconvert ! "
        f"video/x-raw,format=BGR ! "
        f"appsink drop=true max-buffers=1 sync=false"
    )


def build_rtsp_pipeline(uri: str) -> str:
    """
    Build a GStreamer pipeline string for an RTSP H.264 stream via NVDEC.

    Args:
        uri: Full RTSP URI (e.g. rtsp://192.168.1.100:554/stream1).

    Returns:
        GStreamer pipeline string.
    """
    return (
        f"rtspsrc location={uri} latency=100 ! "
        f"rtph264depay ! h264parse ! nvv4l2decoder ! "
        f"nvvidconv ! "
        f"video/x-raw,format=BGRx ! "
        f"videoconvert ! "
        f"video/x-raw,format=BGR ! "
        f"appsink drop=true max-buffers=1 sync=false"
    )
