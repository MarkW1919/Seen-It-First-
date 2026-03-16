"""
OCR fine-tuning helpers for Phase 3.

This module prepares a PaddleOCR recognition workspace with a restricted
US-plate character dictionary and can install the exported inference model into
the existing runtime slot expected by scripts/build_tensorrt_engines.py.
"""

from __future__ import annotations

import csv
import random
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from edge.ai_training_phase3.dataset_manifest import (
    DEFAULT_PLATE_REGEX,
    build_ocr_recognition_manifest,
    has_errors,
    write_manifest,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
RUNTIME_OCR_EXPORT_DIR = REPO_ROOT / "models" / "raw" / "en_PP-OCRv4_rec_infer"
BUILD_SCRIPT = REPO_ROOT / "scripts" / "build_tensorrt_engines.py"
US_PLATE_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"


@dataclass
class OCRTrainingConfig:
    dataset_root: Path
    workspace_dir: Path
    paddleocr_root: Path
    config_path: Path
    pretrained_model: str | None = None
    labels_csv: Path | None = None
    plate_regex: str = DEFAULT_PLATE_REGEX
    train_ratio: float = 0.8
    val_ratio: float = 0.1
    seed: int = 42
    use_gpu: bool = True
    epoch_num: int | None = None
    train_batch_size: int | None = None
    eval_batch_size: int | None = None


def _resolve_ocr_image(images_root: Path, filename: str, split: str) -> Path | None:
    candidates = [images_root / split / filename, images_root / filename]
    return next((path for path in candidates if path.exists()), None)


def _partition_unspecified_rows(
    rows: list[tuple[str, str]],
    train_ratio: float,
    val_ratio: float,
    seed: int,
) -> dict[str, list[tuple[str, str]]]:
    rng = random.Random(seed)
    shuffled = list(rows)
    rng.shuffle(shuffled)

    total = len(shuffled)
    train_count = int(total * train_ratio)
    val_count = int(total * val_ratio)
    if total >= 3 and train_count == 0:
        train_count = 1
    if total >= 3 and val_count == 0:
        val_count = 1
    if train_count + val_count > total:
        val_count = max(0, total - train_count)

    return {
        "train": shuffled[:train_count],
        "val": shuffled[train_count : train_count + val_count],
        "test": shuffled[train_count + val_count :],
    }


def find_paddleocr_config(paddleocr_root: str | Path) -> Path:
    """Locate a likely English recognition config in a PaddleOCR checkout."""
    root = Path(paddleocr_root).resolve()
    candidates = [
        root / "configs" / "rec" / "PP-OCRv4" / "en_PP-OCRv4_rec.yml",
        root / "configs" / "rec" / "PP-OCRv3" / "en_PP-OCRv3_rec.yml",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        f"Could not find an English recognition config under {root / 'configs' / 'rec'}"
    )


def find_paddleocr_pretrained_model(paddleocr_root: str | Path) -> str | None:
    """Locate a likely English pretrained recognition checkpoint prefix."""
    root = Path(paddleocr_root).resolve()
    candidates = [
        root / "pretrain_models" / "en_PP-OCRv4_rec_train" / "best_accuracy",
        root / "pretrain_models" / "en_PP-OCRv3_rec_train" / "best_accuracy",
    ]
    for candidate in candidates:
        if candidate.with_suffix(".pdparams").exists() or candidate.exists():
            return candidate.as_posix()
    return None


def prepare_ocr_training_workspace(config: OCRTrainingConfig) -> dict[str, Path]:
    """Validate OCR data and write PaddleOCR train/val/test lists plus char dict."""
    dataset_root = Path(config.dataset_root).resolve()
    workspace_dir = Path(config.workspace_dir).resolve()
    workspace_dir.mkdir(parents=True, exist_ok=True)

    manifest = build_ocr_recognition_manifest(
        dataset_root=dataset_root,
        labels_csv=config.labels_csv,
        plate_regex=config.plate_regex,
    )
    manifest_path = workspace_dir / "ocr_dataset_manifest.json"
    write_manifest(manifest, manifest_path)
    if has_errors(manifest):
        raise ValueError(f"OCR dataset validation failed: {manifest_path}")

    labels_csv = Path(config.labels_csv).resolve() if config.labels_csv else dataset_root / "labels.csv"
    images_root = dataset_root / "images"

    explicit: dict[str, list[tuple[str, str]]] = {"train": [], "val": [], "test": []}
    unspecified: list[tuple[str, str]] = []

    with labels_csv.open("r", encoding="utf-8", newline="") as file_obj:
        reader = csv.DictReader(file_obj)
        for row in reader:
            filename = str(row.get("filename", "")).strip()
            text = str(row.get("text", "")).strip().upper()
            split = str(row.get("split", "")).strip().lower() or "unspecified"

            resolved = _resolve_ocr_image(images_root, filename, split)
            if resolved is None:
                resolved = _resolve_ocr_image(images_root, filename, "unspecified")
            if resolved is None:
                continue

            rel_path = resolved.relative_to(images_root).as_posix()
            sample = (rel_path, text)
            if split in explicit:
                explicit[split].append(sample)
            else:
                unspecified.append(sample)

    auto_splits = _partition_unspecified_rows(
        unspecified,
        train_ratio=config.train_ratio,
        val_ratio=config.val_ratio,
        seed=config.seed,
    )
    for split_name in explicit:
        explicit[split_name].extend(auto_splits[split_name])

    images_workspace = workspace_dir / "images"
    if images_workspace.exists():
        shutil.rmtree(images_workspace)
    shutil.copytree(images_root, images_workspace)

    list_paths: dict[str, Path] = {}
    for split_name in ("train", "val", "test"):
        list_path = workspace_dir / f"{split_name}_list.txt"
        list_paths[split_name] = list_path
        lines = [f"{rel_path}\t{text}" for rel_path, text in explicit[split_name]]
        list_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")

    dict_path = workspace_dir / "us_plate_dict.txt"
    dict_path.write_text("\n".join(US_PLATE_CHARS) + "\n", encoding="utf-8")

    return {
        "manifest_path": manifest_path,
        "images_dir": images_workspace,
        "train_list": list_paths["train"],
        "val_list": list_paths["val"],
        "test_list": list_paths["test"],
        "char_dict_path": dict_path,
    }


def build_paddleocr_train_command(
    config: OCRTrainingConfig,
    prepared: dict[str, Path],
    python_executable: str = sys.executable,
) -> list[str]:
    """Build the official PaddleOCR training command."""
    command = [
        python_executable,
        "tools/train.py",
        "-c",
        str(Path(config.config_path).resolve()),
        "-o",
        f"Global.save_model_dir={(Path(config.workspace_dir).resolve() / 'output').as_posix()}",
        f"Global.character_dict_path={prepared['char_dict_path'].as_posix()}",
        "Global.use_space_char=False",
        f"Global.use_gpu={'True' if config.use_gpu else 'False'}",
        f"Train.dataset.data_dir={prepared['images_dir'].as_posix()}",
        f"Train.dataset.label_file_list=[\"{prepared['train_list'].as_posix()}\"]",
        f"Eval.dataset.data_dir={prepared['images_dir'].as_posix()}",
        f"Eval.dataset.label_file_list=[\"{prepared['val_list'].as_posix()}\"]",
    ]

    if config.pretrained_model:
        command.append(f"Global.pretrained_model={config.pretrained_model}")
    if config.epoch_num is not None:
        command.append(f"Global.epoch_num={config.epoch_num}")
    if config.train_batch_size is not None:
        command.append(f"Train.loader.batch_size_per_card={config.train_batch_size}")
    if config.eval_batch_size is not None:
        command.append(f"Eval.loader.batch_size_per_card={config.eval_batch_size}")

    return command


def build_paddleocr_export_command(
    config: OCRTrainingConfig,
    prepared: dict[str, Path],
    checkpoint_prefix: str | Path,
    save_inference_dir: str | Path,
    python_executable: str = sys.executable,
) -> list[str]:
    """Build the official PaddleOCR export command."""
    return [
        python_executable,
        "tools/export_model.py",
        "-c",
        str(Path(config.config_path).resolve()),
        "-o",
        f"Global.pretrained_model={Path(checkpoint_prefix).as_posix()}",
        f"Global.save_inference_dir={Path(save_inference_dir).resolve().as_posix()}",
        f"Global.character_dict_path={prepared['char_dict_path'].as_posix()}",
        "Global.use_space_char=False",
        f"Global.use_gpu={'True' if config.use_gpu else 'False'}",
    ]


def install_runtime_ocr_export(
    export_dir: str | Path,
    runtime_dir: str | Path = RUNTIME_OCR_EXPORT_DIR,
) -> Path:
    """Copy the exported PaddleOCR inference model into the runtime raw slot."""
    source = Path(export_dir).resolve()
    target = Path(runtime_dir).resolve()
    if not source.exists():
        raise FileNotFoundError(f"OCR export directory not found: {source}")

    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target)
    return target


def build_runtime_ocr_engine(
    python_executable: str = sys.executable,
    precision: str = "fp16",
) -> int:
    """Invoke the existing runtime engine build flow for the OCR slot."""
    command = [
        python_executable,
        str(BUILD_SCRIPT),
        "--model",
        "ocr",
        "--precision",
        precision,
    ]
    result = subprocess.run(command, cwd=REPO_ROOT, check=False)
    return result.returncode
