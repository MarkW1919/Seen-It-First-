"""
Dataset validation helpers for Phase 3 training work.

Supported layouts:

YOLO detection:
    dataset_root/
      images/{train,val,test}/*.{jpg,jpeg,png,bmp,webp}
      labels/{train,val,test}/*.txt

OCR recognition:
    dataset_root/
      images/<filename>
      images/<split>/<filename>         # optional split subdirs
      labels.csv                        # columns: filename,text[,split]
"""

from __future__ import annotations

import csv
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
DEFAULT_PLATE_REGEX = r"^[A-Z0-9]{2,8}$"


@dataclass
class DatasetIssue:
    level: str
    message: str


@dataclass
class SplitSummary:
    name: str
    image_count: int = 0
    label_count: int = 0
    paired_count: int = 0
    missing_labels: int = 0
    orphan_labels: int = 0
    invalid_label_files: int = 0
    annotation_count: int = 0


def _add_issue(issues: list[DatasetIssue], level: str, message: str) -> None:
    issues.append(DatasetIssue(level=level, message=message))


def _iter_files(path: Path, suffixes: Iterable[str]) -> dict[str, Path]:
    if not path.exists():
        return {}

    suffix_set = {suffix.lower() for suffix in suffixes}
    indexed: dict[str, Path] = {}
    for file_path in sorted(path.iterdir()):
        if not file_path.is_file():
            continue
        if file_path.suffix.lower() not in suffix_set:
            continue
        indexed[file_path.stem] = file_path
    return indexed


def _validate_yolo_label_file(path: Path, class_count: int | None) -> tuple[int, list[str]]:
    errors: list[str] = []
    annotation_count = 0

    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        return 0, [f"{path}: could not read label file ({exc})"]

    for line_number, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line:
            continue

        parts = line.split()
        if len(parts) != 5:
            errors.append(f"{path.name}:{line_number}: expected 5 columns, found {len(parts)}")
            continue

        try:
            class_id = int(parts[0])
            coords = [float(value) for value in parts[1:]]
        except ValueError:
            errors.append(f"{path.name}:{line_number}: non-numeric YOLO label value")
            continue

        if class_id < 0:
            errors.append(f"{path.name}:{line_number}: class id must be >= 0")
            continue
        if class_count is not None and class_id >= class_count:
            errors.append(
                f"{path.name}:{line_number}: class id {class_id} exceeds class_count={class_count}"
            )
            continue
        if not all(0.0 <= value <= 1.0 for value in coords):
            errors.append(f"{path.name}:{line_number}: bbox values must be normalized to [0, 1]")
            continue
        if coords[2] <= 0.0 or coords[3] <= 0.0:
            errors.append(f"{path.name}:{line_number}: bbox width/height must be > 0")
            continue

        annotation_count += 1

    return annotation_count, errors


def build_yolo_detection_manifest(
    dataset_root: str | Path,
    class_count: int | None = None,
) -> dict:
    """Validate a YOLO detection dataset and return a JSON-serializable manifest."""
    root = Path(dataset_root).resolve()
    issues: list[DatasetIssue] = []
    split_summaries: dict[str, SplitSummary] = {}
    total_annotations = 0

    if not root.exists():
        _add_issue(issues, "ERROR", f"Dataset root does not exist: {root}")
        return {
            "task": "yolo_detection",
            "dataset_root": str(root),
            "splits": {},
            "totals": {"images": 0, "labels": 0, "annotations": 0},
            "issues": [asdict(issue) for issue in issues],
        }

    images_root = root / "images"
    labels_root = root / "labels"

    if not images_root.exists():
        _add_issue(issues, "ERROR", f"Missing images directory: {images_root}")
    if not labels_root.exists():
        _add_issue(issues, "ERROR", f"Missing labels directory: {labels_root}")

    for split in ("train", "val", "test"):
        image_dir = images_root / split
        label_dir = labels_root / split
        summary = SplitSummary(name=split)

        images = _iter_files(image_dir, IMAGE_SUFFIXES)
        labels = _iter_files(label_dir, {".txt"})

        summary.image_count = len(images)
        summary.label_count = len(labels)

        if split in {"train", "val"}:
            if not image_dir.exists():
                _add_issue(issues, "ERROR", f"Missing required image split: {image_dir}")
            if not label_dir.exists():
                _add_issue(issues, "ERROR", f"Missing required label split: {label_dir}")
            if image_dir.exists() and not images:
                _add_issue(issues, "ERROR", f"Required image split is empty: {image_dir}")

        missing_labels = sorted(set(images) - set(labels))
        orphan_labels = sorted(set(labels) - set(images))
        summary.missing_labels = len(missing_labels)
        summary.orphan_labels = len(orphan_labels)
        summary.paired_count = len(set(images) & set(labels))

        for stem in missing_labels:
            _add_issue(
                issues,
                "ERROR",
                f"{split}: image is missing a label file: {images[stem].name}",
            )
        for stem in orphan_labels:
            _add_issue(
                issues,
                "ERROR",
                f"{split}: label has no matching image: {labels[stem].name}",
            )

        invalid_files = 0
        for stem in sorted(set(images) & set(labels)):
            annotation_count, errors = _validate_yolo_label_file(labels[stem], class_count)
            if errors:
                invalid_files += 1
                for message in errors:
                    _add_issue(issues, "ERROR", message)
            summary.annotation_count += annotation_count

        summary.invalid_label_files = invalid_files
        total_annotations += summary.annotation_count
        split_summaries[split] = summary

    return {
        "task": "yolo_detection",
        "dataset_root": str(root),
        "class_count": class_count,
        "splits": {name: asdict(summary) for name, summary in split_summaries.items()},
        "totals": {
            "images": sum(summary.image_count for summary in split_summaries.values()),
            "labels": sum(summary.label_count for summary in split_summaries.values()),
            "annotations": total_annotations,
        },
        "issues": [asdict(issue) for issue in issues],
    }


