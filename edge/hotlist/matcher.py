"""
Hotlist matcher: checks OCR results against in-memory hotlist.

Enforces 60-second cooldown per plate to prevent alert spam.
"""

import logging
import re
import time
from dataclasses import dataclass

from edge.hotlist.loader import HotlistLoader
from edge.inference.ocr import OCRResult

logger = logging.getLogger(__name__)

_PLATE_NORMALIZE_RE = re.compile(r"[^A-Z0-9]")


@dataclass
class HotlistAlert:
    """A hotlist match event."""
    plate: str
    reason: str
    priority: str
    confidence: float
    camera_id: str
    timestamp: float
    track_id: int | None = None


class HotlistMatcher:
    """
    Matches detected plates against the hotlist with cooldown.

    - Normalizes plate text before lookup
    - In-memory set for O(1) lookup
    - 60-second cooldown per plate to prevent duplicate alerts
    """

    def __init__(self, loader: HotlistLoader, cooldown_sec: int = 60):
        self.loader = loader
        self.cooldown_sec = max(0, int(cooldown_sec))
        self._last_alert_time: dict[str, float] = {}

    def check(
        self,
        ocr_results: list[OCRResult],
        camera_id: str,
        track_id: int | None = None,
    ) -> list[HotlistAlert]:
        """
        Check OCR results against the hotlist.

        Returns list of HotlistAlert for any matches not in cooldown.
        """
        alerts: list[HotlistAlert] = []
        for result in ocr_results:
            alert = self._match_normalized_plate(
                plate_text=result.text,
                camera_id=camera_id,
                confidence=result.confidence,
                track_id=track_id,
            )
            if alert is not None:
                alerts.append(alert)
        return alerts

    @staticmethod
    def _normalize(plate: str) -> str:
        return _PLATE_NORMALIZE_RE.sub("", plate.upper().strip())

    def clear_cooldowns(self):
        """Clear all cooldown timers."""
        self._last_alert_time.clear()

    def match_plate(
        self,
        plate_text: str,
        camera_id: str,
        confidence: float = 1.0,
        track_id: int | None = None,
    ) -> list[HotlistAlert]:
        """
        Convenience wrapper to check a single raw plate string.

        Normalises the text, respects the per-plate cooldown, and returns
        HotlistAlert objects — same semantics as check() but for a single
        pre-confirmed plate rather than a list of OCRResult objects.
        """
        alert = self._match_normalized_plate(
            plate_text=plate_text,
            camera_id=camera_id,
            confidence=confidence,
            track_id=track_id,
        )
        return [alert] if alert is not None else []

    def _match_normalized_plate(
        self,
        plate_text: str,
        camera_id: str,
        confidence: float,
        track_id: int | None,
    ) -> HotlistAlert | None:
        """Shared match/cooldown implementation for single-plate checks."""
        self._prune_expired_cooldowns()

        plate = self._normalize(plate_text)
        if not plate or plate not in self.loader.plates:
            return None

        now = time.monotonic()
        last_time = self._last_alert_time.get(plate, 0.0)
        if (now - last_time) < self.cooldown_sec:
            logger.debug(
                "Hotlist match for %s suppressed (cooldown, %.0fs remaining)",
                plate, self.cooldown_sec - (now - last_time),
            )
            return None

        info = self.loader.get_info(plate) or {}
        alert = HotlistAlert(
            plate=plate,
            reason=info.get("reason", "unknown"),
            priority=info.get("priority", "normal"),
            confidence=confidence,
            camera_id=camera_id,
            timestamp=time.time(),
            track_id=track_id,
        )
        self._last_alert_time[plate] = now

        logger.warning(
            "HOTLIST MATCH: %s (reason=%s, priority=%s, conf=%.2f, cam=%s)",
            plate, alert.reason, alert.priority, alert.confidence, camera_id,
        )
        return alert

    def _prune_expired_cooldowns(self):
        """Bound cooldown map growth by removing expired entries."""
        if not self._last_alert_time:
            return
        now = time.monotonic()
        expired = [
            plate for plate, ts in self._last_alert_time.items()
            if (now - ts) >= self.cooldown_sec
        ]
        for plate in expired:
            self._last_alert_time.pop(plate, None)

    @property
    def active_cooldowns(self) -> int:
        self._prune_expired_cooldowns()
        return len(self._last_alert_time)
