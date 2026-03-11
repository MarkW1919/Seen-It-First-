#!/usr/bin/env python3
"""Seen-It-First build preflight checker.

Validates software-side prerequisites and reports blockers before first run.

Usage:
    python scripts/preflight_check.py
    python scripts/preflight_check.py --strict
"""
"""Deployment preflight checker for Seen-It-First edge service."""

from __future__ import annotations

import argparse
import os
import socket
from dataclasses import dataclass
from pathlib import Path
from typing import List

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
SYSTEM_CONFIG_PATH = REPO_ROOT / "edge" / "config" / "system.yaml"
CAMERA_CONFIG_PATH = REPO_ROOT / "edge" / "camera" / "config.yaml"
SYSTEMD_UNIT_PATH = REPO_ROOT / "systemd" / "seen-it-first-edge.service"


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str
    blocker: bool = False


def _check_exists(path: Path, desc: str, blocker: bool = True) -> CheckResult:
    exists = path.exists()
    return CheckResult(
        name=desc,
        ok=exists,
        detail=f"{path} {'found' if exists else 'missing'}",
        blocker=blocker,
    )


def _check_writable_dir(path: Path, desc: str, blocker: bool = True) -> CheckResult:
    if not path.exists():
        return CheckResult(desc, False, f"{path} missing", blocker=blocker)
    ok = os.access(path, os.W_OK)
    return CheckResult(desc, ok, f"{path} {'writable' if ok else 'not writable'}", blocker=blocker)


def _check_port(host: str, port: int) -> CheckResult:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(0.6)
    try:
        in_use = sock.connect_ex((host, port)) == 0
        if in_use:
            return CheckResult("API port availability", False, f"{host}:{port} already in use", blocker=True)
        return CheckResult("API port availability", True, f"{host}:{port} appears free", blocker=False)
    except OSError as exc:
        return CheckResult("API port availability", False, f"port check error: {exc}", blocker=False)
    finally:
        sock.close()


def run_checks(strict: bool = False) -> List[CheckResult]:
    results: List[CheckResult] = []

    results.append(_check_exists(SYSTEM_CONFIG_PATH, "System config present"))
    results.append(_check_exists(CAMERA_CONFIG_PATH, "Camera config present"))
    results.append(_check_exists(SYSTEMD_UNIT_PATH, "Systemd unit file present", blocker=False))

    if not SYSTEM_CONFIG_PATH.exists():
        return results

    with open(SYSTEM_CONFIG_PATH, "r", encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh) or {}

    # Paths from config
    system_cfg = cfg.get("system", {})
    db_rel = system_cfg.get("database_path", "data/seen_it_first.db")
    db_path = REPO_ROOT / db_rel
    data_dir = db_path.parent

    hotlist_cfg = cfg.get("hotlist", {})
    hotlist_path = REPO_ROOT / hotlist_cfg.get("file_path", "data/hotlist.csv")

    evidence_cfg = cfg.get("evidence", {})
    evidence_root = REPO_ROOT / evidence_cfg.get("root", "data/evidence")

    api_cfg = cfg.get("api", {})
    api_host = api_cfg.get("host", "0.0.0.0")
    api_port = int(api_cfg.get("port", 8080))

    inf_cfg = cfg.get("inference", {})
    model_targets = {
        "Vehicle engine": inf_cfg.get("vehicle_detection", {}).get("model_path", "models/vehicle/vehicle.engine"),
        "Plate engine": inf_cfg.get("plate_detection", {}).get("model_path", "models/plate/plate.engine"),
        "OCR engine": inf_cfg.get("ocr", {}).get("model_path", "models/ocr/ocr.engine"),
        "Classifier engine": inf_cfg.get("classifier", {}).get("model_path", "models/classifier/classifier.engine"),
    }

    # Directory/runtime checks
    results.append(_check_writable_dir(data_dir, "Data directory writable"))
    results.append(_check_writable_dir(REPO_ROOT / "logs", "Logs directory writable"))

    # Hotlist presence is optional for startup, but recommended.
    hotlist_exists = hotlist_path.exists()
    results.append(
        CheckResult(
            "Hotlist CSV",
            hotlist_exists,
            f"{hotlist_path} {'found' if hotlist_exists else 'missing (optional)'}",
            blocker=False,
        )
    )

    # Evidence root may be created lazily, so strict-mode only blocker.
    if evidence_root.exists():
        results.append(_check_writable_dir(evidence_root, "Evidence directory writable", blocker=False))
    else:
        results.append(
            CheckResult(
                "Evidence directory",
                not strict,
                f"{evidence_root} missing (will be created at runtime)",
                blocker=strict,
            )
        )

    # Model engines are runtime blockers for full capability.
    for label, rel_path in model_targets.items():
        p = REPO_ROOT / rel_path
        ok = p.exists()
        results.append(
            CheckResult(
                label,
                ok,
                f"{p} {'found' if ok else 'missing'}",
                blocker=True,
            )
        )

    # API port check (advisory)
    host_for_probe = "127.0.0.1" if api_host == "0.0.0.0" else api_host
    results.append(_check_port(host_for_probe, api_port))

    return results


def print_report(results: List[CheckResult]) -> int:
    blockers = [r for r in results if (not r.ok and r.blocker)]
    warnings = [r for r in results if (not r.ok and not r.blocker)]

    print("Seen-It-First preflight report")
    print("=" * 36)

    for r in results:
        state = "PASS" if r.ok else ("BLOCKER" if r.blocker else "WARN")
        print(f"[{state:<7}] {r.name}: {r.detail}")

    print("\nSummary")
    print("-" * 36)
    print(f"Pass: {sum(1 for r in results if r.ok)}")
    print(f"Warnings: {len(warnings)}")
    print(f"Blockers: {len(blockers)}")

    if blockers:
        print("\nAction needed: resolve blockers before first production run.")
        return 1

    print("\nPreflight passed with no blockers.")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check Seen-It-First go-live prerequisites")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat optional runtime-createable paths as blockers",
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
    results = run_checks(strict=args.strict)
    return print_report(results)
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
