# Phase 3: Custom Model Fine-Tuning Pipeline

**Not required for Phase 1 deployment.**

Phase 1 uses pretrained models exclusively. This directory is reserved
for Phase 3 custom training pipelines and dataset utilities.

## Phase 3 Scope

When Phase 3 begins, this directory will contain:

1. **Nighttime dataset collection** — scripts for capturing and labeling
   night LPR training data from deployed edge units.

2. **Fine-tuning pipelines**:
   - YOLOv8s plate detector fine-tuning on collected US plate data
   - CRNN OCR fine-tuning on night-captured plate crops
   - EfficientNet-Lite0 classifier fine-tuning on regional vehicle data

3. **Model export + TensorRT optimization** — automated scripts for:
   - PyTorch/ONNX export
   - TensorRT FP16/INT8 engine building
   - Validation against Phase 1 accuracy baselines

## Phase 1 Model Strategy

| Model | Phase 1 Source | Custom Training |
|-------|---------------|-----------------|
| YOLOv8n (vehicle) | COCO pretrained | Not required |
| YOLOv8s (plate) | Pretrained US-plate model | Not required |
| CRNN (OCR) | Pretrained OCR model | Not required |
| EfficientNet-Lite0 | Pretrained classifier | Not required |

All models are deployed as-is in Phase 1 after TensorRT engine conversion.
No custom datasets, no retraining, no fine-tuning.

## Utilities Added Here

- `dataset_manifest.py`
  - validates YOLO detection datasets laid out as `images/{train,val,test}` + `labels/{train,val,test}`
  - validates OCR recognition datasets laid out as `images/` + `labels.csv`
  - produces JSON-serializable manifests for dataset quality checks before training

## Script Entry Points

- `python scripts/validate_training_dataset.py --task yolo_detection --dataset-root <path>`
- `python scripts/validate_training_dataset.py --task ocr_recognition --dataset-root <path>`

These utilities are intentionally isolated from runtime inference code. They
exist to support future accuracy work without changing the deployed edge
pipeline layout.
