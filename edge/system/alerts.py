"""
Alert output: console logging and audio beep on hotlist match.
"""

import logging
import subprocess
import sys
import threading

from edge.hotlist.matcher import HotlistAlert

logger = logging.getLogger(__name__)


class AlertManager:
    """
    Handles alert output for hotlist matches.

    - Console: prints colored alert to stdout
    - Audio: plays a beep via system speaker (aplay or paplay)
    """

    def __init__(self, config: dict):
        self.audio_enabled = config.get("audio_alert", True)
        self.beep_freq = config.get("beep_frequency", 1000)
        self.beep_duration_ms = config.get("beep_duration_ms", 500)
        self._alert_count = 0

    def fire_alert(self, alert: HotlistAlert):
        """Process a hotlist alert: console output + optional audio."""
        self._alert_count += 1

        # Console alert
        self._console_alert(alert)

        # Audio alert (non-blocking)
        if self.audio_enabled:
            threading.Thread(
                target=self._audio_beep,
                daemon=True,
            ).start()

    def _console_alert(self, alert: HotlistAlert):
        """Print a prominent console alert."""
        border = "=" * 60
        msg = (
            f"\n{border}\n"
            f"  HOTLIST ALERT  #{self._alert_count}\n"
            f"  Plate:      {alert.plate}\n"
            f"  Reason:     {alert.reason}\n"
            f"  Priority:   {alert.priority}\n"
            f"  Confidence: {alert.confidence:.1%}\n"
            f"  Camera:     {alert.camera_id}\n"
            f"{border}\n"
        )

        # Use ANSI colors if terminal supports it
        if sys.stdout.isatty():
            red = "\033[91m"
            bold = "\033[1m"
            reset = "\033[0m"
            msg = f"{red}{bold}{msg}{reset}"

        print(msg, flush=True)

    def _audio_beep(self):
        """Play a beep sound via system audio."""
        try:
            # Try beep command first (most common on embedded Linux)
            subprocess.run(
                [
                    "beep",
                    "-f", str(self.beep_freq),
                    "-l", str(self.beep_duration_ms),
                ],
                timeout=2,
                capture_output=True,
            )
        except FileNotFoundError:
            # Fallback: generate tone with sox/play
            try:
                duration_sec = self.beep_duration_ms / 1000.0
                subprocess.run(
                    [
                        "play", "-n", "synth",
                        str(duration_sec), "sine", str(self.beep_freq),
                    ],
                    timeout=2,
                    capture_output=True,
                )
            except FileNotFoundError:
                # Last resort: terminal bell
                print("\a", end="", flush=True)
            except subprocess.TimeoutExpired:
                pass
        except subprocess.TimeoutExpired:
            pass

    @property
    def alert_count(self) -> int:
        return self._alert_count
