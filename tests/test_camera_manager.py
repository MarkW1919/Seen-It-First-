from pathlib import Path

from edge.camera.manager import CameraManager


def test_load_config_handles_empty_yaml(tmp_path: Path):
    cfg = tmp_path / "camera.yaml"
    cfg.write_text("", encoding="utf-8")

    manager = CameraManager(str(cfg))

    assert manager.cameras == {}


def test_load_config_supports_legacy_list_and_skips_invalid_entries(tmp_path: Path):
    cfg = tmp_path / "camera.yaml"
    cfg.write_text(
        """
        cameras:
          - id: cam_a
            type: CSI
            sensor_id: 2
            enabled: true
          - not-a-dict
          - id: cam_disabled
            enabled: false
        """,
        encoding="utf-8",
    )

    manager = CameraManager(str(cfg))

    assert sorted(manager.cameras.keys()) == ["cam_a"]
    assert manager.get_camera("cam_a").config.camera_type == "csi"
    assert manager.get_camera("cam_a").config.sensor_id == 2


def test_load_config_uses_defaults_for_invalid_numeric_values(tmp_path: Path):
    cfg = tmp_path / "camera.yaml"
    cfg.write_text(
        """
        cameras:
          cam_bad_nums:
            sensor_id: not-a-number
            width: nope
            height: bad
            fps: ???
            enabled: true
        """,
        encoding="utf-8",
    )

    manager = CameraManager(str(cfg))
    cam = manager.get_camera("cam_bad_nums")

    assert cam is not None
    assert cam.config.sensor_id == 0
    assert cam.config.width == 1920
    assert cam.config.height == 1080
    assert cam.config.fps == 30


def test_load_config_handles_malformed_yaml(tmp_path: Path):
    cfg = tmp_path / "camera.yaml"
    cfg.write_text("cameras: [", encoding="utf-8")

    manager = CameraManager(str(cfg))

    assert manager.cameras == {}
