#!/usr/bin/env python3
"""
Download pretrained models for Seen-It-First Phase 1.

Downloads source pretrained artifacts to models/raw/:
  yolov8n.pt          — vehicle detection (COCO pretrained)
  yolov8n_lp.pt       — license plate detection (US-plate pretrained)
  yolov8n-cls.pt      — vehicle classification (ImageNet pretrained)
  en_PP-OCRv4_rec_infer/  — PaddleOCR English recognition model

Run once before build_tensorrt_engines.py, which exports runtime ONNX assets
to models/onnx and TensorRT engines to models/<module>/.

Phase 1: ONLY pretrained models. No training, no datasets.

Usage:
    python scripts/download_models.py
    python scripts/download_models.py --skip vehicle    # skip specific model
    python scripts/download_models.py --model ocr       # download one model
"""

import argparse
import logging
import os
import shutil
import sys
import tarfile
import urllib.request
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent
MODELS_RAW = REPO_ROOT / "models" / "raw"

# ---------------------------------------------------------------------------
# Model specs
# ---------------------------------------------------------------------------

# YOLOv8 models via ultralytics (downloaded by model name; ultralytics caches
# them in ~/.config/Ultralytics/ then we copy to models/raw/).
YOLO_MODELS = {
    "vehicle": {
        "model_name": "yolov8n.pt",
        "dest": MODELS_RAW / "yolov8n.pt",
        "description": "YOLOv8n COCO pretrained — vehicle detection",
    },
    "plate": {
        # keremberke/yolov8-license-plate-detection via ultralytics Hub
        "model_name": "keremberke/yolov8-license-plate-detection:best.pt",
        "dest": MODELS_RAW / "yolov8n_lp.pt",
        "description": "YOLOv8n LP detection — US license plate pretrained",
    },
    "classifier": {
        "model_name": "yolov8n-cls.pt",
        "dest": MODELS_RAW / "yolov8n-cls.pt",
        "description": "YOLOv8n-cls ImageNet pretrained — vehicle classification",
    },
}

# PaddleOCR PP-OCRv4 English recognition model (direct download)
PADDLE_OCR_SPEC = {
    "url": (
        "https://paddleocr.bj.bcebos.com/PP-OCRv4/english/"
        "en_PP-OCRv4_rec_infer.tar"
    ),
    "tar_name": "en_PP-OCRv4_rec_infer.tar",
    "extract_dir": "en_PP-OCRv4_rec_infer",
    "description": "PaddleOCR PP-OCRv4 English recognition model",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _progress_hook(block_num: int, block_size: int, total_size: int):
    downloaded = block_num * block_size
    if total_size > 0:
        pct = min(100, downloaded * 100 // total_size)
        mb = downloaded / (1024 * 1024)
        print(f"\r  {pct:3d}%  {mb:.1f} MB", end="", flush=True)


def download_url(url: str, dest: Path) -> bool:
    """Download url to dest with a progress bar. Returns True on success."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    try:
        logger.info("Downloading: %s", url)
        urllib.request.urlretrieve(url, tmp, reporthook=_progress_hook)
        print()  # newline after progress
        tmp.rename(dest)
        return True
    except Exception as exc:
        logger.error("Download failed: %s", exc)
        if tmp.exists():
            tmp.unlink()
        return False


def download_yolo_model(spec: dict) -> bool:
    """Download a YOLOv8 model via the ultralytics library."""
    dest: Path = spec["dest"]
    if dest.exists():
        logger.info("Already present: %s", dest.name)
        return True

    try:
        from ultralytics import YOLO
    except ImportError:
        logger.error(
            "ultralytics not installed. Run: pip install ultralytics"
        )
        return False

    dest.parent.mkdir(parents=True, exist_ok=True)
    model_name = spec["model_name"]
    logger.info("Fetching via ultralytics: %s", model_name)

    try:
        model = YOLO(model_name)
        # ultralytics downloads to ~/.config/Ultralytics/<name>
        # The YOLO object gives us the path
        src_path = Path(model.ckpt_path) if hasattr(model, "ckpt_path") else None
        if src_path is None or not src_path.exists():
            # Fallback: check common cache locations
            import torch
            cache = Path(torch.hub.get_dir()) / "ultralytics" / model_name
            if not cache.exists():
                # Last resort: just copy the model file if accessible
                logger.warning(
                    "Could not locate downloaded .pt; model may already be "
                    "in ultralytics cache."
                )
                # Save directly using ultralytics export path
                src_path = Path(model_name)

        if src_path and src_path.exists() and src_path != dest:
            shutil.copy2(src_path, dest)
            logger.info("Saved: %s", dest)
        else:
            # ultralytics may have saved to cwd
            cwd_file = Path(model_name.split(":")[-1])
            if cwd_file.exists():
                shutil.copy2(cwd_file, dest)
                logger.info("Saved: %s", dest)
            else:
                logger.warning(
                    "Model loaded but .pt not found at expected path. "
                    "Check %s manually.", dest.parent
                )
        return True
    except Exception as exc:
        logger.error("Failed to download %s: %s", model_name, exc)
        return False


def download_paddleocr_model() -> bool:
    """Download PaddleOCR PP-OCRv4 English recognition model."""
    extract_dir = MODELS_RAW / PADDLE_OCR_SPEC["extract_dir"]
    if extract_dir.exists():
        logger.info("Already present: %s/", extract_dir.name)
        return True

    tar_dest = MODELS_RAW / PADDLE_OCR_SPEC["tar_name"]
    if not tar_dest.exists():
        ok = download_url(PADDLE_OCR_SPEC["url"], tar_dest)
        if not ok:
            return False

    logger.info("Extracting: %s", tar_dest.name)
    try:
        with tarfile.open(tar_dest, "r") as tf:
            tf.extractall(MODELS_RAW)
        tar_dest.unlink()  # remove archive after extraction
        logger.info("Extracted to: %s/", extract_dir.name)
        return True
    except Exception as exc:
        logger.error("Extraction failed: %s", exc)
        return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download Phase 1 pretrained models to models/raw/"
    )
    parser.add_argument(
        "--model",
        choices=["vehicle", "plate", "classifier", "ocr", "all"],
        default="all",
        help="Download a specific model group (default: all)",
    )
    parser.add_argument(
        "--skip",
        nargs="+",
        choices=["vehicle", "plate", "classifier", "ocr"],
        default=[],
        help="Skip one or more model groups",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    MODELS_RAW.mkdir(parents=True, exist_ok=True)

    targets = (
        list(YOLO_MODELS.keys()) + ["ocr"]
        if args.model == "all"
        else [args.model]
    )
    targets = [t for t in targets if t not in args.skip]

    results: dict[str, bool] = {}

    for target in targets:
        if target in YOLO_MODELS:
            spec = YOLO_MODELS[target]
            logger.info("--- %s: %s", target, spec["description"])
            results[target] = download_yolo_model(spec)
        elif target == "ocr":
            logger.info("--- ocr: %s", PADDLE_OCR_SPEC["description"])
            results["ocr"] = download_paddleocr_model()

    print()
    print("=" * 50)
    print("Download summary")
    print("=" * 50)
    for name, ok in results.items():
        status = "OK" if ok else "FAILED"
        print(f"  {name:<15} {status}")

    failed = [k for k, v in results.items() if not v]
    if failed:
        print(f"\nFailed: {failed}")
        print("Run build_tensorrt_engines.py only after all downloads succeed.")
        sys.exit(1)
    else:
        print("\nAll models downloaded. Next: python scripts/build_tensorrt_engines.py")


if __name__ == "__main__":
    main()
