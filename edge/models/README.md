# Seen-It-First Model Directory

Place trained model files here before running the edge service.

## Required Models

| File | Format | Purpose | Input Shape |
|---|---|---|---|
| `yolo_vehicle_detector.pt` | PyTorch / TRT | Vehicle bounding box detection | 640×640 |
| `vehicle_make_model_classifier.onnx` | ONNX | Make / model / year classification | 1×3×224×224 |
| `vehicle_color_model.onnx` | ONNX | Color classification (12 classes) | 1×3×224×224 |
| `vehicle_embedding_model.onnx` | ONNX | 128-dim ReID embedding for fingerprinting | 1×3×128×128 |

## Label Files

| File | Format | Used by |
|---|---|---|
| `vehicle_make_model_labels.json` | JSON dict `{index: {vehicle_type, make, model, year_range}}` | `vehicle_classifier.py` |

## Fallback Behaviour

The system degrades gracefully when models are absent:

- **vehicle_make_model_classifier.onnx** missing → all make/model/year fields = `"unknown"`
- **vehicle_color_model.onnx** missing → HSV histogram fallback (always runs)
- **vehicle_embedding_model.onnx** missing → fingerprint hash derived from text fields only
- **All ONNX models** missing → ImageNet TRT classifier (if TRT engine present) provides coarse vehicle type

## Phase Roadmap

| Phase | Classifier | Color | ReID |
|---|---|---|---|
| 1 (current) | ImageNet TRT fallback | HSV histogram | Text-hash only |
| 2 | Fine-tuned ONNX on vehicle dataset | ONNX 12-class model | ONNX 128-dim model |
| 3 | Fleet-specific fine-tuned ONNX | — | Cosine similarity cross-cam |
