#!/usr/bin/env python3
"""Prepare and run Phase 3 OCR fine-tuning against a PaddleOCR checkout."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fine-tune the OCR recognizer with PaddleOCR and install it into the current runtime layout."
    )
    parser.add_argument("--dataset-root", type=Path, required=True, help="OCR dataset root.")
    parser.add_argument(
        "--workspace-dir",
        type=Path,
        default=REPO_ROOT / "data" / "training" / "ocr_recognizer",
        help="Workspace for manifests, list files, and export outputs.",
    )
    parser.add_argument(
        "--paddleocr-root",
        type=Path,
        required=True,
        help="Path to a PaddleOCR source checkout.",
    )
    parser.add_argument(
        "--config-path",
        type=Path,
        default=None,
        help="Optional PaddleOCR recognition config. Auto-detected when omitted.",
    )
    parser.add_argument(
        "--pretrained-model",
        default=None,
        help="Optional PaddleOCR checkpoint prefix for fine-tuning. Auto-detected when omitted.",
    )
    parser.add_argument("--labels-csv", type=Path, default=None)
    parser.add_argument("--train-ratio", type=float, default=0.8)
    parser.add_argument("--val-ratio", type=float, default=0.1)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--epoch-num", type=int, default=None)
    parser.add_argument("--train-batch-size", type=int, default=None)
    parser.add_argument("--eval-batch-size", type=int, default=None)
    parser.add_argument("--precision", choices=["fp16", "fp32"], default="fp16")
    parser.add_argument(
        "--prepare-only",
        action="store_true",
        help="Only prepare manifests, list files, and char dictionary.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print PaddleOCR train/export commands without executing them.",
    )
    parser.add_argument(
        "--install-runtime-slot",
        action="store_true",
        help="Copy the exported inference model into models/raw/en_PP-OCRv4_rec_infer.",
    )
    parser.add_argument(
        "--build-runtime-engine",
        action="store_true",
        help="Build models/ocr/ocr.engine after installing the runtime slot.",
    )
    return parser.parse_args()


def _run_command(command: list[str], cwd: Path) -> int:
    print(subprocess.list2cmdline(command))
    result = subprocess.run(command, cwd=cwd, check=False)
    return result.returncode


def main() -> int:
    args = parse_args()
    config_path = args.config_path or find_paddleocr_config(args.paddleocr_root)
    pretrained_model = args.pretrained_model or find_paddleocr_pretrained_model(args.paddleocr_root)

    config = OCRTrainingConfig(
        dataset_root=args.dataset_root,
        workspace_dir=args.workspace_dir,
        paddleocr_root=args.paddleocr_root,
        config_path=config_path,
        pretrained_model=pretrained_model,
        labels_csv=args.labels_csv,
        train_ratio=args.train_ratio,
        val_ratio=args.val_ratio,
        seed=args.seed,
        epoch_num=args.epoch_num,
        train_batch_size=args.train_batch_size,
        eval_batch_size=args.eval_batch_size,
    )

    prepared = prepare_ocr_training_workspace(config)
    print(f"Dataset manifest: {prepared['manifest_path']}")
    print(f"Train list: {prepared['train_list']}")
    print(f"Val list: {prepared['val_list']}")
    print(f"Char dict: {prepared['char_dict_path']}")

    if args.prepare_only:
        print("Preparation complete. Training was not started.")
        return 0

    train_command = build_paddleocr_train_command(config, prepared)
    output_dir = Path(config.workspace_dir).resolve() / "output"
    checkpoint_prefix = output_dir / "best_accuracy"
    export_dir = Path(config.workspace_dir).resolve() / "inference_export"
    export_command = build_paddleocr_export_command(
        config,
        prepared,
        checkpoint_prefix=checkpoint_prefix,
        save_inference_dir=export_dir,
    )

    if args.dry_run:
        print("Train command:")
        print(subprocess.list2cmdline(train_command))
        print("Export command:")
        print(subprocess.list2cmdline(export_command))
        return 0

    rc = _run_command(train_command, cwd=Path(args.paddleocr_root).resolve())
    if rc != 0:
        return rc

    rc = _run_command(export_command, cwd=Path(args.paddleocr_root).resolve())
    if rc != 0:
        return rc

    if args.install_runtime_slot:
        installed = install_runtime_ocr_export(export_dir)
        print(f"Installed runtime OCR export: {installed}")

        if args.build_runtime_engine:
            rc = build_runtime_ocr_engine(precision=args.precision)
            if rc != 0:
                return rc

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