def build_ocr_recognition_manifest(
    dataset_root: str | Path,
    labels_csv: str | Path | None = None,
    plate_regex: str = DEFAULT_PLATE_REGEX,
) -> dict:
    """Validate an OCR recognition dataset and return a JSON-serializable manifest."""
    root = Path(dataset_root).resolve()
    issues: list[DatasetIssue] = []
    split_counts: dict[str, int] = {}
    regex = re.compile(plate_regex)

    labels_path = Path(labels_csv).resolve() if labels_csv is not None else root / "labels.csv"
    images_root = root / "images"

    if not root.exists():
        _add_issue(issues, "ERROR", f"Dataset root does not exist: {root}")
    if not images_root.exists():
        _add_issue(issues, "ERROR", f"Missing OCR images directory: {images_root}")
    if not labels_path.exists():
        _add_issue(issues, "ERROR", f"Missing OCR labels file: {labels_path}")

    duplicate_keys: set[tuple[str, str]] = set()
    duplicate_count = 0
    row_count = 0
    valid_count = 0

    if labels_path.exists():
        try:
            with labels_path.open("r", encoding="utf-8", newline="") as file_obj:
                reader = csv.DictReader(file_obj)
                fieldnames = {name.strip() for name in (reader.fieldnames or [])}
                if not {"filename", "text"}.issubset(fieldnames):
                    _add_issue(
                        issues,
                        "ERROR",
                        f"OCR labels file must contain filename,text columns: {labels_path}",
                    )
                else:
                    for row_number, row in enumerate(reader, start=2):
                        row_count += 1
                        filename = str(row.get("filename", "")).strip()
                        text = str(row.get("text", "")).strip().upper()
                        split = str(row.get("split", "")).strip() or "unspecified"

                        if not filename:
                            _add_issue(issues, "ERROR", f"labels.csv:{row_number}: filename is required")
                            continue
                        if not text:
                            _add_issue(issues, "ERROR", f"labels.csv:{row_number}: text is required")
                            continue

                        key = (split, filename)
                        if key in duplicate_keys:
                            duplicate_count += 1
                            _add_issue(
                                issues,
                                "ERROR",
                                f"labels.csv:{row_number}: duplicate OCR sample for split={split} file={filename}",
                            )
                            continue
                        duplicate_keys.add(key)

                        candidate_paths = [
                            images_root / split / filename,
                            images_root / filename,
                        ]
                        resolved_image = next((path for path in candidate_paths if path.exists()), None)
                        if resolved_image is None:
                            _add_issue(
                                issues,
                                "ERROR",
                                f"labels.csv:{row_number}: image file not found for {filename}",
                            )
                            continue

                        if resolved_image.suffix.lower() not in IMAGE_SUFFIXES:
                            _add_issue(
                                issues,
                                "ERROR",
                                f"labels.csv:{row_number}: unsupported image suffix for {filename}",
                            )
                            continue

                        if not regex.match(text):
                            _add_issue(
                                issues,
                                "ERROR",
                                f"labels.csv:{row_number}: text does not match plate regex {plate_regex}: {text}",
                            )
                            continue

                        split_counts[split] = split_counts.get(split, 0) + 1
                        valid_count += 1
        except OSError as exc:
            _add_issue(issues, "ERROR", f"Could not read OCR labels file {labels_path}: {exc}")

    if row_count == 0:
        _add_issue(issues, "ERROR", f"OCR labels file has no samples: {labels_path}")

    return {
        "task": "ocr_recognition",
        "dataset_root": str(root),
        "labels_csv": str(labels_path),
        "plate_regex": plate_regex,
        "splits": split_counts,
        "totals": {
            "rows": row_count,
            "valid_samples": valid_count,
            "duplicates": duplicate_count,
        },
        "issues": [asdict(issue) for issue in issues],
    }


def has_errors(manifest: dict) -> bool:
    """Return True when the manifest contains any ERROR issue."""
    return any(issue.get("level") == "ERROR" for issue in manifest.get("issues", []))


def write_manifest(manifest: dict, output_path: str | Path) -> None:
    """Write a dataset manifest to JSON."""
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
