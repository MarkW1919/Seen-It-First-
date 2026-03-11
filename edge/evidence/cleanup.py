"""
Evidence file retention manager.

Runs a background thread that sweeps the evidence directories every
12 hours and removes files older than the configured retention period
(default 30 days).  Empty date directories are pruned after each sweep.

No inference code is blocked — the sweep thread is fully independent.
"""

import logging
import threading
import time
from pathlib import Path

logger = logging.getLogger(__name__)

_DEFAULT_ROOT           = Path("data/evidence")
_DEFAULT_RETENTION_DAYS = 30
_CHECK_INTERVAL_S       = 12 * 3600   # 12 hours
_CATEGORIES             = ("vehicles", "plates", "composite")
_IMAGE_SUFFIXES         = (".jpg", ".jpeg")


class MediaRetentionManager:
    """
    Periodic cleanup of old evidence image files.

    Usage::

        mgr = MediaRetentionManager("data/evidence", retention_days=30)
        mgr.start()          # launches background sweep thread
        # … at shutdown …
        mgr.stop()
    """

    def __init__(
        self,
        evidence_root: str | Path | None = None,
        retention_days: int = _DEFAULT_RETENTION_DAYS,
    ):
        self._root           = Path(evidence_root) if evidence_root else _DEFAULT_ROOT
        self._retention_days = max(1, int(retention_days))
        if retention_days < 1:
            logger.warning("Invalid retention_days=%s; defaulting to 1 day", retention_days)
        self._stop_event     = threading.Event()
        self._thread: threading.Thread | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self):
        """Start the background sweep thread (daemon, non-blocking)."""
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="evidence-cleanup",
            daemon=True,
        )
        self._thread.start()
        logger.info(
            "MediaRetentionManager started (retention=%d days, interval=12h)",
            self._retention_days,
        )

    def stop(self, join_timeout_s: float = 2.0):
        """Signal the sweep thread to exit and optionally wait briefly."""
        self._stop_event.set()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=max(0.0, join_timeout_s))

    def run_once(self):
        """
        Execute a single cleanup sweep immediately (blocking).

        Useful for testing or forced cleanup at startup.
        """
        self._cleanup()

    # ------------------------------------------------------------------
    # Background loop
    # ------------------------------------------------------------------

    def _run(self):
        """Thread body: wait _CHECK_INTERVAL_S between sweeps."""
        # Run an immediate first sweep at startup
        self._cleanup()
        while not self._stop_event.wait(timeout=_CHECK_INTERVAL_S):
            self._cleanup()

    # ------------------------------------------------------------------
    # Cleanup logic
    # ------------------------------------------------------------------

    def _cleanup(self):
        """Delete files older than retention period and prune empty dirs."""
        cutoff = time.time() - (self._retention_days * 86_400)
        removed = 0
        errors  = 0

        for category in _CATEGORIES:
            cat_dir = self._root / category
            if not cat_dir.exists():
                continue

            for file_path in cat_dir.rglob("*"):
                if not file_path.is_file() or file_path.suffix.lower() not in _IMAGE_SUFFIXES:
                    continue
                try:
                    if file_path.stat().st_mtime < cutoff:
                        file_path.unlink()
                        removed += 1
                except FileNotFoundError:
                    pass  # already deleted by another process — fine
                except OSError:
                    logger.warning("Could not remove evidence file: %s", file_path)
                    errors += 1

        if removed:
            logger.info(
                "Evidence cleanup: removed %d file(s) older than %d days "
                "(errors=%d)",
                removed, self._retention_days, errors,
            )
        else:
            logger.debug(
                "Evidence cleanup: no files older than %d days",
                self._retention_days,
            )

        self._prune_empty_dirs()

    def _prune_empty_dirs(self):
        """Remove date/month/year directories that are now empty."""
        for category in _CATEGORIES:
            cat_dir = self._root / category
            if not cat_dir.exists():
                continue

            # Walk deepest-first so children are removed before parents
            for dir_path in sorted(cat_dir.rglob("*"), reverse=True):
                if dir_path.is_dir() and dir_path != cat_dir:
                    try:
                        dir_path.rmdir()   # no-op if non-empty
                    except OSError:
                        pass               # directory not empty — skip
