# SEEN IT FIRST — Edge Service Dockerfile (Development Only)
# Production deployment uses systemd (see deployment/systemd/)
FROM nvcr.io/nvidia/l4t-tensorrt:r36.4.0-py3

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-pip \
    python3-opencv \
    libgstreamer1.0-0 \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad \
    gstreamer1.0-plugins-ugly \
    gstreamer1.0-tools \
    libgstrtspserver-1.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY edge/requirements.txt /app/edge/requirements.txt
RUN pip3 install --no-cache-dir -r /app/edge/requirements.txt

# Application code
COPY edge/ /app/edge/

# Create data directories
RUN mkdir -p /data/captures /data/clips /data/logs

ENV SIF_CONFIG_DIR=/app/edge/config
ENV SIF_DATA_DIR=/data
ENV SIF_LOG_LEVEL=INFO
ENV PYTHONPATH=/app

EXPOSE 8000

CMD ["python3", "-m", "edge.main"]
