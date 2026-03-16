#!/usr/bin/env python3
"""Train and optionally install a fine-tuned plate detector into runtime slots."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from edge.ai_training_phase3.plate_training import (
    PlateTrainingConfig,
    build_runtime_plate_engine,
    install_runtime_plate_checkpoint,
    prepare_plate_training_workspace,
    train_plate_detector,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fine-tune the Phase 3 plate detector and install it into the current runtime layout."
    )
    parser.add_argument("--dataset-root", type=Path, required=True, help="YOLO dataset root.")
    parser.add_argument(
        "--workspace-dir",
        type=Path,
        default=REPO_ROOT / "data" / "training" / "plate_detector",
        help="Workspace for manifests and dataset YAML.",
    )
    parser.add_argument(
        "--project-dir",
        type=Path,
        default=REPO_ROOT / "runs" / "phase3",
        help="Ultralytics project directory.",
    )
    parser.add_argument("--run-name", default="plate_detector", help="Ultralytics run name.")
    parser.add_argument(
        "--base-model",
        default="yolov8s.pt",
        help="Base Ultralytics checkpoint. Default stays within Jetson GPU budget.",
    )
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=16)
    parser.add_argument("--device", default="0")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--patience", type=int, default=20)
    parser.add_argument("--precision", choices=["fp16", "fp32"], default="fp16")
    parser.add_argument(
        "--prepare-only",
        action="store_true",
        help="Only validate and write training workspace files.",
    )
    parser.add_argument(
        "--install-runtime-slot",
        action="store_true",
        help="Copy the trained best.pt into models/raw/yolov8n_lp.pt after training.",
    )
    parser.add_argument(
        "--build-runtime-engine",
        action="store_true",
        help="Build models/plate/plate.engine after installing the runtime slot.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = PlateTrainingConfig(
        dataset_root=args.dataset_root,
        workspace_dir=args.workspace_dir,
        project_dir=args.project_dir,
        run_name=args.run_name,
        base_model=args.base_model,
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        device=args.device,
        workers=args.workers,
        patience=args.patience,
    )

    prepared = prepare_plate_training_workspace(config)
    print(f"Dataset manifest: {prepared['manifest_path']}")
    print(f"Dataset YAML: {prepared['dataset_yaml']}")

    if args.prepare_only:
        print("Preparation complete. Training was not started.")
        return 0

    result = train_plate_detector(config)
    print(f"Training run dir: {result['run_dir']}")
    print(f"Best checkpoint: {result['checkpoint_path']}")

    if args.install_runtime_slot:
        installed = install_runtime_plate_checkpoint(result["checkpoint_path"])
        print(f"Installed runtime checkpoint: {installed}")

        if args.build_runtime_engine:
            rc = build_runtime_plate_engine(precision=args.precision)
            if rc != 0:
                return rc

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
