#!/usr/bin/env python3
"""Deployment preflight checker for Seen-It-First edge service."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import yaml


REQUIRED_MODEL_KEYS = [
    "inference.vehicle_detection.model_path",
    "inference.plate_detection.model_path",
    "inference.ocr.model_path",
    "inference.classifier.model_path",
]


class CheckContext:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def error(self, message: str) -> None:
        self.errors.append(message)

    def warn(self, message: str) -> None:
        self.warnings.append(message)


def _load_yaml(path: Path, label: str, ctx: CheckContext) -> dict:
    try:
        with path.open("r", encoding="utf-8") as f:
            parsed = yaml.safe_load(f) or {}
    except FileNotFoundError:
        ctx.error(f"Missing required config file: {path}")
        return {}
    except (OSError, yaml.YAMLError) as exc:
        ctx.error(f"Failed to parse {label} YAML at {path}: {exc}")
        return {}

    if not isinstance(parsed, dict):
        ctx.error(f"Invalid {label} root type at {path}: expected dict, found {type(parsed).__name__}")
        return {}

    return parsed


def _get_key(config: dict, key_path: str):
    current = config
    for part in key_path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def check_required_files(system_config: Path, camera_config: Path, ctx: CheckContext) -> None:
    for path in (system_config, camera_config):
        if not path.exists():
            ctx.error(f"Missing required config file: {path}")


def check_models(system_cfg: dict, repo_root: Path, ctx: CheckContext) -> None:
    for key in REQUIRED_MODEL_KEYS:
        value = _get_key(system_cfg, key)
        if value is None:
            ctx.error(f"Missing required key in edge/config/system.yaml: {key}")
            continue
        if not isinstance(value, str) or not value.strip():
            ctx.error(f"Invalid required model path value for key {key}: {value!r}")
            continue

        path = _resolve(repo_root, value)
        if not path.exists():
            ctx.error(f"Missing model/engine path for key {key}: {path}")


def check_writable_paths(repo_root: Path, ctx: CheckContext) -> None:
    for rel in ("data", "logs"):
        path = repo_root / rel
        if not path.exists():
            ctx.error(f"Missing required writable directory: {path}")
            continue

        if not path.is_dir():
            ctx.error(f"Writable path is not a directory: {path}")
            continue

        if not os.access(path, os.W_OK | os.X_OK):
            ctx.error(f"Runtime user cannot write directory: {path}")
            continue

        probe = path / ".preflight_write_probe"
        try:
            with probe.open("w", encoding="utf-8") as f:
                f.write("ok\n")
            probe.unlink()
        except OSError as exc:
            ctx.error(f"Runtime user cannot create files in {path}: {exc}")


def _validate_camera(cam_id: str, cam_def: dict, ctx: CheckContext) -> None:
    required_int_fields = ["sensor_id", "width", "height", "fps"]
    for field in required_int_fields:
        if field not in cam_def:
            ctx.error(f"Camera {cam_id} missing required key: cameras.{cam_id}.{field}")
            continue
        try:
            value = int(cam_def[field])
        except (TypeError, ValueError):
            ctx.error(f"Camera {cam_id} has non-integer value for cameras.{cam_id}.{field}: {cam_def[field]!r}")
            continue
        if value <= 0 and field != "sensor_id":
            ctx.error(f"Camera {cam_id} has invalid non-positive value for cameras.{cam_id}.{field}: {value}")

    cam_type = str(cam_def.get("type", "csi")).lower()
    if cam_type not in {"csi", "rtsp"}:
        ctx.error(f"Camera {cam_id} has invalid type in cameras.{cam_id}.type: {cam_type!r}")

    if cam_type == "rtsp":
        uri = cam_def.get("uri")
        if not isinstance(uri, str) or not uri.strip():
            ctx.error(f"Camera {cam_id} requires non-empty URI for cameras.{cam_id}.uri when type=rtsp")


def check_camera_config(camera_cfg: dict, ctx: CheckContext) -> None:
    cameras = camera_cfg.get("cameras")
    if not isinstance(cameras, dict):
        ctx.error("Invalid camera config: required mapping at key cameras")
        return

    enabled = []
    for cam_id, cam_def in cameras.items():
        if not isinstance(cam_def, dict):
            ctx.error(f"Camera definition must be a mapping: cameras.{cam_id}")
            continue

        if bool(cam_def.get("enabled", True)):
            enabled.append((str(cam_id), cam_def))

    if not enabled:
        ctx.error("No enabled cameras found in edge/camera/config.yaml (expected at least one enabled=true)")
        return

    sensor_ids: set[int] = set()
    for cam_id, cam_def in enabled:
        _validate_camera(cam_id, cam_def, ctx)
        try:
            sensor_id = int(cam_def.get("sensor_id"))
        except (TypeError, ValueError):
            continue
        if sensor_id in sensor_ids:
            ctx.error(f"Duplicate sensor_id among enabled cameras: {sensor_id} (camera {cam_id})")
        sensor_ids.add(sensor_id)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate Seen-It-First deployment prerequisites.")
    parser.add_argument(
        "--system-config",
        default="edge/config/system.yaml",
        help="Path to system YAML config (default: edge/config/system.yaml)",
    )
    parser.add_argument(
        "--camera-config",
        default="edge/camera/config.yaml",
        help="Path to camera YAML config (default: edge/camera/config.yaml)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    ctx = CheckContext()

    system_config = Path(args.system_config).resolve()
    camera_config = Path(args.camera_config).resolve()
    repo_root = system_config.parents[2]

    check_required_files(system_config, camera_config, ctx)
    system_cfg = _load_yaml(system_config, "system config", ctx)
    camera_cfg = _load_yaml(camera_config, "camera config", ctx)

    if system_cfg:
        check_models(system_cfg, repo_root, ctx)
    if camera_cfg:
        check_camera_config(camera_cfg, ctx)

    check_writable_paths(repo_root, ctx)

    if ctx.errors:
        print("Preflight checks FAILED:")
        for err in ctx.errors:
            print(f"  - {err}")
        if ctx.warnings:
            print("Warnings:")
            for warn in ctx.warnings:
                print(f"  - {warn}")
        return 1

    print("Preflight checks passed.")
    if ctx.warnings:
        print("Warnings:")
        for warn in ctx.warnings:
            print(f"  - {warn}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
