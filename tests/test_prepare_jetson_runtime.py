import importlib.util
import sys
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parent.parent / "scripts" / "prepare_jetson_runtime.py"
SPEC = importlib.util.spec_from_file_location("prepare_jetson_runtime", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_build_steps_default_order():
    args = MODULE.parse_args(["--dry-run"])
    steps = MODULE.build_steps(args, python_executable="python")

    assert [step.name for step in steps] == [
        "Bootstrap runtime files",
        "Validate runtime config",
        "Download pretrained models",
        "Build TensorRT engines",
        "Run preflight gate",
        "Run pipeline smoke test",
    ]
    assert "--pipeline-only" in steps[-1].command


def test_build_steps_respects_skip_flags():
    args = MODULE.parse_args(
        [
            "--dry-run",
            "--skip-download",
            "--skip-build",
            "--skip-pipeline-test",
            "--strict-preflight",
        ]
    )
    steps = MODULE.build_steps(args, python_executable="python")

    assert [step.name for step in steps] == [
        "Bootstrap runtime files",
        "Validate runtime config",
        "Run preflight gate",
    ]
    assert "--strict" in steps[-1].command
