"""
Hotlist loader: reads plate list from CSV into an in-memory set.

Supports hot-reload via file modification time check.
"""

import csv
import logging
import os
import re
from pathlib import Path

logger = logging.getLogger(__name__)

# Unified normalizer used by loader and matcher.
_PLATE_NORMALIZE_RE = re.compile(r"[^A-Z0-9]")


class HotlistLoader:
    """
    Loads a hotlist of license plates from a CSV file into memory.

    CSV format: plate_number,reason,priority
    Example:
        ABC1234,stolen,high
        XYZ5678,wanted,medium

    Plates are normalized (uppercase, stripped) on load.
    Supports periodic reload by checking file mtime.
    """

    def __init__(self, file_path: str):
        self.file_path = Path(file_path)
        self._plates: dict[str, dict] = {}  # plate → {reason, priority}
        self._plate_set: set[str] = set()
        self._last_mtime: float = 0.0

    def load(self) -> bool:
        """Load or reload the hotlist from disk."""
        if not self.file_path.exists():
            logger.warning("Hotlist file not found: %s", self.file_path)
            return False

        try:
            mtime = os.path.getmtime(self.file_path)
        except OSError:
            logger.error("Cannot stat hotlist file: %s", self.file_path)
            return False

        new_plates: dict[str, dict] = {}
        try:
            with open(self.file_path, "r", newline="") as f:
                reader = csv.reader(f)
                for row_num, row in enumerate(reader, 1):
                    if not row or row[0].startswith("#"):
                        continue  # skip empty lines and comments
                    plate = self._normalize(row[0])
                    if not plate:
                        logger.warning("Hotlist line %d: empty plate, skipping", row_num)
                        continue
                    reason = row[1].strip() if len(row) > 1 else "unknown"
                    priority = row[2].strip() if len(row) > 2 else "normal"
                    new_plates[plate] = {"reason": reason, "priority": priority}
        except (csv.Error, UnicodeDecodeError, OSError):
            logger.exception("Failed to load hotlist CSV: %s", self.file_path)
            return False
        with open(self.file_path, "r", newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            for row_num, row in enumerate(reader, 1):
                if not row:
                    continue
                first_cell = row[0].strip()
                if not first_cell or first_cell.startswith("#"):
                    continue  # skip empty lines and comments

                plate = self._normalize(first_cell)
                if not plate:
                    logger.warning("Hotlist line %d: empty plate, skipping", row_num)
                    continue

                if plate in new_plates:
                    logger.warning("Hotlist line %d: duplicate plate %s, overriding prior entry", row_num, plate)

                reason = row[1].strip() if len(row) > 1 and row[1].strip() else "unknown"
                priority = row[2].strip() if len(row) > 2 and row[2].strip() else "normal"
                new_plates[plate] = {"reason": reason, "priority": priority}

        self._plates = new_plates
        self._plate_set = set(new_plates.keys())
        self._last_mtime = mtime

        logger.info("Hotlist loaded: %d plates from %s", len(self._plates), self.file_path)
        return True

    def check_reload(self) -> bool:
        """Check if file has been modified and reload if needed."""
        if not self.file_path.exists():
            return False
        try:
            current_mtime = os.path.getmtime(self.file_path)
        except OSError:
            return False

        if current_mtime > self._last_mtime:
            logger.info("Hotlist file changed, reloading")
            loaded = self.load()
            if not loaded:
                logger.warning("Hotlist reload failed; continuing with previous in-memory hotlist")
            return loaded
        return False

    @staticmethod
    def _normalize(plate: str) -> str:
        """Normalize a plate string: uppercase, strip spaces and non-alnum."""
        return _PLATE_NORMALIZE_RE.sub("", plate.upper().strip())

    @property
    def plates(self) -> set[str]:
        return self._plate_set

    def get_info(self, plate: str) -> dict | None:
        """Get reason/priority for a plate."""
        return self._plates.get(self._normalize(plate))

    @property
    def count(self) -> int:
        return len(self._plates)
