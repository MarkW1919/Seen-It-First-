"""
Plate detector fine-tuning helpers for Phase 3.

This module keeps training isolated from runtime inference code while
installing trained artifacts into the existing runtime slots expected by
scripts/build_tensorrt_engines.py.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

from edge.ai_training_phase3.dataset_manifest import (
    build_yolo_detection_manifest,
    has_errors,
    write_manifest,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
RUNTIME_PLATE_CHECKPOINT = REPO_ROOT / "models" / "raw" / "yolov8n_lp.pt"
BUILD_SCRIPT = REPO_ROOT / "scripts" / "build_tensorrt_engines.py"


@dataclass
class PlateTrainingConfig:
    dataset_root: Path
    workspace_dir: Path
    project_dir: Path
    run_name: str = "plate_detector"
    base_model: str = "yolov8s.pt"
    epochs: int = 100
    imgsz: int = 640
    batch: int = 16
    device: str = "0"
    workers: int = 4
    patience: int = 20
    cache: bool = False
    amp: bool = True
    class_names: tuple[str, ...] = ("plate",)


def prepare_plate_training_workspace(config: PlateTrainingConfig) -> dict[str, Path]:
    """Validate the dataset and write the YOLO dataset YAML plus manifest."""
    dataset_root = Path(config.dataset_root).resolve()
    workspace_dir = Path(config.workspace_dir).resolve()
    workspace_dir.mkdir(parents=True, exist_ok=True)

    manifest = build_yolo_detection_manifest(
        dataset_root=dataset_root,
        class_count=len(config.class_names),
    )
    manifest_path = workspace_dir / "plate_dataset_manifest.json"
    write_manifest(manifest, manifest_path)
    if has_errors(manifest):
        raise ValueError(f"Plate dataset validation failed: {manifest_path}")

    dataset_yaml = workspace_dir / "plate_dataset.yaml"
    dataset_yaml.write_text(
        yaml.safe_dump(
            {
                "path": str(dataset_root),
                "train": "images/train",
                "val": "images/val",
                "test": "images/test",
                "names": list(config.class_names),
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    return {
        "dataset_yaml": dataset_yaml,
        "manifest_path": manifest_path,
    }


def train_plate_detector(config: PlateTrainingConfig) -> dict[str, Path]:
    """Run Ultralytics training and return the best checkpoint path."""
    prepared = prepare_plate_training_workspace(config)

    try:
        from ultralytics import YOLO
    except ImportError as exc:
        raise RuntimeError(
            "ultralytics is required for plate detector training. "
            "Install it in the training environment first."
        ) from exc

    model = YOLO(config.base_model)
    model.train(
        data=str(prepared["dataset_yaml"]),
        project=str(Path(config.project_dir).resolve()),
        name=config.run_name,
        epochs=config.epochs,
        imgsz=config.imgsz,
        batch=config.batch,
        device=config.device,
        workers=config.workers,
        patience=config.patience,
        cache=config.cache,
        amp=config.amp,
        pretrained=True,
        exist_ok=True,
    )

    save_dir = Path(getattr(model.trainer, "save_dir", Path(config.project_dir) / config.run_name))
    best_path = save_dir / "weights" / "best.pt"
    if not best_path.exists():
        raise FileNotFoundError(f"Training completed without best.pt at {best_path}")

    return {
        **prepared,
        "run_dir": save_dir,
        "checkpoint_path": best_path,
    }


def install_runtime_plate_checkpoint(
    checkpoint_path: str | Path,
    runtime_path: str | Path = RUNTIME_PLATE_CHECKPOINT,
) -> Path:
    """Copy the trained checkpoint into the existing runtime raw-model slot."""
    source = Path(checkpoint_path).resolve()
    target = Path(runtime_path).resolve()
    if not source.exists():
        raise FileNotFoundError(f"Checkpoint not found: {source}")

    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    return target


def build_runtime_plate_engine(
    python_executable: str = sys.executable,
    precision: str = "fp16",
) -> int:
    """Invoke the existing runtime engine build flow for the plate slot."""
    command = [
        python_executable,
        str(BUILD_SCRIPT),
        "--model",
        "plate",
        "--precision",
        precision,
    ]
    result = subprocess.run(command, cwd=REPO_ROOT, check=False)
    return result.returncode
