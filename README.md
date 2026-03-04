# Seen-It-First-Edge

Edge-only AI license plate recognition system for NVIDIA Jetson Orin Nano Super.

## Phase 1 Scope

Detect and read US license plates at night (80–100 ft range) using 2–4 cameras.
No cloud. No Docker in production. Single-process edge service.

**US plates only.** No EU/International plate support in Phase 1.
Character set: A-Z 0-9. Validation regex: `^[A-Z0-9]{5,8}$`

### Model Strategy (Phase 1)

All models are **pretrained**. No custom training, fine-tuning, or dataset
creation is required for Phase 1 deployment.

| Model | Source | Custom Training |
|-------|--------|-----------------|
| YOLOv8n (vehicle) | COCO pretrained | Not required |
| YOLOv8s (plate) | Pretrained US-plate model | Not required |
| CRNN (OCR) | Pretrained OCR model | Not required |
| EfficientNet-Lite0 (classifier) | Pretrained | Not required |

Custom fine-tuning pipelines (nighttime datasets, model re-export) are
deferred to **Phase 3**. See `ai/training_phase3/README.md`.

### Capabilities

- **Camera ingestion**: 4x RTSP/CSI cameras at 30 FPS via GStreamer + NVDEC
- **Vehicle detection**: YOLOv8n pretrained at 12–15 FPS (TensorRT FP16)
- **Plate detection**: YOLOv8s pretrained US-plate model on vehicle crops only (TensorRT FP16)
- **OCR**: Pretrained CRNN with US plate post-processing (TensorRT FP16)
- **Classification**: EfficientNet-Lite0 pretrained for color/year bucket (TensorRT INT8)
- **Tracking**: Lightweight DeepSORT (IoU + appearance embedding)
- **Hotlist matching**: In-memory set with 60s cooldown, console + audio alerts
- **Storage**: SQLite with WAL mode
- **Thermal protection**: Two-level adaptive throttling

## Hardware Requirements

| Component | Specification |
|-----------|--------------|
| Compute | NVIDIA Jetson Orin Nano Super (8 GB) |
| Cameras | 2–4x Starvis 2 sensor cameras |
| IR | External 850nm IR illumination |
| Storage | 64 GB+ NVMe SSD |

## GPU Memory Budget

| Model | Engine Size | VRAM |
|-------|-----------|------|
| YOLOv8n (vehicle) | ~12 MB | ~45 MB |
| YOLOv8s (plate) | ~45 MB | ~90 MB |
| CRNN (OCR) | ~8 MB | ~30 MB |
| EfficientNet-Lite0 (classifier) | ~5 MB | ~15 MB |
| **Total models** | **~70 MB** | **~180 MB** |
| Runtime overhead | — | ~300 MB |
| **Total GPU** | — | **~480 MB** |

Target: < 75% GPU utilization on 8 GB shared memory.

## Inference Pipeline

```
Camera (30 FPS) → Vehicle Detection (15 FPS) → Plate Detection (on crops)
                                                      ↓
                                              OCR (conf > threshold)
                                                      ↓
                                              Hotlist Check → Alert
                                                      ↓
                                              Classifier (once/track)
                                                      ↓
                                              SQLite Storage
```

## Directory Structure

```
edge/
├── camera/          # GStreamer capture + camera management
├── inference/       # All ML models + scheduling
├── hotlist/         # Plate matching + CSV loader
├── storage/         # SQLite database + repository
├── system/          # Thermal monitoring, alerts
├── config/          # system.yaml
└── main.py          # Service entry point

models/              # TensorRT engine files (not in git)
systemd/             # systemd service file
ai/training_phase3/  # Phase 3 fine-tuning (not required for Phase 1)
docs/                # Build rules and documentation
```

## Setup

```bash
# On Jetson Orin Nano Super with JetPack 6.x installed

# Create virtual env (inherits system TensorRT/PyCUDA)
python3 -m venv --system-site-packages venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create data directory
mkdir -p data logs

# (Optional) Create hotlist
echo "ABC1234,stolen,high" > data/hotlist.csv

# Edit camera config
nano edge/camera/config.yaml

# Run
python -m edge.main
```

## Production Deployment

```bash
# Copy to /opt
sudo cp -r . /opt/seen-it-first
sudo useradd -r -s /bin/false sif
sudo chown -R sif:sif /opt/seen-it-first

# Install systemd service
sudo cp systemd/seen-it-first-edge.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable seen-it-first-edge
sudo systemctl start seen-it-first-edge

# Check status
sudo systemctl status seen-it-first-edge
journalctl -u seen-it-first-edge -f
```

## Night Vision

Night mode is auto-detected via histogram brightness.
Only plate ROI gets enhancement (CLAHE) — no full-frame processing.

## Thermal Protection

| Level | Trigger | Action |
|-------|---------|--------|
| 0 | < 80°C | Normal (15 FPS detection) |
| 1 | ≥ 80°C | Reduce to 10 FPS |
| 2 | ≥ 90°C | Reduce to 8 FPS + suspend classifier |

All thermal events logged to SQLite.

## Performance Targets

| Metric | Target |
|--------|--------|
| Ingest | 30 FPS per camera |
| Vehicle detection | 12–15 FPS |
| Hotlist alert latency | < 2 seconds |
| Operating temp | Stable at 90°F+ ambient |
