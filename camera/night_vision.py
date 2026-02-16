"""Night vision control for IR LEDs and IR-cut filter."""
import logging
import threading
import time

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

        self._night_mode = False
        self._ir_enabled = False
        self._monitor_thread: threading.Thread | None = None
        self._running = False
        self._gpio_available = False

        self._init_gpio()

    def _init_gpio(self):
        """Initialize GPIO pins for IR LED and IR-cut filter control."""
        try:
            # Jetson.GPIO for Jetson platforms
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
        """Estimate ambient light level from frame brightness.

        This is a simplified estimation. In production, use a dedicated
        lux sensor (BH1750) for accurate readings.
        """
        import numpy as np

        if frame is None:
            return 100.0

        # Convert to grayscale and compute mean brightness
        if len(frame.shape) == 3:
            import cv2

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        else:
            gray = frame

        mean_brightness = float(np.mean(gray))

        # Rough mapping: 0-255 brightness -> 0-1000 lux (approximate)
        estimated_lux = (mean_brightness / 255.0) * 1000.0
        return estimated_lux

    def start_auto_monitoring(self, get_frame_fn):
        """Start automatic day/night switching based on ambient light."""
        if not self.auto_switch:
            return

        self._running = True
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            args=(get_frame_fn,),
            daemon=True,
        )
        self._monitor_thread.start()
        logger.info("Auto night vision monitoring started")

    def _monitor_loop(self, get_frame_fn):
        """Monitor ambient light and switch modes automatically."""
        while self._running:
            try:
                frame = get_frame_fn()
                lux = self.estimate_lux(frame)

                if lux < self.lux_threshold and not self._night_mode:
                    logger.info(f"Low light detected ({lux:.1f} lux), switching to night mode")
                    time.sleep(self.transition_delay)
                    self.enable_night_mode()
                elif lux > self.lux_threshold * 2 and self._night_mode:
                    logger.info(f"Daylight detected ({lux:.1f} lux), switching to day mode")
                    time.sleep(self.transition_delay)
                    self.disable_night_mode()

            except Exception as e:
                logger.error(f"Night vision monitor error: {e}")

            time.sleep(5)  # Check every 5 seconds

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
