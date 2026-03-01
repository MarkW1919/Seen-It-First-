#!/usr/bin/env python3
"""Verify that all required AI model files are present and valid.

Checks for ONNX/TensorRT model weights, label files, and configuration.
Reports missing files with instructions on how to obtain them.

Usage:
    python3 -m ai.verify_models          # Run from project root
    python3 ai/verify_models.py          # Run directly
    python3 ai/verify_models.py --quiet  # Exit code only (0=ok, 1=missing)
"""

import argparse
import json
import os
import sys
from pathlib import Path

# Resolve the models directory relative to this script
SCRIPT_DIR = Path(__file__).resolve().parent
MODELS_DIR = SCRIPT_DIR / "models"

# Required model files: (relative path from models/, description, how to obtain)
REQUIRED_MODELS = [
    {
        "path": "yolov8n_vehicles.onnx",
        "description": "Vehicle detector (YOLOv8n) ONNX weights",
        "size_hint": "~12 MB",
        "obtain": "Run: ./ai/download_models.sh --yolo",
    },
    {
        "path": "yolov8n_plates.onnx",
        "description": "License plate detector (YOLOv8n) ONNX weights",
        "size_hint": "~12 MB",
        "obtain": "Run: ./ai/download_models.sh --yolo",
    },
    {
        "path": "crnn_plate_ocr.onnx",
        "description": "Plate OCR (CRNN) ONNX weights",
        "size_hint": "~20 MB",
        "obtain": "Run: ./ai/download_models.sh --ocr",
    },
    {
        "path": "efficientnet_ymm.onnx",
        "description": "Vehicle classifier (EfficientNet-B0) ONNX weights",
        "size_hint": "~16 MB",
        "obtain": "Run: ./ai/download_models.sh --classifier",
    },
]

# TensorRT engine files (built at runtime on target device)
OPTIONAL_ENGINES = [
    {
        "path": "yolov8n_vehicles.engine",
        "description": "Vehicle detector TensorRT engine",
        "obtain": "Built automatically on first run, or: python3 -m ai.tensorrt_utils",
    },
    {
        "path": "yolov8n_plates.engine",
        "description": "Plate detector TensorRT engine",
        "obtain": "Built automatically on first run, or: python3 -m ai.tensorrt_utils",
    },
    {
        "path": "crnn_plate_ocr.engine",
        "description": "Plate OCR TensorRT engine",
        "obtain": "Built automatically on first run, or: python3 -m ai.tensorrt_utils",
    },
    {
        "path": "efficientnet_ymm.engine",
        "description": "Vehicle classifier TensorRT engine",
        "obtain": "Built automatically on first run, or: python3 -m ai.tensorrt_utils",
    },
    {
        "path": "deepsort_reid.engine",
        "description": "DeepSORT re-identification TensorRT engine",
        "obtain": "Built from ReID ONNX model on target device",
    },
]

# Label files required by the vehicle classifier
REQUIRED_LABELS = [
    {
        "path": "labels/makes.json",
        "description": "Vehicle make labels (e.g., Toyota, Ford, ...)",
        "obtain": "Run: ./ai/download_models.sh --labels",
    },
    {
        "path": "labels/models.json",
        "description": "Vehicle model labels (e.g., Camry, F-150, ...)",
        "obtain": "Run: ./ai/download_models.sh --labels",
    },
    {
        "path": "labels/years.json",
        "description": "Vehicle year labels (1990-2026)",
        "obtain": "Run: ./ai/download_models.sh --labels",
    },
    {
        "path": "labels/colors.json",
        "description": "Vehicle color labels (e.g., black, white, ...)",
        "obtain": "Run: ./ai/download_models.sh --labels",
    },
]


def _check_file(models_dir: Path, entry: dict) -> dict:
    """Check if a file exists and return its status."""
    filepath = models_dir / entry["path"]
    exists = filepath.is_file()
    result = {
        "path": entry["path"],
        "full_path": str(filepath),
        "description": entry["description"],
        "exists": exists,
        "obtain": entry["obtain"],
    }
    if exists:
        size_bytes = filepath.stat().st_size
        result["size_bytes"] = size_bytes
        result["size_human"] = _human_size(size_bytes)
    else:
        result["size_hint"] = entry.get("size_hint", "unknown")
    return result


def _validate_label_file(models_dir: Path, entry: dict) -> dict:
    """Check if a label JSON file exists and contains valid data."""
    result = _check_file(models_dir, entry)
    if not result["exists"]:
        return result

    filepath = models_dir / entry["path"]
    try:
        with open(filepath) as f:
            data = json.load(f)
        if not isinstance(data, list):
            result["valid"] = False
            result["error"] = "File does not contain a JSON array"
        elif not all(isinstance(item, str) for item in data):
            result["valid"] = False
            result["error"] = "Array contains non-string elements"
        elif len(data) == 0:
            result["valid"] = False
            result["error"] = "Array is empty"
        else:
            result["valid"] = True
            result["label_count"] = len(data)
    except json.JSONDecodeError as e:
        result["valid"] = False
        result["error"] = f"Invalid JSON: {e}"
    except OSError as e:
        result["valid"] = False
        result["error"] = f"Read error: {e}"

    return result


