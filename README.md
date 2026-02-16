# RepoScan Pro

AI-powered License Plate Recognition (LPR) and Vehicle Detection system built for repossession agents and tow truck operators. Runs on NVIDIA Jetson Orin Nano Super with Sony Starvis 2 IMX685 camera.

## Architecture

```
┌──────────────────────────────────────────────────────┐
│  Frontend PWA (Vite + React 18 + TypeScript)         │
│  Tailwind CSS · Leaflet Maps · Zustand · TanStack    │
├──────────────────────────────────────────────────────┤
│  Nginx Reverse Proxy (SSL · WebSocket · RTSP)        │
├──────────────────────────────────────────────────────┤
│  Backend API (FastAPI · async SQLAlchemy 2.0)        │
│  PostgreSQL+PostGIS · Redis · JWT · WebSocket        │
├──────────────────────────────────────────────────────┤
│  AI Pipeline (TensorRT · YOLOv8 · CRNN · DeepSORT)  │
│  Vehicle Detection · Plate OCR · YMM Classification  │
├──────────────────────────────────────────────────────┤
│  Camera Layer (GStreamer · MIPI CSI-2 · PTZ · RTSP)  │
│  Sony IMX685 · Night Vision · Auto-Tracking          │
├──────────────────────────────────────────────────────┤
│  Jetson Orin Nano Super (8GB) · 15W · CUDA · DLA    │
└──────────────────────────────────────────────────────┘
```

## Quick Start

```bash
# 1. Clone and configure
cp .env.example .env
# Edit .env with your settings

# 2. Launch all services
docker compose up -d

# 3. Open the PWA
# Navigate to http://localhost in your browser
```

## Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| Frontend | Vite + React 18 + TypeScript | Fast builds, type safety, modern DX |
| Styling | Tailwind CSS | Utility-first, rapid dark-mode UI |
| State | Zustand + TanStack Query | Lightweight state + smart data caching |
| Maps | Leaflet + OpenStreetMap | Free, no API key required |
| Backend | FastAPI + async SQLAlchemy 2.0 | High-perf async Python API |
| Database | PostgreSQL 16 + PostGIS | Spatial queries for GPS data |
| Cache | Redis 7 | Hot list caching, pub/sub alerts |
| AI/ML | TensorRT + YOLOv8 + CRNN | Optimized inference on Jetson |
| Tracking | DeepSORT | Multi-object tracking across frames |
| Camera | GStreamer + Argus | Hardware-accelerated video pipeline |
| Deploy | Docker Compose + systemd | Container orchestration + auto-start |
| Monitor | Prometheus + Grafana | System health and performance |

## Key Features

- **Real-time LPR** — 25-30 FPS plate detection and OCR for all 50 US states
- **Hot List Alerts** — Instant audio/visual alerts when a target plate is spotted
- **Vehicle Classification** — Year, make, model, and color identification
- **Night Vision** — Sony Starvis 2 IMX685 with IR LED control
- **GPS Mapping** — Live tracking, route history, and detection heatmaps
- **Offline PWA** — Full functionality without internet, syncs when connected
- **PTZ Auto-Tracking** — Camera follows detected vehicles automatically
- **Multi-agent Support** — Role-based access for teams

## Project Structure

```
├── backend/       FastAPI server, database models, auth, WebSocket
├── frontend/      React PWA with Tailwind, maps, real-time alerts
├── ai/            TensorRT inference pipeline, models, tracking
├── camera/        GStreamer capture, PTZ control, RTSP streaming
├── deploy/        Nginx, Prometheus, Grafana, systemd, scripts
└── docs/          Hardware guide, API reference, quick start
```

## Hardware Requirements

- **Compute**: NVIDIA Jetson Orin Nano Super (8GB)
- **Camera**: Sony Starvis 2 IMX685 (MIPI CSI-2)
- **Storage**: 1TB NVMe SSD
- **Network**: 4G/5G modem or WiFi
- **Power**: 15W vehicle power adapter

## Performance

| Metric | Target |
|--------|--------|
| Detection FPS | 25-30 @ 1080p |
| LPR Accuracy (Day) | 92-95% |
| LPR Accuracy (Night) | 85-90% |
| End-to-End Latency | <500ms |
| Hot List Match | <100ms |
| Power Draw | 10-15W |
| Memory | <6GB |
