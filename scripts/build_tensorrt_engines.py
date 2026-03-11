#!/usr/bin/env python3
"""
Build TensorRT engines from pretrained models.

Pipeline per model:
    .pt  →  ONNX  →  TensorRT .engine

Output locations:
    models/vehicle/vehicle.engine   (YOLOv8n, FP16)
    models/plate/plate.engine       (YOLOv8n-LP, FP16)
    models/classifier/classifier.engine  (YOLOv8n-cls, FP16)
    models/ocr/ocr.engine           (PaddleOCR PP-OCRv4 rec, FP16)
    models/onnx/*.onnx              (runtime ONNX assets)

Requires:
    ultralytics      — YOLOv8 ONNX export
    paddle2onnx      — PaddleOCR → ONNX conversion
    tensorrt         — engine builder
    pycuda           — GPU access

Run download_models.py first.

Usage:
    python scripts/build_tensorrt_engines.py
    python scripts/build_tensorrt_engines.py --model vehicle
    python scripts/build_tensorrt_engines.py --precision fp32
"""

import argparse
import logging
import subprocess
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent
MODELS_RAW = REPO_ROOT / "models" / "raw"
MODELS_ONNX = REPO_ROOT / "models" / "onnx"

# Final engine output paths (must match system.yaml)
ENGINE_PATHS = {
    "vehicle":    REPO_ROOT / "models" / "vehicle" / "vehicle.engine",
    "plate":      REPO_ROOT / "models" / "plate" / "plate.engine",
    "classifier": REPO_ROOT / "models" / "classifier" / "classifier.engine",
    "ocr":        REPO_ROOT / "models" / "ocr" / "ocr.engine",
}

# ONNX intermediate paths
ONNX_PATHS = {
    "vehicle":    MODELS_ONNX / "vehicle.onnx",
    "plate":      MODELS_ONNX / "plate.onnx",
    "classifier": MODELS_ONNX / "classifier.onnx",
    "ocr":        MODELS_ONNX / "ocr.onnx",
}

# Input shapes for static TRT optimization profiles (N, C, H, W)
INPUT_SHAPES = {
    "vehicle":    (1, 3, 640, 640),
    "plate":      (1, 3, 640, 640),
    "classifier": (1, 3, 224, 224),
    "ocr":        (1, 3, 48, 320),    # PP-OCRv4 rec: H=48, W=320 (fixed for plates)
}


# ---------------------------------------------------------------------------
# ONNX export: YOLOv8 (.pt → .onnx)
# ---------------------------------------------------------------------------

def export_yolo_to_onnx(model_key: str, pt_path: Path, onnx_path: Path) -> bool:
    """Export a YOLOv8 .pt to ONNX using ultralytics."""
    if onnx_path.exists():
        logger.info("ONNX cache hit: %s", onnx_path.name)
        return True

    try:
        from ultralytics import YOLO
    except ImportError:
        logger.error("ultralytics not installed: pip install ultralytics")
        return False

    if not pt_path.exists():
        logger.error("Source .pt not found: %s", pt_path)
        logger.error("Run download_models.py first.")
        return False

    logger.info("Exporting %s → ONNX: %s", pt_path.name, onnx_path.name)
    onnx_path.parent.mkdir(parents=True, exist_ok=True)

    _, _, h, w = INPUT_SHAPES[model_key]

    try:
        model = YOLO(str(pt_path))
        exported = model.export(
            format="onnx",
            imgsz=(h, w),
            simplify=True,
            dynamic=False,
            opset=17,
        )
        # ultralytics writes the ONNX next to the .pt by default
        exported_path = Path(exported)
        if exported_path != onnx_path:
            import shutil
            shutil.move(str(exported_path), str(onnx_path))
        logger.info("ONNX saved: %s", onnx_path)
        return True
    except Exception as exc:
        logger.error("ONNX export failed for %s: %s", pt_path.name, exc)
        return False


# ---------------------------------------------------------------------------
# ONNX export: PaddleOCR (.pdmodel → .onnx)
# ---------------------------------------------------------------------------

