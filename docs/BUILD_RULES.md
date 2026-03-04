# Build Rules

Mandatory build safety rules for Seen-It-First-Edge development.

## Sequential Build Order

Build subsystems sequentially in this order:

1. `edge/storage/` — Database and schema
2. `edge/config/` — System configuration
3. `edge/camera/` — Camera capture and management
4. `edge/inference/` — All ML models, tracker, and scheduler
5. `edge/hotlist/` — Plate matching and CSV loader
6. `edge/system/` — Thermal monitoring, system monitoring, alerts
7. `edge/main.py` — Service orchestrator

Each layer depends only on layers above it.

## Subsystem Requirements

Every subsystem must:

- **Run independently** — each module can be imported and instantiated
  without requiring other subsystems to be running.
- **Import cleanly** — `python -c "from edge.<module> import *"` must
  succeed without errors.
- **Pass linting** — no syntax errors, no undefined names, no unused
  imports that break execution.
- **Start without runtime errors** — instantiation must not throw
  exceptions (missing engine files are handled gracefully, not with
  crashes).

## Code Quality Rules

- **No placeholder functions** — every function must contain a real
  implementation, not `pass` or `raise NotImplementedError`.
- **No "TODO" stubs** — do not commit code with TODO placeholders
  where the implementation is required for the system to function.
- **No empty class shells** — every class must have working methods
  that fulfill its documented contract.

## Verification Commands

```bash
# Verify all modules import cleanly
python -c "from edge.storage.database import Database"
python -c "from edge.camera.capture import CameraCapture"
python -c "from edge.camera.manager import CameraManager"
python -c "from edge.inference.vehicle_detector import VehicleDetector"
python -c "from edge.inference.plate_detector import PlateDetector"
python -c "from edge.inference.ocr import PlateOCR"
python -c "from edge.inference.classifier import VehicleClassifier"
python -c "from edge.inference.tracker import Tracker"
python -c "from edge.inference.scheduler import InferenceScheduler"
python -c "from edge.hotlist.loader import HotlistLoader"
python -c "from edge.hotlist.matcher import HotlistMatcher"
python -c "from edge.system.thermal import ThermalMonitor"
python -c "from edge.system.monitoring import SystemMonitor"
python -c "from edge.system.alerts import AlertManager"
python -c "from edge.main import EdgeService"
```

## Model Strategy

Phase 1 uses pretrained models only. No custom training dependency.

Inference modules must initialize without requiring:
- Custom training runs
- Dataset creation pipelines
- Fine-tuning steps

Models that are not present on disk are handled gracefully (logged
warning, pipeline continues with available models).

## GPU Budget Lock

Do not increase model sizes beyond:

| Model | Max Variant | Precision |
|-------|-------------|-----------|
| Vehicle detection | YOLOv8n | FP16 |
| Plate detection | YOLOv8s | FP16 |
| OCR | CRNN | FP16 |
| Classifier | EfficientNet-Lite0 | INT8 |

Max concurrent inference workers: 2.
Frame skipping: enabled (drop oldest on overflow).
