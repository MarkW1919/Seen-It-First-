#!/usr/bin/env bash
# ─── RepoScan Pro: Download & Prepare AI Model Weights ───
#
# Downloads pretrained models and converts them to ONNX format.
# TensorRT .engine files are built at runtime on the target device.
#
# Usage:
#   ./download_models.sh              # Download all models + generate labels
#   ./download_models.sh --yolo       # Download only YOLO vehicle/plate models
#   ./download_models.sh --ocr        # Download only OCR model
#   ./download_models.sh --classifier # Download only classifier model
#   ./download_models.sh --labels     # Generate label files only
#   ./download_models.sh --verify     # Verify all model files are present
set -euo pipefail

MODELS_DIR="$(cd "$(dirname "$0")/models" && pwd)"
mkdir -p "$MODELS_DIR"

echo "=== RepoScan Pro Model Downloader ==="
echo "Target directory: $MODELS_DIR"
echo ""

# ─── 1. Vehicle Detection: YOLOv8n ───
download_vehicle_model() {
    echo "[1/4] Vehicle Detector (YOLOv8n) ..."
    if [ -f "$MODELS_DIR/yolov8n_vehicles.onnx" ]; then
        echo "  Already exists, skipping."
        return
    fi
    python3 -c "
from ultralytics import YOLO
model = YOLO('yolov8n.pt')
model.export(format='onnx', imgsz=640, opset=17, simplify=True)
import shutil, pathlib
src = pathlib.Path('yolov8n.onnx')
if src.exists():
    shutil.move(str(src), '$MODELS_DIR/yolov8n_vehicles.onnx')
    print('  Exported to yolov8n_vehicles.onnx')
"
    echo "  Done."
}

# ─── 2. Plate Detection: YOLOv8n (fine-tune placeholder) ───
download_plate_model() {
    echo "[2/4] Plate Detector (YOLOv8n) ..."
    if [ -f "$MODELS_DIR/yolov8n_plates.onnx" ]; then
        echo "  Already exists, skipping."
        return
    fi
    echo "  NOTE: Plate detection requires a fine-tuned model."
    echo "  Downloading base YOLOv8n as starting point for transfer learning."
    python3 -c "
from ultralytics import YOLO
model = YOLO('yolov8n.pt')
model.export(format='onnx', imgsz=640, opset=17, simplify=True)
import shutil, pathlib
src = pathlib.Path('yolov8n.onnx')
if src.exists():
    shutil.move(str(src), '$MODELS_DIR/yolov8n_plates.onnx')
    print('  Exported to yolov8n_plates.onnx')
"
    echo "  To fine-tune on license plate data, see docs/MODEL_TRAINING.md"
    echo "  Done."
}

# ─── 3. Plate OCR: CRNN stub ───
download_ocr_model() {
    echo "[3/4] Plate OCR (CRNN) ..."
    if [ -f "$MODELS_DIR/crnn_plate_ocr.onnx" ]; then
        echo "  Already exists, skipping."
        return
    fi
    echo "  Generating CRNN architecture ONNX export ..."
    python3 -c "
import torch
import torch.nn as nn

class CRNN(nn.Module):
    def __init__(self, num_classes=37):  # A-Z + 0-9 + blank
        super().__init__()
        self.cnn = nn.Sequential(
            nn.Conv2d(1, 64, 3, 1, 1), nn.ReLU(), nn.MaxPool2d(2, 2),
            nn.Conv2d(64, 128, 3, 1, 1), nn.ReLU(), nn.MaxPool2d(2, 2),
            nn.Conv2d(128, 256, 3, 1, 1), nn.BatchNorm2d(256), nn.ReLU(),
            nn.Conv2d(256, 256, 3, 1, 1), nn.ReLU(), nn.MaxPool2d((2, 1), (2, 1)),
            nn.Conv2d(256, 512, 3, 1, 1), nn.BatchNorm2d(512), nn.ReLU(),
        )
        self.rnn = nn.LSTM(512 * 6, 256, num_layers=2, bidirectional=True, batch_first=True)
        self.fc = nn.Linear(512, num_classes)

    def forward(self, x):
        conv = self.cnn(x)
        b, c, h, w = conv.size()
        conv = conv.permute(0, 3, 1, 2).reshape(b, w, c * h)
        rnn_out, _ = self.rnn(conv)
        output = self.fc(rnn_out)
        return output

model = CRNN()
dummy = torch.randn(1, 1, 48, 200)
torch.onnx.export(model, dummy, '$MODELS_DIR/crnn_plate_ocr.onnx',
                   input_names=['input'], output_names=['output'],
                   dynamic_axes={'input': {0: 'batch'}, 'output': {0: 'batch'}},
                   opset_version=17)
print('  Exported CRNN to crnn_plate_ocr.onnx')
print('  NOTE: This is an untrained model. Train on plate OCR data before production use.')
"
    echo "  Done."
}

# ─── 4. Vehicle Classifier: EfficientNet stub ───
download_classifier_model() {
    echo "[4/4] Vehicle Classifier (EfficientNet-B0) ..."
    if [ -f "$MODELS_DIR/efficientnet_ymm.onnx" ]; then
        echo "  Already exists, skipping."
        return
    fi
    python3 -c "
import torch
from torchvision.models import efficientnet_b0
model = efficientnet_b0(weights=None)
model.classifier[1] = torch.nn.Linear(1280, 1000)  # placeholder classes
model.eval()
dummy = torch.randn(1, 3, 224, 224)
torch.onnx.export(model, dummy, '$MODELS_DIR/efficientnet_ymm.onnx',
                   input_names=['input'], output_names=['output'],
                   dynamic_axes={'input': {0: 'batch'}, 'output': {0: 'batch'}},
                   opset_version=17)
print('  Exported EfficientNet-B0 to efficientnet_ymm.onnx')
print('  NOTE: Retrain on Year/Make/Model dataset before production use.')
"
    echo "  Done."
}

