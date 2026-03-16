#!/usr/bin/env python3
"""Run the recommended Phase 1 Jetson bring-up steps in build-order."""

from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Step:
    name: str
    command: list[str]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare a Seen-It-First runtime on Jetson in the supported order."
    )
    parser.add_argument(
        "--precision",
        choices=["fp16", "fp32"],
        default="fp16",
        help="TensorRT engine precision for the build step (default: fp16).",
    )
    parser.add_argument(
        "--system-config",
        type=Path,
        default=REPO_ROOT / "edge" / "config" / "system.yaml",
        help="System config path for validation and preflight.",
    )
    parser.add_argument(
        "--camera-config",
        type=Path,
        default=REPO_ROOT / "edge" / "camera" / "config.yaml",
        help="Camera config path for validation and preflight.",
    )
    parser.add_argument(
        "--pipeline-runs",
        type=int,
        default=1,
        help="Number of pipeline smoke-test runs (default: 1).",
    )
    parser.add_argument(
        "--skip-download",
        action="store_true",
        help="Skip the pretrained model download step.",
    )
    parser.add_argument(
        "--skip-build",
        action="store_true",
        help="Skip the TensorRT engine build step.",
    )
    parser.add_argument(
        "--skip-pipeline-test",
        action="store_true",
        help="Skip the pipeline smoke-test step.",
    )
    parser.add_argument(
        "--strict-preflight",
        action="store_true",
        help="Run preflight in strict mode.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the command plan without executing it.",
    )
    return parser.parse_args(argv)


def build_steps(args: argparse.Namespace, python_executable: str | None = None) -> list[Step]:
    python_cmd = python_executable or sys.executable

    def py(script_name: str, *extra: str) -> list[str]:
        return [python_cmd, str(REPO_ROOT / "scripts" / script_name), *extra]

    steps = [
        Step("Bootstrap runtime files", py("bootstrap_runtime.py")),
        Step(
            "Validate runtime config",
            py(
                "validate_config.py",
                "--system",
                str(args.system_config),
                "--camera",
                str(args.camera_config),
            ),
        ),
    ]

    if not args.skip_download:
        steps.append(Step("Download pretrained models", py("download_models.py")))

    if not args.skip_build:
        steps.append(
            Step(
                "Build TensorRT engines",
                py("build_tensorrt_engines.py", "--precision", args.precision),
            )
        )

    preflight_cmd = py(
        "preflight_check.py",
        "--system-config",
        str(args.system_config),
        "--camera-config",
        str(args.camera_config),
    )
    if args.strict_preflight:
        preflight_cmd.append("--strict")
    steps.append(Step("Run preflight gate", preflight_cmd))

    if not args.skip_pipeline_test:
        steps.append(
            Step(
                "Run pipeline smoke test",
                py(
                    "test_pipeline.py",
                    "--pipeline-only",
                    "--runs",
                    str(args.pipeline_runs),
                ),
            )
        )

    return steps


def _format_command(command: list[str]) -> str:
    return subprocess.list2cmdline(command)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    steps = build_steps(args)

    if sys.platform != "linux":
        print("WARN: prepare_jetson_runtime.py is intended for Linux/Jetson hosts.")

    print("Seen-It-First Jetson runtime plan")
    print("=" * 36)
    for idx, step in enumerate(steps, start=1):
        print(f"{idx}. {step.name}")
        print(f"   {_format_command(step.command)}")

    if args.dry_run:
        return 0

    for idx, step in enumerate(steps, start=1):
        print()
        print(f"[{idx}/{len(steps)}] {step.name}")
        result = subprocess.run(step.command, cwd=REPO_ROOT, check=False)
        if result.returncode != 0:
            print(f"FAILED: {step.name} (exit code {result.returncode})")
            return result.returncode

    print()
    print("Runtime preparation completed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
