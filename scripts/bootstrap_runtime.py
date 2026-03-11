#!/usr/bin/env python3
"""Create local runtime directories/files required for first boot."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

RUNTIME_DIRS = [
    REPO_ROOT / "data",
    REPO_ROOT / "logs",
    REPO_ROOT / "data" / "evidence",
    REPO_ROOT / "data" / "snapshots",
]

HOTLIST_PATH = REPO_ROOT / "data" / "hotlist.csv"


def main() -> int:
    for d in RUNTIME_DIRS:
        d.mkdir(parents=True, exist_ok=True)
        print(f"created/exists: {d}")

    if not HOTLIST_PATH.exists():
        HOTLIST_PATH.write_text("ABC1234,stolen,high\n", encoding="utf-8")
        print(f"created: {HOTLIST_PATH}")
    else:
        print(f"exists: {HOTLIST_PATH}")

    print("runtime bootstrap complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
