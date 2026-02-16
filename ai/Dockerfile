# For Jetson Orin Nano Super - use NVIDIA L4T base image
# For development without Jetson, use standard PyTorch image
FROM nvcr.io/nvidia/l4t-pytorch:r36.2.0-pth2.1-py3

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    libopencv-dev \
    python3-opencv \
    && rm -rf /var/lib/apt/lists/*

# Python deps
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# App code
COPY . .

# Create model and data directories
RUN mkdir -p /app/models /data/captures

CMD ["python3", "-m", "ai.pipeline"]
