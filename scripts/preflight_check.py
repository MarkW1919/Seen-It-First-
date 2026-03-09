#!/usr/bin/env python3
"""Seen-It-First build preflight checker.

Validates software-side prerequisites and reports blockers before first run.

Usage:
    python scripts/preflight_check.py
    python scripts/preflight_check.py --strict
"""

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
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    results = run_checks(strict=args.strict)
    return print_report(results)


if __name__ == "__main__":
    raise SystemExit(main())