# ─── 5. Label Files for Vehicle Classifier ───
generate_labels() {
    echo "[labels] Generating vehicle classifier label files ..."
    LABELS_DIR="$MODELS_DIR/labels"
    mkdir -p "$LABELS_DIR"

    if [ -f "$LABELS_DIR/makes.json" ] && [ -f "$LABELS_DIR/models.json" ] \
       && [ -f "$LABELS_DIR/years.json" ] && [ -f "$LABELS_DIR/colors.json" ]; then
        echo "  All label files already exist, skipping."
        return
    fi

    SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

    python3 -c "
import json, os

labels_dir = '$LABELS_DIR'

makes = [
    'Acura', 'Alfa Romeo', 'Aston Martin', 'Audi', 'Bentley',
    'BMW', 'Buick', 'Cadillac', 'Chevrolet', 'Chrysler',
    'Dodge', 'Ferrari', 'Fiat', 'Ford', 'Genesis',
    'GMC', 'Honda', 'Hyundai', 'Infiniti', 'Jaguar',
    'Jeep', 'Kia', 'Lamborghini', 'Land Rover', 'Lexus',
    'Lincoln', 'Lotus', 'Lucid', 'Maserati', 'Mazda',
    'McLaren', 'Mercedes-Benz', 'Mini', 'Mitsubishi', 'Nissan',
    'Polestar', 'Pontiac', 'Porsche', 'Ram', 'Rivian',
    'Rolls-Royce', 'Saturn', 'Scion', 'Smart', 'Subaru',
    'Suzuki', 'Tesla', 'Toyota', 'Volkswagen', 'Volvo',
]

models = [
    'Accord', 'Altima', 'Avalon', 'Blazer', 'Bronco',
    'C-Class', 'Camaro', 'Camry', 'Canyon', 'Challenger',
    'Charger', 'Cherokee', 'Civic', 'Colorado', 'Compass',
    'Corolla', 'Corvette', 'CR-V', 'CT4', 'CT5',
    'Durango', 'E-Class', 'Elantra', 'Enclave', 'Encore',
    'Envision', 'Equinox', 'Escalade', 'Escape', 'Explorer',
    'Expedition', 'F-150', 'Forester', 'Forte', 'Frontier',
    'GLC', 'GLE', 'Golf', 'Grand Cherokee', 'Highlander',
    'HR-V', 'Impreza', 'IS', 'Jetta', 'K5',
    'Kicks', 'Kona', 'Mach-E', 'Malibu', 'Maverick',
    'Maxima', 'Model 3', 'Model S', 'Model X', 'Model Y',
    'Murano', 'Mustang', 'NX', 'Odyssey', 'Optima',
    'Outback', 'Outlander', 'Pacifica', 'Passport', 'Pathfinder',
    'Pilot', 'Prius', 'Q5', 'Q7', 'RAV4',
    'Ranger', 'Ridgeline', 'Rogue', 'RX', 'Santa Fe',
    'Seltos', 'Sentra', 'Sierra', 'Silverado', 'Sorento',
    'Soul', 'Sportage', 'Stinger', 'Suburban', 'Tacoma',
    'Tahoe', 'Telluride', 'Tiguan', 'Titan', 'Traverse',
    'Trax', 'Tucson', 'Tundra', 'Venue', 'Wrangler',
    'X3', 'X5', 'XT4', 'XT5', 'Yukon',
]

years = [str(y) for y in range(1990, 2027)]

colors = [
    'black', 'white', 'silver', 'gray', 'red',
    'blue', 'brown', 'green', 'beige', 'gold',
    'orange', 'yellow', 'purple', 'maroon', 'teal',
]

for name, data in [('makes', makes), ('models', models), ('years', years), ('colors', colors)]:
    path = os.path.join(labels_dir, f'{name}.json')
    if not os.path.exists(path):
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)
            f.write('\n')
        print(f'  Generated {name}.json ({len(data)} labels)')
    else:
        print(f'  {name}.json already exists, skipping.')
"
    echo "  Done."
}

# ─── 6. Verify Models ───
run_verify() {
    SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
    echo "[verify] Running model verification ..."
    python3 "$SCRIPT_DIR/verify_models.py"
    exit $?
}

# ─── Parse args ───
if [ $# -eq 0 ]; then
    download_vehicle_model
    download_plate_model
    download_ocr_model
    download_classifier_model
    generate_labels
else
    case "$1" in
        --yolo)
            download_vehicle_model
            download_plate_model
            ;;
        --ocr)
            download_ocr_model
            ;;
        --classifier)
            download_classifier_model
            ;;
        --labels)
            generate_labels
            ;;
        --verify)
            run_verify
            ;;
        *)
            echo "Usage: $0 [--yolo|--ocr|--classifier|--labels|--verify]"
            exit 1
            ;;
    esac
fi

echo ""
echo "=== Model download complete ==="
echo "Models saved to: $MODELS_DIR"
echo ""
echo "Next steps:"
echo "  1. Fine-tune plate detector on your license plate dataset"
echo "  2. Train CRNN OCR model on plate character data"
echo "  3. Train EfficientNet classifier on Year/Make/Model data"
echo "  4. Convert to TensorRT on Jetson: python3 -m ai.tensorrt_utils"
