# SEEN IT FIRST — API Service Dockerfile (Development Only)
# Runs FastAPI API server standalone for dev/test without full edge system
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY edge/requirements.txt /app/edge/requirements.txt
RUN pip install --no-cache-dir -r /app/edge/requirements.txt

COPY edge/ /app/edge/

RUN mkdir -p /data/captures /data/clips /data/logs

ENV SIF_CONFIG_DIR=/app/edge/config
ENV SIF_DATA_DIR=/data
ENV SIF_LOG_LEVEL=DEBUG
ENV PYTHONPATH=/app

EXPOSE 8000

CMD ["uvicorn", "edge.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
