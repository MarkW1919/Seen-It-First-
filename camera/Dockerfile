# Jetson L4T base with GStreamer and multimedia support
# L4T r36.2.0 ships: CUDA 12.2, Python 3.10, OpenCV via apt
FROM nvcr.io/nvidia/l4t-pytorch:r36.2.0-pth2.1-py3

WORKDIR /app

# GStreamer, video, and OpenCV via system packages (not pip)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gstreamer1.0-tools \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad \
    libgstreamer1.0-dev \
    libgstrtspserver-1.0-dev \
    gstreamer1.0-rtsp \
    v4l-utils \
    libopencv-dev \
    python3-opencv \
    && rm -rf /var/lib/apt/lists/*

# Python deps (opencv excluded — provided by apt above)
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /data/captures

# Non-root user with video group for /dev/video0 access
RUN useradd -r -s /usr/sbin/nologin -G video appuser \
    && chown -R appuser:appuser /app /data/captures

USER appuser

CMD ["python3", "-m", "camera.controller"]