def export_paddle_to_onnx(paddle_dir: Path, onnx_path: Path) -> bool:
    """Convert PaddleOCR paddle inference model to ONNX via paddle2onnx."""
    if onnx_path.exists():
        logger.info("ONNX cache hit: %s", onnx_path.name)
        return True

    model_file = paddle_dir / "inference.pdmodel"
    params_file = paddle_dir / "inference.pdiparams"

    if not model_file.exists() or not params_file.exists():
        logger.error(
            "PaddleOCR inference model not found in: %s", paddle_dir
        )
        logger.error("Run download_models.py first.")
        return False

    try:
        import paddle2onnx  # noqa: F401
    except ImportError:
        logger.error(
            "paddle2onnx not installed: pip install paddle2onnx paddlepaddle"
        )
        return False

    onnx_path.parent.mkdir(parents=True, exist_ok=True)
    logger.info("Converting PaddleOCR → ONNX: %s", onnx_path.name)

    cmd = [
        sys.executable, "-m", "paddle2onnx",
        "--model_dir", str(paddle_dir),
        "--model_filename", "inference.pdmodel",
        "--params_filename", "inference.pdiparams",
        "--save_file", str(onnx_path),
        "--opset_version", "11",
        "--enable_onnx_checker", "True",
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        logger.info("paddle2onnx: %s", result.stdout.strip())
        logger.info("ONNX saved: %s", onnx_path)
        return True
    except subprocess.CalledProcessError as exc:
        logger.error("paddle2onnx failed:\n%s", exc.stderr)
        return False


# ---------------------------------------------------------------------------
# TensorRT engine build
# ---------------------------------------------------------------------------

def build_trt_engine(
    onnx_path: Path,
    engine_path: Path,
    precision: str,
    input_shape: tuple,
) -> bool:
    """Build a TensorRT engine from ONNX using ModelLoader."""
    # Import here so missing TRT gives a clear error at runtime
    sys.path.insert(0, str(REPO_ROOT))
    from edge.inference.model_loader import ModelLoader

    loader = ModelLoader(workspace_gb=2.0)
    return loader.load_or_build(
        onnx_path=onnx_path,
        engine_path=engine_path,
        precision=precision,
        input_shape=input_shape,
    )


# ---------------------------------------------------------------------------
# Per-model build functions
# ---------------------------------------------------------------------------

def build_vehicle(precision: str) -> bool:
    ok = export_yolo_to_onnx(
        "vehicle",
        MODELS_RAW / "yolov8n.pt",
        ONNX_PATHS["vehicle"],
    )
    if not ok:
        return False
    return build_trt_engine(
        ONNX_PATHS["vehicle"],
        ENGINE_PATHS["vehicle"],
        precision,
        INPUT_SHAPES["vehicle"],
    )


def build_plate(precision: str) -> bool:
    ok = export_yolo_to_onnx(
        "plate",
        MODELS_RAW / "yolov8n_lp.pt",
        ONNX_PATHS["plate"],
    )
    if not ok:
        return False
    return build_trt_engine(
        ONNX_PATHS["plate"],
        ENGINE_PATHS["plate"],
        precision,
        INPUT_SHAPES["plate"],
    )


def build_classifier(precision: str) -> bool:
    ok = export_yolo_to_onnx(
        "classifier",
        MODELS_RAW / "yolov8n-cls.pt",
        ONNX_PATHS["classifier"],
    )
    if not ok:
        return False
    return build_trt_engine(
        ONNX_PATHS["classifier"],
        ENGINE_PATHS["classifier"],
        precision,
        INPUT_SHAPES["classifier"],
    )


def build_ocr(precision: str) -> bool:
    paddle_dir = MODELS_RAW / "en_PP-OCRv4_rec_infer"
    ok = export_paddle_to_onnx(paddle_dir, ONNX_PATHS["ocr"])
    if not ok:
        return False
    return build_trt_engine(
        ONNX_PATHS["ocr"],
        ENGINE_PATHS["ocr"],
        precision,
        INPUT_SHAPES["ocr"],
    )


BUILD_FUNCS = {
    "vehicle":    build_vehicle,
    "plate":      build_plate,
    "classifier": build_classifier,
    "ocr":        build_ocr,
}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build TensorRT engines from pretrained models"
    )
    parser.add_argument(
        "--model",
        choices=["vehicle", "plate", "classifier", "ocr", "all"],
        default="all",
        help="Build a specific model (default: all)",
    )
    parser.add_argument(
        "--precision",
        choices=["fp32", "fp16"],
        default="fp16",
        help="TensorRT engine precision (default: fp16)",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    targets = list(BUILD_FUNCS.keys()) if args.model == "all" else [args.model]

    # Pre-flight: verify TRT and GPU
    sys.path.insert(0, str(REPO_ROOT))
    from edge.inference.model_loader import ModelLoader
    loader = ModelLoader()
    gpu = loader.verify_gpu()

    print("GPU info:")
    for k, v in gpu.items():
        print(f"  {k:<22} {v}")
    print()

    if not gpu["trt_available"]:
        logger.error(
            "TensorRT not available. Install JetPack or TensorRT SDK first."
        )
        sys.exit(1)

    results: dict[str, bool] = {}
    for target in targets:
        print(f"{'='*50}")
        print(f"Building: {target} ({args.precision.upper()})")
        print(f"{'='*50}")
        results[target] = BUILD_FUNCS[target](args.precision)

    print()
    print("=" * 50)
    print("Build summary")
    print("=" * 50)
    for name, ok in results.items():
        status = "OK" if ok else "FAILED"
        engine = ENGINE_PATHS[name]
        size = ""
        if engine.exists():
            size = f"  ({engine.stat().st_size / (1024*1024):.1f} MB)"
        print(f"  {name:<15} {status}{size}")

    failed = [k for k, v in results.items() if not v]
    if failed:
        logger.error("Failed models: %s", failed)
        sys.exit(1)
    else:
        print("\nAll engines built. Next: python scripts/test_pipeline.py")


if __name__ == "__main__":
    main()
