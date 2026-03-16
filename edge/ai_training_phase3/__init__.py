"""Phase 3 training utilities for dataset validation and preparation."""

from edge.ai_training_phase3.dataset_manifest import (
    DEFAULT_PLATE_REGEX,
    build_ocr_recognition_manifest,
    build_yolo_detection_manifest,
    has_errors,
    write_manifest,
)
from edge.ai_training_phase3.ocr_training import (
    OCRTrainingConfig,
    build_paddleocr_export_command,
    build_paddleocr_train_command,
    build_runtime_ocr_engine,
    find_paddleocr_config,
    find_paddleocr_pretrained_model,
    install_runtime_ocr_export,
    prepare_ocr_training_workspace,
)
from edge.ai_training_phase3.plate_training import (
    PlateTrainingConfig,
    build_runtime_plate_engine,
    install_runtime_plate_checkpoint,
    prepare_plate_training_workspace,
    train_plate_detector,
)

__all__ = [
    "DEFAULT_PLATE_REGEX",
    "OCRTrainingConfig",
    "PlateTrainingConfig",
    "build_ocr_recognition_manifest",
    "build_paddleocr_export_command",
    "build_paddleocr_train_command",
    "build_runtime_ocr_engine",
    "build_runtime_plate_engine",
    "build_yolo_detection_manifest",
    "find_paddleocr_config",
    "find_paddleocr_pretrained_model",
    "has_errors",
    "install_runtime_ocr_export",
    "install_runtime_plate_checkpoint",
    "prepare_ocr_training_workspace",
    "prepare_plate_training_workspace",
    "train_plate_detector",
    "write_manifest",
]
