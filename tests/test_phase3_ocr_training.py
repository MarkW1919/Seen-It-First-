import csv
from pathlib import Path

from edge.ai_training_phase3.ocr_training import (
    OCRTrainingConfig,
    build_paddleocr_export_command,
    build_paddleocr_train_command,
    find_paddleocr_config,
    prepare_ocr_training_workspace,
)


def test_prepare_ocr_training_workspace_creates_lists_and_dict(tmp_path: Path):
    dataset_root = tmp_path / "ocr_dataset"
    (dataset_root / "images").mkdir(parents=True, exist_ok=True)
    (dataset_root / "images/plate_001.jpg").write_bytes(b"img")
    (dataset_root / "images/plate_002.jpg").write_bytes(b"img")

    with (dataset_root / "labels.csv").open("w", encoding="utf-8", newline="") as file_obj:
        writer = csv.DictWriter(file_obj, fieldnames=["filename", "text"])
        writer.writeheader()
        writer.writerow({"filename": "plate_001.jpg", "text": "ABC1234"})
        writer.writerow({"filename": "plate_002.jpg", "text": "XYZ789"})

    paddle_root = tmp_path / "PaddleOCR"
    (paddle_root / "configs" / "rec" / "PP-OCRv4").mkdir(parents=True, exist_ok=True)
    config_path = paddle_root / "configs" / "rec" / "PP-OCRv4" / "en_PP-OCRv4_rec.yml"
    config_path.write_text("Global: {}\n", encoding="utf-8")

    config = OCRTrainingConfig(
        dataset_root=dataset_root,
        workspace_dir=tmp_path / "workspace",
        paddleocr_root=paddle_root,
        config_path=config_path,
    )

    prepared = prepare_ocr_training_workspace(config)

    assert prepared["char_dict_path"].exists()
    assert "A" in prepared["char_dict_path"].read_text(encoding="utf-8")
    assert prepared["train_list"].exists()
    assert prepared["manifest_path"].exists()


def test_build_paddleocr_commands_include_runtime_relevant_overrides(tmp_path: Path):
    paddle_root = tmp_path / "PaddleOCR"
    (paddle_root / "configs" / "rec" / "PP-OCRv4").mkdir(parents=True, exist_ok=True)
    config_path = paddle_root / "configs" / "rec" / "PP-OCRv4" / "en_PP-OCRv4_rec.yml"
    config_path.write_text("Global: {}\n", encoding="utf-8")

    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    prepared = {
        "images_dir": workspace / "images",
        "train_list": workspace / "train_list.txt",
        "val_list": workspace / "val_list.txt",
        "char_dict_path": workspace / "us_plate_dict.txt",
    }
    for path in prepared.values():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")

    config = OCRTrainingConfig(
        dataset_root=tmp_path / "ocr_dataset",
        workspace_dir=workspace,
        paddleocr_root=paddle_root,
        config_path=config_path,
        pretrained_model="pretrain_models/en_PP-OCRv4_rec_train/best_accuracy",
        epoch_num=50,
        train_batch_size=64,
    )

    train_cmd = build_paddleocr_train_command(config, prepared, python_executable="python")
    export_cmd = build_paddleocr_export_command(
        config,
        prepared,
        checkpoint_prefix=workspace / "output" / "best_accuracy",
        save_inference_dir=workspace / "inference_export",
        python_executable="python",
    )

    assert "tools/train.py" in train_cmd
    assert any(arg.startswith("Global.character_dict_path=") for arg in train_cmd)
    assert any(arg.startswith("Train.dataset.label_file_list=") for arg in train_cmd)
    assert "tools/export_model.py" in export_cmd
    assert any(arg.startswith("Global.save_inference_dir=") for arg in export_cmd)


def test_find_paddleocr_config_prefers_v4_then_v3(tmp_path: Path):
    paddle_root = tmp_path / "PaddleOCR"
    v3 = paddle_root / "configs" / "rec" / "PP-OCRv3"
    v4 = paddle_root / "configs" / "rec" / "PP-OCRv4"
    v3.mkdir(parents=True, exist_ok=True)
    v4.mkdir(parents=True, exist_ok=True)
    v4_path = v4 / "en_PP-OCRv4_rec.yml"
    v4_path.write_text("Global: {}\n", encoding="utf-8")

    assert find_paddleocr_config(paddle_root) == v4_path
