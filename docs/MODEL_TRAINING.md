# Model Training Guide

RepoScan Pro uses four AI models. This guide covers how to train or fine-tune each one.

## Overview

| Model | Architecture | Purpose | Input | Output |
|-------|-------------|---------|-------|--------|
| Vehicle Detector | YOLOv8n | Detect vehicles in frame | 640x640 image | Bounding boxes + classes |
| Plate Detector | YOLOv8n | Detect plates in vehicle crop | 640x640 image | Plate bounding boxes |
| Plate OCR | CRNN | Read plate characters | 200x48 grayscale | Character sequence |
| Vehicle Classifier | EfficientNet-B0 | Year/Make/Model/Color | 224x224 image | YMM + color class |

## 1. Vehicle Detector (YOLOv8n)

The base YOLOv8n already detects cars, trucks, and buses from COCO. Fine-tuning on repo-specific vehicle classes improves accuracy:

```bash
# Prepare dataset in YOLO format:
# dataset/
#   images/train/  images/val/
#   labels/train/  labels/val/
#   data.yaml

# data.yaml:
# train: images/train
# val: images/val
# nc: 6
# names: [car, truck, suv, van, motorcycle, bus]

from ultralytics import YOLO
model = YOLO("yolov8n.pt")
model.train(data="dataset/data.yaml", epochs=100, imgsz=640, batch=16)
model.export(format="onnx", imgsz=640, opset=17, simplify=True)
```

## 2. Plate Detector (YOLOv8n)

Requires a license plate detection dataset:

- **Recommended datasets**: CCPD, OpenALPR benchmark, RodoSol-ALPR
- Label plates with bounding boxes in YOLO format (single class: `plate`)

```python
from ultralytics import YOLO
model = YOLO("yolov8n.pt")
model.train(data="plates_dataset/data.yaml", epochs=150, imgsz=640, batch=16)
model.export(format="onnx", imgsz=640, opset=17, simplify=True)
```

## 3. Plate OCR (CRNN)

CTC-based sequence recognition model:

- **Training data**: Cropped plate images with text labels
- **Augmentations**: Random perspective, blur, noise, brightness jitter
- **Character set**: `ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789` (36 chars + CTC blank)

```python
# See ai/plate_ocr.py for the CRNN architecture
# Training loop uses CTC loss:
import torch
criterion = torch.nn.CTCLoss(blank=0, zero_infinity=True)
optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)

# After training:
torch.onnx.export(model, dummy_input, "crnn_plate_ocr.onnx", opset_version=17)
```

## 4. Vehicle Classifier (EfficientNet-B0)

Multi-task classification for Year, Make, Model, and Color:

- **Recommended datasets**: CompCars, Stanford Cars, VMMRdb
- **Architecture**: Shared backbone with 4 classification heads

```python
from torchvision.models import efficientnet_b0
model = efficientnet_b0(weights="IMAGENET1K_V1")
# Replace classifier head with multi-task heads
# Train with cross-entropy loss on each task
```

## TensorRT Conversion (on Jetson)

After training, convert ONNX models to TensorRT for maximum inference speed:

```bash
# On the Jetson device:
trtexec --onnx=models/yolov8n_vehicles.onnx \
        --saveEngine=models/yolov8n_vehicles.engine \
        --fp16

# Or use the utility:
python3 -m ai.tensorrt_utils
```

## Download Pretrained Stubs

To get started with base models for fine-tuning:

```bash
cd ai
./download_models.sh
```
