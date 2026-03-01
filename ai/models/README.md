# AI Models Directory

This directory contains the AI model weights and label files used by the RepoScan Pro inference pipeline. Model files are not checked into version control due to their size.

## Expected Files

### ONNX Models (required for inference)

| File | Architecture | Purpose | Approx. Size |
|------|-------------|---------|-------------|
| `yolov8n_vehicles.onnx` | YOLOv8n | Vehicle detection (car, truck, SUV, van, motorcycle, bus) | ~12 MB |
| `yolov8n_plates.onnx` | YOLOv8n | License plate detection within vehicle crops | ~12 MB |
| `crnn_plate_ocr.onnx` | CRNN | OCR character recognition on plate images | ~20 MB |
| `efficientnet_ymm.onnx` | EfficientNet-B0 | Vehicle Year/Make/Model/Color classification | ~16 MB |

### TensorRT Engines (built at runtime on target device)

| File | Source ONNX | Notes |
|------|------------|-------|
| `yolov8n_vehicles.engine` | `yolov8n_vehicles.onnx` | Built automatically on first run |
| `yolov8n_plates.engine` | `yolov8n_plates.onnx` | Built automatically on first run |
| `crnn_plate_ocr.engine` | `crnn_plate_ocr.onnx` | Built automatically on first run |
| `efficientnet_ymm.engine` | `efficientnet_ymm.onnx` | Built automatically on first run |
| `deepsort_reid.engine` | ReID model | Used by the multi-object tracker |

TensorRT engines are device-specific and must be built on the target hardware (e.g., Jetson Orin Nano). They are generated automatically when the pipeline starts, or manually via:

```bash
python3 -m ai.tensorrt_utils
```

### Label Files

| File | Contents | Count |
|------|----------|-------|
| `labels/makes.json` | Vehicle manufacturer names (e.g., Toyota, Ford) | 50 |
| `labels/models.json` | Vehicle model names (e.g., Camry, F-150) | ~100 |
| `labels/years.json` | Model years as strings ("1990" through "2026") | 37 |
| `labels/colors.json` | Vehicle color names (e.g., black, white, silver) | ~15 |

Label files are JSON arrays of strings. They are referenced by `ai/config.yaml` and loaded by the vehicle classifier at runtime. The label array indices must correspond to the model's output class indices.

## How to Obtain Models

### Quick Start (download base model stubs)

```bash
cd ai
./download_models.sh
```

This downloads YOLOv8n base weights and generates CRNN and EfficientNet architecture stubs. These are starting points for fine-tuning, not production-ready models.

### Download Only Labels

```bash
./download_models.sh --labels
```

### Verify All Files

```bash
./download_models.sh --verify
# or
python3 -m ai.verify_models
```

### Individual Model Downloads

```bash
./download_models.sh --yolo        # Vehicle + plate detectors
./download_models.sh --ocr         # CRNN plate OCR
./download_models.sh --classifier  # EfficientNet vehicle classifier
```

## Training Custom Models

For production use, the base model stubs must be fine-tuned on appropriate datasets. See [docs/MODEL_TRAINING.md](../../docs/MODEL_TRAINING.md) for detailed training instructions covering:

1. **Vehicle Detector** -- Fine-tune YOLOv8n on vehicle-class data
2. **Plate Detector** -- Fine-tune YOLOv8n on license plate bounding boxes
3. **Plate OCR** -- Train CRNN with CTC loss on plate character data
4. **Vehicle Classifier** -- Train EfficientNet-B0 on Year/Make/Model/Color datasets

## Directory Structure

```
models/
  yolov8n_vehicles.onnx      # Vehicle detection ONNX
  yolov8n_vehicles.engine     # Vehicle detection TensorRT (device-built)
  yolov8n_plates.onnx         # Plate detection ONNX
  yolov8n_plates.engine       # Plate detection TensorRT (device-built)
  crnn_plate_ocr.onnx         # Plate OCR ONNX
  crnn_plate_ocr.engine       # Plate OCR TensorRT (device-built)
  efficientnet_ymm.onnx       # Vehicle classifier ONNX
  efficientnet_ymm.engine     # Vehicle classifier TensorRT (device-built)
  deepsort_reid.engine        # Tracker ReID TensorRT (device-built)
  labels/
    makes.json                # Vehicle make labels
    models.json               # Vehicle model labels
    years.json                # Year labels (1990-2026)
    colors.json               # Vehicle color labels
```
