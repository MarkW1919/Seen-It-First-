#!/usr/bin/env bash
# ─── Generate a .env file with random secrets ───
set -euo pipefail

ENV_FILE="${1:-.env}"

if [ -f "$ENV_FILE" ]; then
    echo "ERROR: $ENV_FILE already exists. Remove it first or specify a different path."
    exit 1
fi

POSTGRES_PASSWORD=$(openssl rand -base64 32 | tr -d '/+=' | head -c 32)
SECRET_KEY=$(openssl rand -hex 64)
GRAFANA_PASSWORD=$(openssl rand -base64 16 | tr -d '/+=' | head -c 16)

cat > "$ENV_FILE" <<EOF
# ─── RepoScan Pro Environment Configuration ───
# Auto-generated on $(date -u +"%Y-%m-%dT%H:%M:%SZ")

# Database
POSTGRES_HOST=db
POSTGRES_PORT=5432
POSTGRES_USER=reposcan
POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
POSTGRES_DB=reposcan

# Redis
REDIS_HOST=redis
REDIS_PORT=6379

# Backend
SECRET_KEY=${SECRET_KEY}
API_HOST=0.0.0.0
API_PORT=8000
CORS_ORIGINS=http://localhost:5173,http://localhost:3000

# AI Pipeline
AI_DEVICE=cuda
AI_PRECISION=fp16
DETECTION_CONFIDENCE=0.5
PLATE_CONFIDENCE=0.6
OCR_CONFIDENCE=0.7

# Camera
CAMERA_SOURCE=0
CAMERA_WIDTH=1920
CAMERA_HEIGHT=1080
CAMERA_FPS=30
RTSP_PORT=8554

# Map
MAP_DEFAULT_LAT=39.8283
MAP_DEFAULT_LNG=-98.5795
MAP_DEFAULT_ZOOM=5

# Alerts
ALERT_SOUND_ENABLED=true
ALERT_VIBRATION_ENABLED=true

# Storage
DATA_DIR=/data
CAPTURE_RETENTION_DAYS=30

# Monitoring
GRAFANA_PASSWORD=${GRAFANA_PASSWORD}
EOF

chmod 600 "$ENV_FILE"
echo "Generated $ENV_FILE with random secrets."
echo "Review and customize as needed."
