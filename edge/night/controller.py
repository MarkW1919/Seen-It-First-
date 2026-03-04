"""
SEEN IT FIRST - Edge AI Vehicle LPR System
Night mode controller for the Jetson Orin Nano Super deployment.

Automatically detects day/night transitions via frame brightness analysis
and controls IR LED illumination and IR cut filter via GPIO.  Provides
hysteresis to prevent flickering at the transition boundary.

GPIO control uses RPi.GPIO with a graceful fallback for development
environments that lack the Jetson GPIO header.
"""

from __future__ import annotations

import threading
from typing import Optional

import numpy as np

from edge.utils.logging import get_logger

logger = get_logger("night.controller")

# ---------------------------------------------------------------------------
# GPIO import with graceful fallback
# ---------------------------------------------------------------------------
_GPIO_AVAILABLE = False
try:
    import RPi.GPIO as GPIO  # type: ignore[import-untyped]
    _GPIO_AVAILABLE = True
    logger.info("RPi.GPIO loaded successfully -- hardware GPIO available")
except ImportError:
    GPIO = None  # type: ignore[assignment]
    logger.warning(
        "RPi.GPIO not available -- running without hardware GPIO control. "
        "Night mode state will still be tracked but IR LEDs / cut filter "
        "will not be actuated."
    )

# ---------------------------------------------------------------------------
# Default thresholds (0-255 brightness scale)
# ---------------------------------------------------------------------------
_DEFAULT_ACTIVATE_THRESHOLD = 60    # Enter night mode when brightness < 60
_DEFAULT_DEACTIVATE_THRESHOLD = 80  # Exit night mode when brightness > 80


