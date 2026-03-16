import csv
from pathlib import Path

from edge.ai_training_phase3.dataset_manifest import (
    build_ocr_recognition_manifest,
    build_yolo_detection_manifest,
    has_errors,
)


def test_build_yolo_detection_manifest_valid_dataset(tmp_path: Path):
    dataset_root = tmp_path / "yolo"
    for rel in [
        "images/train",
        "images/val",
        "labels/train",
        "labels/val",
    ]:
        (dataset_root / rel).mkdir(parents=True, exist_ok=True)

    (dataset_root / "images/train/car_001.jpg").write_bytes(b"img")
    (dataset_root / "images/val/car_002.jpg").write_bytes(b"img")
    (dataset_root / "labels/train/car_001.txt").write_text("0 0.5 0.5 0.2 0.2\n", encoding="utf-8")
    (dataset_root / "labels/val/car_002.txt").write_text("0 0.4 0.6 0.1 0.1\n", encoding="utf-8")

    manifest = build_yolo_detection_manifest(dataset_root, class_count=1)

    assert not has_errors(manifest)
    assert manifest["totals"]["images"] == 2
    assert manifest["totals"]["annotations"] == 2
    assert manifest["splits"]["train"]["paired_count"] == 1


def test_build_yolo_detection_manifest_reports_missing_label(tmp_path: Path):
    dataset_root = tmp_path / "yolo"
    for rel in [
        "images/train",
        "images/val",
        "labels/train",
        "labels/val",
    ]:
        (dataset_root / rel).mkdir(parents=True, exist_ok=True)

    (dataset_root / "images/train/car_001.jpg").write_bytes(b"img")
    (dataset_root / "images/val/car_002.jpg").write_bytes(b"img")
    (dataset_root / "labels/val/car_002.txt").write_text("0 0.4 0.6 0.1 0.1\n", encoding="utf-8")

    manifest = build_yolo_detection_manifest(dataset_root)

    assert has_errors(manifest)
    assert any("missing a label file" in issue["message"] for issue in manifest["issues"])


def test_build_ocr_recognition_manifest_valid_dataset(tmp_path: Path):
    dataset_root = tmp_path / "ocr"
    (dataset_root / "images/train").mkdir(parents=True, exist_ok=True)
    (dataset_root / "images/val").mkdir(parents=True, exist_ok=True)
    (dataset_root / "images/train/plate_001.jpg").write_bytes(b"img")
    (dataset_root / "images/val/plate_002.jpg").write_bytes(b"img")

    with (dataset_root / "labels.csv").open("w", encoding="utf-8", newline="") as file_obj:
        writer = csv.DictWriter(file_obj, fieldnames=["filename", "text", "split"])
        writer.writeheader()
        writer.writerow({"filename": "plate_001.jpg", "text": "ABC1234", "split": "train"})
        writer.writerow({"filename": "plate_002.jpg", "text": "XYZ789", "split": "val"})

    manifest = build_ocr_recognition_manifest(dataset_root)

    assert not has_errors(manifest)
    assert manifest["totals"]["valid_samples"] == 2
    assert manifest["splits"] == {"train": 1, "val": 1}


def test_build_ocr_recognition_manifest_reports_invalid_label_row(tmp_path: Path):
    dataset_root = tmp_path / "ocr"
    (dataset_root / "images").mkdir(parents=True, exist_ok=True)
    (dataset_root / "images/plate_001.jpg").write_bytes(b"img")

    with (dataset_root / "labels.csv").open("w", encoding="utf-8", newline="") as file_obj:
        writer = csv.DictWriter(file_obj, fieldnames=["filename", "text"])
        writer.writeheader()
        writer.writerow({"filename": "plate_001.jpg", "text": "bad-text"})

    manifest = build_ocr_recognition_manifest(dataset_root)

    assert has_errors(manifest)
    assert any("does not match plate regex" in issue["message"] for issue in manifest["issues"])
