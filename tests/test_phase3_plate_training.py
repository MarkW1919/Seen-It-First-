from pathlib import Path

import yaml

from edge.ai_training_phase3.plate_training import (
    PlateTrainingConfig,
    install_runtime_plate_checkpoint,
    prepare_plate_training_workspace,
)


def test_prepare_plate_training_workspace_writes_dataset_yaml(tmp_path: Path):
    dataset_root = tmp_path / "plate_dataset"
    for rel in [
        "images/train",
        "images/val",
        "labels/train",
        "labels/val",
    ]:
        (dataset_root / rel).mkdir(parents=True, exist_ok=True)

    (dataset_root / "images/train/plate_001.jpg").write_bytes(b"img")
    (dataset_root / "images/val/plate_002.jpg").write_bytes(b"img")
    (dataset_root / "labels/train/plate_001.txt").write_text("0 0.5 0.5 0.2 0.2\n", encoding="utf-8")
    (dataset_root / "labels/val/plate_002.txt").write_text("0 0.4 0.6 0.2 0.2\n", encoding="utf-8")

    config = PlateTrainingConfig(
        dataset_root=dataset_root,
        workspace_dir=tmp_path / "workspace",
        project_dir=tmp_path / "runs",
    )
    prepared = prepare_plate_training_workspace(config)

    parsed = yaml.safe_load(prepared["dataset_yaml"].read_text(encoding="utf-8"))
    assert parsed["train"] == "images/train"
    assert parsed["val"] == "images/val"
    assert parsed["names"] == ["plate"]
    assert prepared["manifest_path"].exists()


def test_install_runtime_plate_checkpoint_copies_file(tmp_path: Path):
    checkpoint = tmp_path / "best.pt"
    checkpoint.write_bytes(b"weights")

    installed = install_runtime_plate_checkpoint(
        checkpoint_path=checkpoint,
        runtime_path=tmp_path / "models" / "raw" / "yolov8n_lp.pt",
    )

    assert installed.exists()
    assert installed.read_bytes() == b"weights"
