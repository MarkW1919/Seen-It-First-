# SEEN IT FIRST

Edge AI vehicle identification and license plate recognition system built for NVIDIA Jetson Orin Nano Super.

## System Overview

SEEN IT FIRST is a real-time, vehicle-mounted LPR system that captures, identifies, and alerts on vehicles of interest using 4 simultaneous camera streams processed by a cascaded AI inference pipeline. The system runs entirely on-device with no cloud dependency.

**US license plates only.** All OCR, validation, and formatting rules target US plate standards.

## Hardware Architecture

```
┌─────────────────────────────────────────────────┐
│              Jetson Orin Nano Super              │
│  8GB VRAM · 1024 CUDA cores · JetPack 6.x       │
│                                                   │
│  ┌─────────────┐   ┌─────────────┐               │
│  │  Housing A   │   │  Housing B   │              │
│  │ IMX462 (LPR) │   │ IMX462 (LPR) │             │
│  │ IMX327 (Wide)│   │ IMX327 (Wide)│             │
│  │ 850nm IR     │   │ 850nm IR     │             │
│  └─────────────┘   └─────────────┘               │
│                                                   │
│  Target: 80–100 ft plate read range              │
│  4 cameras · 30 FPS capture · 15 FPS inference   │
└─────────────────────────────────────────────────┘
```

## Inference Pipeline

Cascaded inference — each stage fires only when the prior stage qualifies:

| Stage              | Frequency   | Scope              | Trigger                          |
|--------------------|-------------|---------------------|----------------------------------|
| Frame Capture      | 30 FPS      | Full frame          | Always (NVDEC hardware decode)   |
| Vehicle Detection  | 15 FPS      | Full frame 640x640  | Every 2nd captured frame         |
| Plate Detection    | On demand   | Vehicle ROI only    | Vehicle confidence >= 0.45       |
| OCR                | On demand   | Plate ROI only      | Plate confidence >= 0.55         |
| Vehicle Classifier | Once/track  | Best vehicle crop   | New confirmed DeepSORT track     |
| DeepSORT Tracker   | 15 FPS      | Detection boxes     | Vehicle detection output         |

## GPU Memory Budget

| Component             | VRAM (MB) |
|-----------------------|-----------|
| YOLOv8n vehicle det   | 180       |
| YOLOv8s plate det     | 280       |
| CRNN OCR              | 50        |
| EfficientNet-Lite0    | 60        |
| DeepSORT ReID         | 40        |
| CUDA context + buffers| 550       |
| **Total**             | **1,160** |

Budget cap: 75% of 8 GB VRAM (6,144 MB). Headroom: ~5 GB.

## Thermal Protection

| GPU Temp | Action                                      |
|----------|---------------------------------------------|
| < 75C    | Full operation: 15 FPS detection            |
| 75-84C   | Reduce to 10 FPS detection                  |
| 85-89C   | Reduce to 8 FPS detection                   |
| >= 90C   | Suspend classifier, detection at 5 FPS      |
| >= 95C   | Suspend all inference, critical alert        |

## Folder Structure

```
edge/              Jetson-side AI system
  camera/          GStreamer capture, multi-stream manager, health monitoring
  inference/       YOLOv8 detection, CRNN OCR, EfficientNet classifier, DeepSORT
  models/          TensorRT engine files (gitignored)
  fusion/          Plate + vehicle fusion, confidence scoring, hotlist matching
  night/           ROI-only CLAHE enhancement, exposure hooks
  ptz/             Pelco-D / ONVIF PTZ control, auto-tracking
  database/        SQLite connection, schema, repository
  api/             FastAPI REST + WebSocket endpoints
  utils/           Logging, image helpers, thermal monitoring
  config/          YAML configuration files
  main.py          System entry point

dashboard/         Windows tactical UI (React + Vite + TypeScript + Tailwind)
deployment/        Dockerfiles (dev), systemd (prod), nginx, Jetson setup guide
docs/              Architecture and performance tuning documentation
scripts/           Model download and TensorRT conversion utilities
tests/             Integration and system tests
```

## Development Workflow

Docker Compose is provided for development only:

```bash
# Start development environment
docker compose up --build

# Run edge system locally (requires Jetson or CUDA GPU)
cd edge && python main.py

# Run dashboard dev server
cd dashboard && npm install && npm run dev
```

## Production Deployment

Production runs via **systemd** (not Docker). The dashboard is pre-built as a static SPA and served by nginx.

```bash
# On Jetson: install and start
sudo cp deployment/systemd/*.service /etc/systemd/system/
sudo systemctl enable --now seen-it-first-edge

# Build dashboard static files (one-time, or on update)
cd dashboard && npm run build
# nginx serves dashboard/dist/ and proxies /api/ to uvicorn
```

See `deployment/jetson-setup.md` for full installation guide.

## Performance Targets

- 30 FPS ingest per camera (NVDEC hardware decode)
- 12-15 FPS vehicle detection per camera
- < 2 second hotlist alert latency
- <= 3 GB total GPU memory usage
- Stable operation in 90F+ ambient temperature
- < 5% dropped frames under full load
