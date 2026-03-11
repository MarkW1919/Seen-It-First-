# Seen-It-First Edge Model Notes

This folder is for **tracked documentation/placeholders only**.

## Canonical runtime artifact root

All runtime model binaries and ONNX assets live under the repository-level
`models/` directory:

- `models/vehicle/vehicle.engine`
- `models/plate/plate.engine`
- `models/ocr/ocr.engine`
- `models/classifier/classifier.engine`
- `models/onnx/vehicle_make_model_classifier.onnx`
- `models/onnx/vehicle_color_model.onnx`
- `models/onnx/vehicle_embedding_model.onnx`
- `models/onnx/vehicle_make_model_labels.json`

## Notes

- `scripts/download_models.py` writes downloaded source checkpoints to
  `models/raw/`.
- `scripts/build_tensorrt_engines.py` converts/exports ONNX and TensorRT
  runtime artifacts into the canonical `models/` layout above.
- Startup preflight in `edge/main.py` logs absolute paths for any missing
  expected model files.
