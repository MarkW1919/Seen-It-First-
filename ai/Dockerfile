# For Jetson Orin Nano Super - NVIDIA L4T base image
# L4T r36.2.0 ships: CUDA 12.2, cuDNN 8.9, TensorRT 8.6, PyTorch 2.1, Python 3.10
FROM nvcr.io/nvidia/l4t-pytorch:r36.2.0-pth2.1-py3

WORKDIR /app

# System deps — use system OpenCV (apt) to avoid conflicts with pip opencv-python-headless
RUN apt-get update && apt-get install -y --no-install-recommends \
    libopencv-dev \
    python3-opencv \
    && rm -rf /var/lib/apt/lists/*

# Python deps (torch/torchvision already in base image; opencv from apt above)
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# App code
COPY . .

# Create model and data directories
RUN mkdir -p /app/models /data/captures

# Verify CUDA/TensorRT alignment at build time
RUN python3 -c "import torch; assert torch.cuda.is_available(), 'CUDA not available'; print(f'CUDA {torch.version.cuda}, cuDNN {torch.backends.cudnn.version()}')"

# Non-root user (needs access to /app/models and /data/captures)
RUN useradd -r -s /usr/sbin/nologin appuser \
    && chown -R appuser:appuser /app /data/captures

USER appuser

CMD ["python3", "-m", "ai.pipeline"]