class NightModeController:
    """Automatic day/night detector with GPIO-driven IR LED and cut filter control.

    The controller analyses the mean brightness of the center 50 % of every
    incoming frame.  Hysteresis prevents rapid toggling at dusk / dawn:

    * **Night activates** when brightness drops *below* ``activate_threshold``
      (default 60).
    * **Day resumes** when brightness rises *above* ``deactivate_threshold``
      (default 80).

    Parameters
    ----------
    ir_led_gpio_pin :
        BCM GPIO pin wired to the IR LED driver.
    ir_cut_gpio_pin :
        BCM GPIO pin wired to the IR cut filter solenoid.
    activate_threshold :
        Brightness (0-255) below which night mode engages.
    deactivate_threshold :
        Brightness (0-255) above which night mode disengages.
    """

    def __init__(
        self,
        ir_led_gpio_pin: int = 18,
        ir_cut_gpio_pin: int = 23,
        activate_threshold: int = _DEFAULT_ACTIVATE_THRESHOLD,
        deactivate_threshold: int = _DEFAULT_DEACTIVATE_THRESHOLD,
    ) -> None:
        self._ir_led_pin = ir_led_gpio_pin
        self._ir_cut_pin = ir_cut_gpio_pin
        self._activate_threshold = activate_threshold
        self._deactivate_threshold = deactivate_threshold

        self._night_mode: bool = False
        self._manual_override: Optional[bool] = None
        self._lock = threading.Lock()

        self._gpio_ready = False
        self._setup_gpio()

        logger.info(
            "NightModeController initialised | ir_led_pin=%d  ir_cut_pin=%d  "
            "activate_threshold=%d  deactivate_threshold=%d",
            self._ir_led_pin,
            self._ir_cut_pin,
            self._activate_threshold,
            self._deactivate_threshold,
        )

    # ------------------------------------------------------------------
    # GPIO setup
    # ------------------------------------------------------------------

    def _setup_gpio(self) -> None:
        """Initialise GPIO pins for IR LED and cut filter."""
        if not _GPIO_AVAILABLE:
            logger.warning("Skipping GPIO setup -- RPi.GPIO not available")
            return

        try:
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)
            GPIO.setup(self._ir_led_pin, GPIO.OUT, initial=GPIO.LOW)
            GPIO.setup(self._ir_cut_pin, GPIO.OUT, initial=GPIO.LOW)
            self._gpio_ready = True
            logger.info(
                "GPIO pins configured | ir_led_pin=%d (OUT)  ir_cut_pin=%d (OUT)",
                self._ir_led_pin,
                self._ir_cut_pin,
            )
        except Exception:
            logger.exception(
                "Failed to configure GPIO pins -- continuing without hardware control"
            )
            self._gpio_ready = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def is_night_mode(self) -> bool:
        """Thread-safe read of the current night mode state.

        If a manual override is active, returns the override value.
        """
        with self._lock:
            if self._manual_override is not None:
                return self._manual_override
            return self._night_mode

    def update(self, frame: np.ndarray) -> None:
        """Analyse *frame* brightness and update night mode state.

        Should be called once per captured frame.  The method computes the
        mean brightness of the center 50 % of the frame and applies the
        hysteresis thresholds.

        Parameters
        ----------
        frame :
            BGR image as a NumPy array (H x W x C).
        """
        brightness = self._compute_center_brightness(frame)

        with self._lock:
            # If a manual override is active, skip automatic detection
            if self._manual_override is not None:
                return

            previous = self._night_mode

            if not self._night_mode and brightness < self._activate_threshold:
                self._night_mode = True
            elif self._night_mode and brightness > self._deactivate_threshold:
                self._night_mode = False

            if self._night_mode != previous:
                transition = "DAY -> NIGHT" if self._night_mode else "NIGHT -> DAY"
                logger.info(
                    "Night mode transition: %s | brightness=%.1f  "
                    "activate_thr=%d  deactivate_thr=%d",
                    transition,
                    brightness,
                    self._activate_threshold,
                    self._deactivate_threshold,
                )
                self._apply_gpio(self._night_mode)

    def force_night_mode(self, enabled: bool) -> None:
        """Manually override night mode state.

        Parameters
        ----------
        enabled :
            ``True`` to force night mode on, ``False`` to force day mode.
        """
        with self._lock:
            previous_override = self._manual_override
            self._manual_override = enabled
            logger.info(
                "Manual override SET | forced_night_mode=%s  previous_override=%s",
                enabled,
                previous_override,
            )
            self._apply_gpio(enabled)

    def clear_override(self) -> None:
        """Remove the manual override and resume automatic brightness-based detection."""
        with self._lock:
            self._manual_override = None
            logger.info(
                "Manual override CLEARED | reverting to auto detection  "
                "current_auto_state=%s",
                self._night_mode,
            )
            self._apply_gpio(self._night_mode)

    def cleanup(self) -> None:
        """Release GPIO resources.  Safe to call even without GPIO."""
        if self._gpio_ready and _GPIO_AVAILABLE:
            try:
                GPIO.cleanup([self._ir_led_pin, self._ir_cut_pin])
                logger.info("GPIO pins cleaned up")
            except Exception:
                logger.exception("Error during GPIO cleanup")
        self._gpio_ready = False

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_center_brightness(frame: np.ndarray) -> float:
        """Return the mean brightness (0-255) of the center 50 % of *frame*.

        Converts to grayscale first so the result is independent of the
        colour channel encoding.
        """
        if frame is None or frame.size == 0:
            return 128.0  # Neutral fallback

        h, w = frame.shape[:2]

        # Center 50 % crop coordinates
        y_start = h // 4
        y_end = y_start + h // 2
        x_start = w // 4
        x_end = x_start + w // 2

        center_crop = frame[y_start:y_end, x_start:x_end]

        # Convert to grayscale if the image is multi-channel
        if len(center_crop.shape) == 3 and center_crop.shape[2] >= 3:
            try:
                import cv2
                gray = cv2.cvtColor(center_crop, cv2.COLOR_BGR2GRAY)
            except ImportError:
                # Manual luminance approximation: 0.299 R + 0.587 G + 0.114 B
                gray = (
                    0.114 * center_crop[:, :, 0].astype(np.float32)
                    + 0.587 * center_crop[:, :, 1].astype(np.float32)
                    + 0.299 * center_crop[:, :, 2].astype(np.float32)
                )
        else:
            gray = center_crop

        return float(np.mean(gray))

    def _apply_gpio(self, night_active: bool) -> None:
        """Set IR LED and IR cut filter GPIO pins.  Caller holds ``_lock``.

        * Night mode ON  -> IR LED HIGH, IR cut filter HIGH (removed)
        * Night mode OFF -> IR LED LOW,  IR cut filter LOW  (engaged)
        """
        if not self._gpio_ready or not _GPIO_AVAILABLE:
            return

        try:
            if night_active:
                GPIO.output(self._ir_led_pin, GPIO.HIGH)
                GPIO.output(self._ir_cut_pin, GPIO.HIGH)
                logger.debug(
                    "GPIO set | ir_led=HIGH  ir_cut=HIGH (night mode ON)"
                )
            else:
                GPIO.output(self._ir_led_pin, GPIO.LOW)
                GPIO.output(self._ir_cut_pin, GPIO.LOW)
                logger.debug(
                    "GPIO set | ir_led=LOW  ir_cut=LOW (day mode)"
                )
        except Exception:
            logger.exception("Failed to set GPIO outputs")
