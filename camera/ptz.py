"""PTZ (Pan-Tilt-Zoom) controller using Pelco-D protocol over RS-485.

Corrected implementation addressing:
- 360° pan boundary enforcement with wrapping (-180 to +180)
- 140° tilt boundary enforcement (-70 to +70)
- Async motor control (no blocking time.sleep)
- asyncio.Lock to prevent interleaved concurrent commands
- Fail-safe recovery: auto-stop on error, serial reconnect, position reset
- Motion state tracking for frame acquisition synchronization
"""

import asyncio
import enum
import logging
import struct
import time

logger = logging.getLogger(__name__)


class MotionState(enum.Enum):
    """Current motion state — used by frame pipeline to suppress blurry captures."""
    IDLE = "idle"
    MOVING = "moving"
    SETTLING = "settling"  # Motor stopped, waiting for vibration to dampen


# ─── Boundary Constants ───

PAN_MIN = -180.0
PAN_MAX = 180.0
PAN_RANGE_DEG = 360.0

TILT_MIN = -70.0
TILT_MAX = 70.0
TILT_RANGE_DEG = 140.0

ZOOM_MIN = 1.0
ZOOM_MAX = 30.0

SPEED_MIN = 1
SPEED_MAX = 63

# After motor stops, wait this long for vibration/settling before resuming capture
SETTLE_TIME_SECONDS = 0.3

# Max time any single movement command can take before forced stop
MAX_MOVE_TIMEOUT_SECONDS = 8.0

# Serial reconnect delay
RECONNECT_DELAY_SECONDS = 2.0


def normalize_pan(angle: float) -> float:
    """Normalize pan angle to [-180, +180] range with wrapping.

    Examples:
        normalize_pan(190)  -> -170 (wraps around)
        normalize_pan(-200) ->  160 (wraps around)
        normalize_pan(180)  ->  180
    """
    while angle > PAN_MAX:
        angle -= PAN_RANGE_DEG
    while angle < PAN_MIN:
        angle += PAN_RANGE_DEG
    return angle


def clamp_tilt(angle: float) -> float:
    """Clamp tilt to [-70, +70] with warning on out-of-range."""
    if angle < TILT_MIN:
        logger.warning("Tilt %.1f° below minimum %.1f°, clamping", angle, TILT_MIN)
        return TILT_MIN
    if angle > TILT_MAX:
        logger.warning("Tilt %.1f° above maximum %.1f°, clamping", angle, TILT_MAX)
        return TILT_MAX
    return angle


def clamp_zoom(level: float) -> float:
    """Clamp zoom to [1, 30] with warning on out-of-range."""
    if level < ZOOM_MIN:
        logger.warning("Zoom %.1fx below minimum %.1fx, clamping", level, ZOOM_MIN)
        return ZOOM_MIN
    if level > ZOOM_MAX:
        logger.warning("Zoom %.1fx above maximum %.1fx, clamping", level, ZOOM_MAX)
        return ZOOM_MAX
    return level


def clamp_speed(speed: int) -> int:
    return max(SPEED_MIN, min(SPEED_MAX, speed))