def _human_size(size_bytes: int) -> str:
    """Convert bytes to human-readable size string."""
    for unit in ("B", "KB", "MB", "GB"):
        if abs(size_bytes) < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def verify(models_dir: Path | None = None, quiet: bool = False) -> bool:
    """Verify all required model and label files.

    Args:
        models_dir: Path to the models directory. Defaults to ai/models/.
        quiet: If True, suppress all output. Only the return value matters.

    Returns:
        True if all required files are present and valid, False otherwise.
    """
    if models_dir is None:
        models_dir = MODELS_DIR

    all_ok = True
    missing_models = []
    missing_labels = []
    invalid_labels = []
    present_models = []
    present_labels = []
    missing_engines = []
    present_engines = []

    # Check required ONNX models
    for entry in REQUIRED_MODELS:
        result = _check_file(models_dir, entry)
        if result["exists"]:
            present_models.append(result)
        else:
            missing_models.append(result)
            all_ok = False

    # Check label files
    for entry in REQUIRED_LABELS:
        result = _validate_label_file(models_dir, entry)
        if not result["exists"]:
            missing_labels.append(result)
            all_ok = False
        elif not result.get("valid", True):
            invalid_labels.append(result)
            all_ok = False
        else:
            present_labels.append(result)

    # Check optional TensorRT engines (informational only, don't affect exit code)
    for entry in OPTIONAL_ENGINES:
        result = _check_file(models_dir, entry)
        if result["exists"]:
            present_engines.append(result)
        else:
            missing_engines.append(result)

    if quiet:
        return all_ok

    # Print report
    print("=" * 60)
    print("  RepoScan Pro - Model Verification Report")
    print("=" * 60)
    print(f"\nModels directory: {models_dir}")
    print()

    # Present ONNX models
    if present_models:
        print("ONNX Models (found):")
        for r in present_models:
            print(f"  [OK]  {r['path']}  ({r['size_human']})")

    # Missing ONNX models
    if missing_models:
        print("\nONNX Models (MISSING):")
        for r in missing_models:
            print(f"  [!!]  {r['path']}")
            print(f"        {r['description']}")
            print(f"        Expected size: {r.get('size_hint', 'unknown')}")
            print(f"        How to obtain: {r['obtain']}")

    print()

    # Present label files
    if present_labels:
        print("Label Files (found):")
        for r in present_labels:
            count = r.get("label_count", "?")
            print(f"  [OK]  {r['path']}  ({count} labels, {r['size_human']})")

    # Missing label files
    if missing_labels:
        print("\nLabel Files (MISSING):")
        for r in missing_labels:
            print(f"  [!!]  {r['path']}")
            print(f"        {r['description']}")
            print(f"        How to obtain: {r['obtain']}")

    # Invalid label files
    if invalid_labels:
        print("\nLabel Files (INVALID):")
        for r in invalid_labels:
            print(f"  [!!]  {r['path']}")
            print(f"        Error: {r.get('error', 'unknown')}")

    print()

    # TensorRT engines (informational)
    if present_engines:
        print("TensorRT Engines (found):")
        for r in present_engines:
            print(f"  [OK]  {r['path']}  ({r['size_human']})")

    if missing_engines:
        print("\nTensorRT Engines (not built yet):")
        for r in missing_engines:
            print(f"  [--]  {r['path']}")
            print(f"        {r['description']}")
            print(f"        {r['obtain']}")

    # Summary
    print()
    print("-" * 60)
    total_required = len(REQUIRED_MODELS) + len(REQUIRED_LABELS)
    total_present = len(present_models) + len(present_labels)
    total_missing = len(missing_models) + len(missing_labels) + len(invalid_labels)

    if all_ok:
        print(f"  All {total_required} required files present and valid.")
        if missing_engines:
            print(f"  {len(missing_engines)} TensorRT engine(s) not yet built (built at runtime).")
        print("\n  Status: READY")
    else:
        print(f"  {total_present}/{total_required} required files present.")
        print(f"  {total_missing} file(s) missing or invalid.")
        print("\n  Status: NOT READY")
        print("\n  Quick fix — download all models and labels:")
        print("    ./ai/download_models.sh")

    print("-" * 60)
    return all_ok


def main():
    parser = argparse.ArgumentParser(
        description="Verify RepoScan Pro AI model files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Exit codes:\n"
            "  0  All required model and label files are present\n"
            "  1  One or more required files are missing or invalid"
        ),
    )
    parser.add_argument(
        "--models-dir",
        type=Path,
        default=None,
        help=f"Path to models directory (default: {MODELS_DIR})",
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Suppress output; exit code only (0=ok, 1=missing)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output results as JSON",
    )
    args = parser.parse_args()

    models_dir = args.models_dir or MODELS_DIR

    if args.json_output:
        results = {
            "models_dir": str(models_dir),
            "models": [],
            "labels": [],
            "engines": [],
        }
        for entry in REQUIRED_MODELS:
            results["models"].append(_check_file(models_dir, entry))
        for entry in REQUIRED_LABELS:
            results["labels"].append(_validate_label_file(models_dir, entry))
        for entry in OPTIONAL_ENGINES:
            results["engines"].append(_check_file(models_dir, entry))

        all_ok = (
            all(r["exists"] for r in results["models"])
            and all(r["exists"] and r.get("valid", True) for r in results["labels"])
        )
        results["all_ok"] = all_ok
        json.dump(results, sys.stdout, indent=2)
        print()
        sys.exit(0 if all_ok else 1)

    ok = verify(models_dir=models_dir, quiet=args.quiet)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
