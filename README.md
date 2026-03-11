# Seen-It-First-Edge

Edge-only AI license plate recognition system for NVIDIA Jetson Orin Nano Super.

## Phase 1 Scope

Detect and read US license plates at night (80–100 ft range) using 2–4 cameras.
No cloud. No Docker in production. Single-process edge service.

**US plates only.** No EU/International plate support in Phase 1.
Character set: A-Z 0-9. Validation regex: `^[A-Z0-9]{2,8}$`

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
deferred to **Phase 3**. See `edge/ai_training_phase3/README.md`.

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

models/              # Runtime TensorRT/ONNX artifacts (generated locally)
edge/models/         # Tracked documentation for expected model files
systemd/             # systemd service file
edge/ai_training_phase3/  # Phase 3 fine-tuning (not required for Phase 1)
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

### API Security Defaults

- API binds to `127.0.0.1:8080` by default for single-user/local deployments.
- To require auth on `/navigation/*` and `/ws`, set `api.auth_token` in `edge/config/system.yaml` and pass `X-API-Key` (or `Authorization: Bearer <token>`).
- If you expose the API on LAN (`0.0.0.0`), also restrict `api.allowed_origins` and use firewall rules.
## Preflight Before Enable

Run the deployment preflight checker before enabling the service. It validates:

- required config files exist
- required model/engine paths from `edge/config/system.yaml`
- writable runtime directories (`data/`, `logs/`)
- camera config parse + enabled camera validity

```bash
python scripts/preflight_check.py \
  --system-config edge/config/system.yaml \
  --camera-config edge/camera/config.yaml
```

The checker exits non-zero on required failures and prints actionable errors with exact missing keys/paths.

## Production Deployment

Use the installer script as the **canonical deployment path**:

```bash
# From repository root
sudo ./scripts/install_edge_service.sh
```

Dry-run preview (no changes applied):

```bash
./scripts/install_edge_service.sh --dry-run
```

After installation:

```bash
sudo systemctl start seen-it-first-edge.service
sudo systemctl status seen-it-first-edge.service
sudo journalctl -u seen-it-first-edge.service -f
```

`seen-it-first-edge.service` runs as `Type=simple` without systemd watchdog heartbeats.
The runtime logs this at startup as `Systemd watchdog mode: disabled (Type=simple, no heartbeat notifications)`.

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

## Secure Navigation API Configuration

The FastAPI service now enforces authentication for all `/navigation/*` routes and `/ws`.

### Example `edge/config/system.yaml` API block

```yaml
api:
  host: "0.0.0.0"
  port: 8080
  environment: "production"  # fail-closed if allowed_origins is empty
  allowed_origins:
    - "https://dashboard.example.com"
    - "https://ops.example.com"
  auth:
    enabled: true
    api_key: "replace-with-long-random-secret"
    bearer_token: ""  # optional alternative to api_key
```

### Dashboard connection requirements

- HTTP requests to navigation endpoints **must** include one of:
  - `X-API-Key: <api_key>`
  - `Authorization: Bearer <bearer_token>`
- WebSocket clients connecting to `/ws` must authenticate via either:
  - Header: `X-API-Key: <api_key>`
  - Header: `Authorization: Bearer <bearer_token>`
  - Query parameter fallback (if your WS client cannot set headers):
    - `ws://<edge-host>:8080/ws?api_key=<api_key>`
    - `ws://<edge-host>:8080/ws?token=<bearer_token>`

### CORS hardening behavior

- `allow_origins=["*"]` is no longer allowed.
- `api.allowed_origins` must be an explicit list of trusted dashboard origins.
- When `api.environment: "production"`, startup fails if `allowed_origins` is empty.
