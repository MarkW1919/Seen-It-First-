# Jetson L4T base with GStreamer and multimedia support
FROM nvcr.io/nvidia/l4t-pytorch:r36.2.0-pth2.1-py3

WORKDIR /app

# GStreamer and video deps
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

COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /data/captures

CMD ["python3", "-m", "camera.controller"]
