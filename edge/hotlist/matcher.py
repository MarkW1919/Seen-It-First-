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
        self.cooldown_sec = cooldown_sec
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
        alerts = []
        now = time.monotonic()

        for result in ocr_results:
            plate = self._normalize(result.text)
            if not plate:
                continue

            if plate not in self.loader.plates:
                continue

            # Cooldown check
            last_time = self._last_alert_time.get(plate, 0.0)
            if (now - last_time) < self.cooldown_sec:
                logger.debug(
                    "Hotlist match for %s suppressed (cooldown, %.0fs remaining)",
                    plate, self.cooldown_sec - (now - last_time),
                )
                continue

            # Match found
            info = self.loader.get_info(plate) or {}
            alert = HotlistAlert(
                plate=plate,
                reason=info.get("reason", "unknown"),
                priority=info.get("priority", "normal"),
                confidence=result.confidence,
                camera_id=camera_id,
                timestamp=time.time(),
                track_id=track_id,
            )
            alerts.append(alert)
            self._last_alert_time[plate] = now

            logger.warning(
                "HOTLIST MATCH: %s (reason=%s, priority=%s, conf=%.2f, cam=%s)",
                plate, alert.reason, alert.priority, alert.confidence, camera_id,
            )

        return alerts

    @staticmethod
    def _normalize(plate: str) -> str:
        return re.sub(r"[^A-Z0-9]", "", plate.upper().strip())

    def clear_cooldowns(self):
        """Clear all cooldown timers."""
        self._last_alert_time.clear()

    @property
    def active_cooldowns(self) -> int:
        now = time.monotonic()
        return sum(
            1 for t in self._last_alert_time.values()
            if (now - t) < self.cooldown_sec
        )
