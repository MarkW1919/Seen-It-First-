"""
SEEN IT FIRST - Structured Logging Module

Provides a logger factory that returns loggers configured with:
  - A rotating file handler emitting newline-delimited JSON.
  - A console (stderr) handler emitting human-readable output.

Uses Python stdlib logging only.

Usage:
    from edge.utils.logging import get_logger
    logger = get_logger(__name__)
    logger.info("Vehicle detected", extra={"plate": "ABC1234", "confidence": 0.92})
"""

from __future__ import annotations

import json
import logging
import logging.handlers
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


# ---------------------------------------------------------------------------
# JSON Formatter
# ---------------------------------------------------------------------------

class JSONFormatter(logging.Formatter):
    """
    Formats log records as single-line JSON objects.

    Always includes: timestamp, level, logger, message.
    Any *extra* fields passed via ``logger.info("msg", extra={...})`` are
    merged into the top-level JSON object under an ``"extra"`` key.
    """

    # Fields injected by the stdlib that we do not want in JSON output.
    _SKIP_FIELDS = frozenset({
        "args", "created", "exc_info", "exc_text", "filename", "funcName",
        "levelname", "levelno", "lineno", "module", "msecs", "msg", "name",
        "pathname", "process", "processName", "relativeCreated",
        "stack_info", "thread", "threadName", "taskName", "message",
    })

    def format(self, record: logging.LogRecord) -> str:
        log_entry: Dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Capture exception text if present
        if record.exc_info and record.exc_info[0] is not None:
            log_entry["exception"] = self.formatException(record.exc_info)

        if record.stack_info:
            log_entry["stack_info"] = self.formatStack(record.stack_info)

        # Merge extra fields
        extras: Dict[str, Any] = {}
        for key, value in record.__dict__.items():
            if key not in self._SKIP_FIELDS and not key.startswith("_"):
                extras[key] = value
        if extras:
            log_entry["extra"] = extras

        return json.dumps(log_entry, default=str, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Human-readable console formatter
# ---------------------------------------------------------------------------

class ConsoleFormatter(logging.Formatter):
    """
    Concise, coloured (when supported) formatter for console output.

    Format:  YYYY-MM-DD HH:MM:SS.mmm | LEVEL    | logger | message | {extras}
    """

    _LEVEL_COLORS = {
        "DEBUG": "\033[36m",      # cyan
        "INFO": "\033[32m",       # green
        "WARNING": "\033[33m",    # yellow
        "ERROR": "\033[31m",      # red
        "CRITICAL": "\033[1;31m", # bold red
    }
    _RESET = "\033[0m"

    def __init__(self, use_color: bool = True) -> None:
        super().__init__()
        self._use_color = use_color and _stream_supports_color(sys.stderr)

    def format(self, record: logging.LogRecord) -> str:
        ts = datetime.fromtimestamp(
            record.created, tz=timezone.utc
        ).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

        level = record.levelname.ljust(8)
        if self._use_color:
            color = self._LEVEL_COLORS.get(record.levelname, "")
            level = f"{color}{level}{self._RESET}"

        parts = [ts, level, record.name, record.getMessage()]

        # Append extras inline
        extras = _extract_extras(record)
        if extras:
            parts.append(json.dumps(extras, default=str, ensure_ascii=False))

        msg = " | ".join(parts)

        if record.exc_info and record.exc_info[0] is not None:
            msg += "\n" + self.formatException(record.exc_info)

        return msg


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Build the set of builtin LogRecord attributes so we can detect user extras.
_BUILTIN_ATTRS = frozenset(logging.LogRecord(
    name="", level=0, pathname="", lineno=0,
    msg="", args=(), exc_info=None,
).__dict__.keys()) | {"message"}


def _extract_extras(record: logging.LogRecord) -> Dict[str, Any]:
    """Return a dict of non-builtin attributes attached to *record*."""
    extras: Dict[str, Any] = {}
    for key, value in record.__dict__.items():
        if key not in _BUILTIN_ATTRS and not key.startswith("_"):
            extras[key] = value
    return extras


def _stream_supports_color(stream: Any) -> bool:
    """Return True if *stream* is attached to a TTY that supports ANSI."""
    if os.environ.get("NO_COLOR"):
        return False
    if not hasattr(stream, "isatty"):
        return False
    return stream.isatty()


# ---------------------------------------------------------------------------
# Setup / Factory
# ---------------------------------------------------------------------------

_logging_configured = False


def setup_logging(
    level: str = "INFO",
    log_file: Optional[str] = None,
    max_bytes: int = 10_485_760,
    backup_count: int = 5,
) -> None:
    """
    Configure the root ``sif`` logger hierarchy.

    This should be called once at application startup.  All loggers created
    via ``get_logger()`` are children of the ``sif`` root logger and inherit
    its handlers.

    Parameters
    ----------
    level : str
        Minimum log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
    log_file : str, optional
        Path to the JSON log file.  Parent directories are created
        automatically.  If ``None``, file logging is disabled.
    max_bytes : int
        Maximum size (bytes) of a single log file before rotation.
    backup_count : int
        Number of rotated backup files to keep.
    """
    global _logging_configured
    if _logging_configured:
        return

    root = logging.getLogger("sif")
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    root.propagate = False

    # Remove any pre-existing handlers to avoid duplicates on re-init
    root.handlers.clear()

    # Console handler -------------------------------------------------------
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setFormatter(ConsoleFormatter(use_color=True))
    root.addHandler(console_handler)

    # File handler (JSON) ---------------------------------------------------
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.handlers.RotatingFileHandler(
            filename=str(log_path),
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        file_handler.setFormatter(JSONFormatter())
        root.addHandler(file_handler)

    _logging_configured = True
    root.info("Logging initialised", extra={"level": level, "file": log_file})


def get_logger(name: str, level: Optional[int] = None) -> logging.Logger:
    """
    Return a logger that is a child of the ``sif`` hierarchy.

    Example::

        logger = get_logger("edge.camera.manager")
        # Actual logger name: sif.edge.camera.manager

    If ``setup_logging()`` has not been called yet, a basic console-only
    configuration is applied automatically so that early log messages are
    never lost.

    Parameters
    ----------
    name : str
        Dot-separated module name.  Will be prefixed with ``sif.``.
    level : int, optional
        Optional override for the logger level.

    Returns
    -------
    logging.Logger
    """
    if not _logging_configured:
        # Provide a minimal fallback so logs are never silently lost
        setup_logging(level="INFO")

    logger = logging.getLogger(f"sif.{name}")
    if level is not None:
        logger.setLevel(level)
    return logger
