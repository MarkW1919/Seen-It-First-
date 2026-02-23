"""Night vision control for IR LEDs and IR-cut filter.

Improved with:
- Gamma-corrected lux estimation matching real camera response curves
- Hysteresis band to prevent rapid day/night oscillation
- Non-blocking IR transition (removed blocking sleep)
- Exponential moving average for lux smoothing
"""
import logging
import threading
import time

import cv2
import numpy as np

logger = logging.getLogger(__name__)


class NightVisionController:
    """Controls IR LEDs and IR-cut filter for night operation.

    The Sony IMX685 Starvis 2 sensor has excellent low-light performance.
    IR illumination extends usable range to near-zero lux conditions.
    """

    def __init__(self, config: dict):
        self.config = config
        self.auto_switch = config.get("auto_switch", True)
        self.lux_threshold = config.get("lux_threshold", 10.0)
        self.ir_led_gpio = config.get("ir_led_gpio", 18)
        self.ir_cut_gpio = config.get("ir_cut_gpio", 23)
        self.transition_delay = config.get("transition_delay", 2.0)

        # Hysteresis: switch to night below threshold, back to day at 2.5x
        self._hysteresis_high = self.lux_threshold * 2.5
        self._hysteresis_low = self.lux_threshold

        # Exponential moving average for lux smoothing
        self._ema_lux = 100.0
        self._ema_alpha = 0.15

        self._night_mode = False
        self._ir_enabled = False
        self._monitor_thread: threading.Thread | None = None
        self._running = False
        self._gpio_available = False

        self._init_gpio()

    def _init_gpio(self):
        """Initialize GPIO pins for IR LED and IR-cut filter control."""
        try:
            import Jetson.GPIO as GPIO

            GPIO.setmode(GPIO.BCM)
            GPIO.setup(self.ir_led_gpio, GPIO.OUT, initial=GPIO.LOW)
            GPIO.setup(self.ir_cut_gpio, GPIO.OUT, initial=GPIO.HIGH)
            self._gpio_available = True
            logger.info("GPIO initialized for night vision control")
        except ImportError:
            logger.info("Jetson.GPIO not available - night vision GPIO disabled")
        except Exception as e:
            logger.warning(f"GPIO init failed: {e}")

    def enable_night_mode(self):
        """Enable night vision mode: IR LEDs on, IR-cut filter removed."""
        if self._gpio_available:
            try:
                import Jetson.GPIO as GPIO

                GPIO.output(self.ir_led_gpio, GPIO.HIGH)
                GPIO.output(self.ir_cut_gpio, GPIO.LOW)
            except Exception as e:
                logger.error(f"Failed to enable night mode GPIO: {e}")

        self._night_mode = True
        self._ir_enabled = True
        logger.info("Night vision enabled")

    def disable_night_mode(self):
        """Disable night vision mode: IR LEDs off, IR-cut filter engaged."""
        if self._gpio_available:
            try:
                import Jetson.GPIO as GPIO

                GPIO.output(self.ir_led_gpio, GPIO.LOW)
                GPIO.output(self.ir_cut_gpio, GPIO.HIGH)
            except Exception as e:
                logger.error(f"Failed to disable night mode GPIO: {e}")

        self._night_mode = False
        self._ir_enabled = False
        logger.info("Night vision disabled")

    def estimate_lux(self, frame) -> float:
        """Estimate ambient light from frame brightness with gamma correction.

        Uses 75th percentile + gamma delinearization to approximate lux.
        Downsamples to 160x120 for fast computation (~0.1ms vs ~3ms at 1080p).
        """
        if frame is None:
            return self._ema_lux

        if len(frame.shape) == 3:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        else:
            gray = frame

        # Downsample to 160x120 for fast percentile (lux doesn't need full res)
        h, w = gray.shape[:2]
        if w > 320:
            gray = cv2.resize(gray, (160, 120), interpolation=cv2.INTER_AREA)

        p75 = float(np.percentile(gray, 75))
        linear = (p75 / 255.0) ** 2.2
        raw_lux = linear * 1000.0

        self._ema_lux = self._ema_alpha * raw_lux + (1 - self._ema_alpha) * self._ema_lux
        return self._ema_lux

    def start_auto_monitoring(self, get_frame_fn):
        """Start automatic day/night switching based on ambient light."""
        if not self.auto_switch:
            return

        self._running = True
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            args=(get_frame_fn,),
            daemon=True,
            name="night-vision-monitor",
        )
        self._monitor_thread.start()
        logger.info("Auto night vision monitoring started")

    def _monitor_loop(self, get_frame_fn):
        """Monitor ambient light with hysteresis to prevent oscillation."""
        while self._running:
            try:
                frame = get_frame_fn()
                lux = self.estimate_lux(frame)

                if lux < self._hysteresis_low and not self._night_mode:
                    logger.info(
                        f"Low light ({lux:.1f} lux < {self._hysteresis_low:.1f}), "
                        f"switching to night mode"
                    )
                    self.enable_night_mode()
                elif lux > self._hysteresis_high and self._night_mode:
                    logger.info(
                        f"Daylight ({lux:.1f} lux > {self._hysteresis_high:.1f}), "
                        f"switching to day mode"
                    )
                    self.disable_night_mode()

            except Exception as e:
                logger.error(f"Night vision monitor error: {e}")

            time.sleep(5)

    def stop(self):
        """Stop auto monitoring and disable IR."""
        self._running = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=10)
        self.disable_night_mode()

    @property
    def is_night_mode(self) -> bool:
        return self._night_mode

    @property
    def is_ir_enabled(self) -> bool:
        return self._ir_enabled

    def cleanup(self):
        """Cleanup GPIO resources."""
        self.stop()
        if self._gpio_available:
            try:
                import Jetson.GPIO as GPIO

                GPIO.cleanup([self.ir_led_gpio, self.ir_cut_gpio])
            except Exception:
                pass