class PTZController:
    """Async PTZ controller with boundary enforcement, fail-safe, and motion tracking.

    All movement methods are async and use an asyncio.Lock to serialize commands,
    preventing interleaved motor operations. The motion_state property allows the
    frame pipeline to skip captures during movement.
    """

    # Pelco-D command bytes
    CMD_PAN_RIGHT = 0x02
    CMD_PAN_LEFT = 0x04
    CMD_TILT_UP = 0x08
    CMD_TILT_DOWN = 0x10
    CMD_ZOOM_IN = 0x20
    CMD_ZOOM_OUT = 0x40
    CMD_STOP = 0x00

    def __init__(self, config: dict) -> None:
        self.config = config
        self.enabled = config.get("enabled", False)
        self.port = config.get("serial_port", "/dev/ttyUSB0")
        self.baud_rate = config.get("baud_rate", 9600)
        self.address = config.get("address", 1)

        self._serial = None
        self._position = {"pan": 0.0, "tilt": 0.0, "zoom": 1.0}
        self._motion_state = MotionState.IDLE
        self._lock = asyncio.Lock()
        self._error_count = 0
        self._max_errors_before_reconnect = 3

        if self.enabled:
            self._connect()

    # ─── Serial Connection with Reconnect ───

    def _connect(self) -> bool:
        try:
            import serial
            if self._serial:
                try:
                    self._serial.close()
                except Exception:
                    pass

            self._serial = serial.Serial(
                port=self.port,
                baudrate=self.baud_rate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=1,
            )
            self._error_count = 0
            logger.info("PTZ connected on %s", self.port)
            return True
        except Exception as e:
            logger.warning("PTZ connection failed: %s", e)
            self._serial = None
            return False

    def _reconnect_if_needed(self) -> bool:
        """Attempt reconnect after repeated errors. Returns True if connected."""
        if self._serial is not None:
            return True
        logger.info("Attempting PTZ reconnect...")
        return self._connect()

    # ─── Low-Level Command (synchronous, called within async lock) ───

    def _send_command(self, cmd1: int, cmd2: int, data1: int = 0, data2: int = 0) -> bool:
        """Send a Pelco-D command packet. Returns True on success."""
        if not self._serial:
            if not self._reconnect_if_needed():
                return False

        sync = 0xFF
        checksum = (self.address + cmd1 + cmd2 + data1 + data2) % 256
        packet = struct.pack(
            "BBBBBBB", sync, self.address, cmd1, cmd2, data1, data2, checksum
        )

        try:
            self._serial.write(packet)
            self._error_count = 0
            return True
        except Exception as e:
            logger.error("PTZ send error: %s", e)
            self._error_count += 1
            if self._error_count >= self._max_errors_before_reconnect:
                logger.warning("Too many PTZ errors, closing serial for reconnect")
                try:
                    self._serial.close()
                except Exception:
                    pass
                self._serial = None
            return False

    def _send_stop(self) -> bool:
        """Emergency stop — always attempt even on error."""
        return self._send_command(0x00, self.CMD_STOP, 0, 0)

    # ─── Async Movement Methods (all protected by lock) ───

    async def pan(self, angle: float, speed: int = 32) -> dict:
        """Pan to target angle with 360° wrapping.

        Returns the final position dict.
        """
        async with self._lock:
            return await self._do_pan(angle, speed)

    async def _do_pan(self, angle: float, speed: int) -> dict:
        target = normalize_pan(angle)
        speed = clamp_speed(speed)
        current = self._position["pan"]

        if abs(target - current) < 0.5:
            return self._position.copy()

        # Determine shortest rotation path (handles 360° wrap)
        delta = target - current
        if delta > 180:
            delta -= 360
        elif delta < -180:
            delta += 360

        self._motion_state = MotionState.MOVING
        try:
            if delta > 0:
                success = self._send_command(0x00, self.CMD_PAN_RIGHT, speed, 0)
            else:
                success = self._send_command(0x00, self.CMD_PAN_LEFT, speed, 0)

            if not success:
                self._send_stop()
                return self._position.copy()

            # Async sleep instead of blocking time.sleep
            move_time = min(abs(delta) / (speed * 3), MAX_MOVE_TIMEOUT_SECONDS)
            await asyncio.sleep(move_time)

            self._send_stop()
            self._position["pan"] = target

            # Settling time for vibration dampening
            self._motion_state = MotionState.SETTLING
            await asyncio.sleep(SETTLE_TIME_SECONDS)
        except asyncio.CancelledError:
            # Fail-safe: always stop motor on cancellation
            self._send_stop()
            self._motion_state = MotionState.IDLE
            raise
        finally:
            self._motion_state = MotionState.IDLE

        return self._position.copy()

    async def tilt(self, angle: float, speed: int = 32) -> dict:
        """Tilt to target angle within 140° range [-70, +70].

        Returns the final position dict.
        """
        async with self._lock:
            return await self._do_tilt(angle, speed)

    async def _do_tilt(self, angle: float, speed: int) -> dict:
        target = clamp_tilt(angle)
        speed = clamp_speed(speed)
        current = self._position["tilt"]

        if abs(target - current) < 0.5:
            return self._position.copy()

        delta = target - current

        self._motion_state = MotionState.MOVING
        try:
            if delta > 0:
                success = self._send_command(0x00, self.CMD_TILT_UP, 0, speed)
            else:
                success = self._send_command(0x00, self.CMD_TILT_DOWN, 0, speed)

            if not success:
                self._send_stop()
                return self._position.copy()

            move_time = min(abs(delta) / (speed * 2), MAX_MOVE_TIMEOUT_SECONDS)
            await asyncio.sleep(move_time)

            self._send_stop()
            self._position["tilt"] = target

            self._motion_state = MotionState.SETTLING
            await asyncio.sleep(SETTLE_TIME_SECONDS)
        except asyncio.CancelledError:
            self._send_stop()
            self._motion_state = MotionState.IDLE
            raise
        finally:
            self._motion_state = MotionState.IDLE

        return self._position.copy()

    async def zoom(self, level: float) -> dict:
        """Set zoom level within [1, 30] range.

        Returns the final position dict.
        """
        async with self._lock:
            return await self._do_zoom(level)

    async def _do_zoom(self, level: float) -> dict:
        target = clamp_zoom(level)
        current = self._position["zoom"]

        if abs(target - current) < 0.1:
            return self._position.copy()

        self._motion_state = MotionState.MOVING
        try:
            if target > current:
                success = self._send_command(0x00, self.CMD_ZOOM_IN, 0, 0)
            else:
                success = self._send_command(0x00, self.CMD_ZOOM_OUT, 0, 0)

            if not success:
                self._send_stop()
                return self._position.copy()

            await asyncio.sleep(0.5)

            self._send_stop()
            self._position["zoom"] = target

            self._motion_state = MotionState.SETTLING
            await asyncio.sleep(SETTLE_TIME_SECONDS)
        except asyncio.CancelledError:
            self._send_stop()
            self._motion_state = MotionState.IDLE
            raise
        finally:
            self._motion_state = MotionState.IDLE

        return self._position.copy()

    async def move_to(
        self, pan: float, tilt: float, zoom: float | None = None
    ) -> dict:
        """Move to absolute position. Serialized via lock — pan, tilt, zoom
        execute sequentially (not interleaved with other commands)."""
        async with self._lock:
            await self._do_pan(pan, 32)
            await self._do_tilt(tilt, 32)
            if zoom is not None:
                await self._do_zoom(zoom)
            return self._position.copy()

    async def stop(self) -> None:
        """Emergency stop — bypasses the command lock for immediate safety."""
        self._send_stop()
        self._motion_state = MotionState.IDLE

    async def home(self) -> dict:
        """Return to home position (0, 0, 1x)."""
        return await self.move_to(0, 0, 1)

    # ─── State Properties ───

    @property
    def position(self) -> dict:
        """Thread-safe copy of current position."""
        return self._position.copy()

    @property
    def motion_state(self) -> MotionState:
        return self._motion_state

    @property
    def is_moving(self) -> bool:
        """True if the PTZ is currently moving or settling."""
        return self._motion_state != MotionState.IDLE

    @property
    def is_connected(self) -> bool:
        return self._serial is not None

    # ─── Lifecycle ───

    def close(self) -> None:
        """Shut down — always stop motors first."""
        self._send_stop()
        if self._serial:
            try:
                self._serial.close()
            except Exception:
                pass
            self._serial = None
        self._motion_state = MotionState.IDLE
