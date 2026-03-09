#!/usr/bin/env python3
"""Validate required runtime keys in Seen-It-First YAML configs."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
SYSTEM_CONFIG = REPO_ROOT / "edge" / "config" / "system.yaml"
CAMERA_CONFIG = REPO_ROOT / "edge" / "camera" / "config.yaml"


@dataclass
class ValidationIssue:
    level: str
    message: str


def _is_valid_url(value: str) -> bool:
    parsed = urlparse(value)
    return bool(parsed.scheme and parsed.netloc)


def validate_system_config(path: Path) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if not path.exists():
        return [ValidationIssue("ERROR", f"Missing system config: {path}")]

    with open(path, "r", encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh) or {}

    required_paths = [
        ("system", "database_path"),
        ("inference", "vehicle_detection", "model_path"),
        ("inference", "plate_detection", "model_path"),
        ("inference", "ocr", "model_path"),
        ("inference", "classifier", "model_path"),
        ("api", "host"),
        ("api", "port"),
        ("hotlist", "file_path"),
        ("navigation", "nominatim_url"),
        ("navigation", "osrm_url"),
    ]

    for key_path in required_paths:
        cur = cfg
        ok = True
        for key in key_path:
            if isinstance(cur, dict) and key in cur:
                cur = cur[key]
            else:
                ok = False
                break
        if not ok:
            issues.append(ValidationIssue("ERROR", f"Missing key: {'.'.join(key_path)}"))

    # Type/range validations
    port = cfg.get("api", {}).get("port")
    if not isinstance(port, int) or not (1 <= port <= 65535):
        issues.append(ValidationIssue("ERROR", f"api.port must be int in [1,65535], got {port!r}"))

    t1 = cfg.get("thermal", {}).get("threshold_1")
    t2 = cfg.get("thermal", {}).get("threshold_2")
    if isinstance(t1, (int, float)) and isinstance(t2, (int, float)):
        if t1 >= t2:
            issues.append(ValidationIssue("ERROR", "thermal.threshold_1 must be less than threshold_2"))

    for key in ("nominatim_url", "osrm_url"):
        value = cfg.get("navigation", {}).get(key, "")
        if not isinstance(value, str) or not _is_valid_url(value):
            issues.append(ValidationIssue("ERROR", f"navigation.{key} must be a valid URL"))

    return issues


def validate_camera_config(path: Path) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if not path.exists():
        return [ValidationIssue("ERROR", f"Missing camera config: {path}")]

    with open(path, "r", encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh) or {}

    cameras = cfg.get("cameras")
    if not isinstance(cameras, dict) or not cameras:
        issues.append(ValidationIssue("ERROR", "camera config must define at least one camera"))
        return issues

    enabled = 0
    for cam_id, cam in cameras.items():
        if not isinstance(cam, dict):
            issues.append(ValidationIssue("ERROR", f"{cam_id} must be a mapping"))
            continue

        for req in ("sensor_id", "width", "height", "fps", "enabled"):
            if req not in cam:
                issues.append(ValidationIssue("ERROR", f"{cam_id}.{req} is required"))

        if cam.get("enabled"):
            enabled += 1

    if enabled == 0:
        issues.append(ValidationIssue("WARN", "No cameras enabled"))

    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Seen-It-First YAML configs")
    parser.add_argument("--system", type=Path, default=SYSTEM_CONFIG)
    parser.add_argument("--camera", type=Path, default=CAMERA_CONFIG)
    args = parser.parse_args()

    issues = validate_system_config(args.system) + validate_camera_config(args.camera)
    errors = [i for i in issues if i.level == "ERROR"]

    if not issues:
        print("PASS: configuration is valid")
        return 0

    for issue in issues:
        print(f"{issue.level}: {issue.message}")

    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
