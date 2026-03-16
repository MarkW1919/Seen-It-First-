#!/usr/bin/env python3
"""Validate Phase 3 training datasets and optionally write a manifest JSON."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from edge.ai_training_phase3.dataset_manifest import (
    DEFAULT_PLATE_REGEX,
    build_ocr_recognition_manifest,
    build_yolo_detection_manifest,
    has_errors,
    write_manifest,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate Phase 3 training datasets for Seen-It-First."
    )
    parser.add_argument(
        "--task",
        choices=["yolo_detection", "ocr_recognition"],
        required=True,
        help="Dataset type to validate.",
    )
    parser.add_argument(
        "--dataset-root",
        type=Path,
        required=True,
        help="Root directory of the dataset to validate.",
    )
    parser.add_argument(
        "--class-count",
        type=int,
        default=None,
        help="Optional YOLO class count bound for yolo_detection validation.",
    )
    parser.add_argument(
        "--labels-csv",
        type=Path,
        default=None,
        help="Optional labels.csv path for OCR datasets.",
    )
    parser.add_argument(
        "--plate-regex",
        default=DEFAULT_PLATE_REGEX,
        help="Regex used to validate OCR label text.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional path to write the manifest JSON.",
    )
    return parser.parse_args()


def _print_manifest_summary(manifest: dict) -> None:
    print(f"Task: {manifest['task']}")
    print(f"Dataset root: {manifest['dataset_root']}")

    splits = manifest.get("splits", {})
    if manifest["task"] == "yolo_detection":
        for name, summary in splits.items():
            print(
                f"  {name:<12} images={summary['image_count']:<4} "
                f"labels={summary['label_count']:<4} "
                f"paired={summary['paired_count']:<4} "
                f"annotations={summary['annotation_count']}"
            )
    else:
        for name, count in sorted(splits.items()):
            print(f"  {name:<12} samples={count}")

    totals = manifest.get("totals", {})
    print(f"Totals: {totals}")

    issues = manifest.get("issues", [])
    if not issues:
        print("PASS: no dataset validation errors found")
        return

    for issue in issues:
        print(f"{issue['level']}: {issue['message']}")


def main() -> int:
    args = parse_args()

    if args.task == "yolo_detection":
        manifest = build_yolo_detection_manifest(
            dataset_root=args.dataset_root,
            class_count=args.class_count,
        )
    else:
        manifest = build_ocr_recognition_manifest(
            dataset_root=args.dataset_root,
            labels_csv=args.labels_csv,
            plate_regex=args.plate_regex,
        )

    if args.output is not None:
        write_manifest(manifest, args.output)
        print(f"Manifest written to: {args.output}")

    _print_manifest_summary(manifest)
    return 1 if has_errors(manifest) else 0


if __name__ == "__main__":
    raise SystemExit(main())
