from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml


SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "preflight_check.py"


def _write_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data), encoding="utf-8")


def test_preflight_passes_with_valid_layout(tmp_path: Path):
    repo = tmp_path / "repo"
    for rel in [
        "edge/config",
        "edge/camera",
        "models/vehicle",
        "models/plate",
        "models/ocr",
        "models/classifier",
        "data",
        "logs",
    ]:
        (repo / rel).mkdir(parents=True, exist_ok=True)

    for model in [
        "models/vehicle/vehicle.engine",
        "models/plate/plate.engine",
        "models/ocr/ocr.engine",
        "models/classifier/classifier.engine",
    ]:
        (repo / model).write_text("engine", encoding="utf-8")

    _write_yaml(
        repo / "edge/config/system.yaml",
        {
            "inference": {
                "vehicle_detection": {"model_path": "models/vehicle/vehicle.engine"},
                "plate_detection": {"model_path": "models/plate/plate.engine"},
                "ocr": {"model_path": "models/ocr/ocr.engine"},
                "classifier": {"model_path": "models/classifier/classifier.engine"},
            }
        },
    )

    _write_yaml(
        repo / "edge/camera/config.yaml",
        {"cameras": {"cam1": {"sensor_id": 0, "width": 1920, "height": 1080, "fps": 30, "enabled": True}}},
    )

    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--system-config",
            str(repo / "edge/config/system.yaml"),
            "--camera-config",
            str(repo / "edge/camera/config.yaml"),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0
    assert "Preflight checks passed." in proc.stdout


def test_preflight_fails_with_missing_model_file(tmp_path: Path):
    repo = tmp_path / "repo"
    for rel in ["edge/config", "edge/camera", "data", "logs"]:
        (repo / rel).mkdir(parents=True, exist_ok=True)

    _write_yaml(
        repo / "edge/config/system.yaml",
        {
            "inference": {
                "vehicle_detection": {"model_path": "models/vehicle/vehicle.engine"},
                "plate_detection": {"model_path": "models/plate/plate.engine"},
                "ocr": {"model_path": "models/ocr/ocr.engine"},
                "classifier": {"model_path": "models/classifier/classifier.engine"},
            }
        },
    )
    _write_yaml(
        repo / "edge/camera/config.yaml",
        {"cameras": {"cam1": {"sensor_id": 0, "width": 1920, "height": 1080, "fps": 30, "enabled": True}}},
    )

    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--system-config",
            str(repo / "edge/config/system.yaml"),
            "--camera-config",
            str(repo / "edge/camera/config.yaml"),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 1
    assert "Missing model/engine path for key inference.vehicle_detection.model_path" in proc.stdout
