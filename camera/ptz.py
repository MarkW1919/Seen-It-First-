"""PTZ (Pan-Tilt-Zoom) controller using Pelco-D protocol over RS-485."""
import logging
import struct
import time

logger = logging.getLogger(__name__)


class PTZController:
    """Control PTZ camera via RS-485 serial with Pelco-D protocol."""

    # Pelco-D commands
    CMD_PAN_RIGHT = 0x02
    CMD_PAN_LEFT = 0x04
    CMD_TILT_UP = 0x08
    CMD_TILT_DOWN = 0x10
    CMD_ZOOM_IN = 0x20
    CMD_ZOOM_OUT = 0x40
    CMD_STOP = 0x00

    def __init__(self, config: dict):
        self.config = config
        self.enabled = config.get("enabled", False)
        self.port = config.get("serial_port", "/dev/ttyUSB0")
        self.baud_rate = config.get("baud_rate", 9600)
        self.address = config.get("address", 1)
        self.pan_range = config.get("pan_range", [-170, 170])
        self.tilt_range = config.get("tilt_range", [-30, 90])
        self.zoom_range = config.get("zoom_range", [1, 30])

        self._serial = None
        self._position = {"pan": 0.0, "tilt": 0.0, "zoom": 1.0}

        if self.enabled:
            self._connect()

    def _connect(self):
        try:
            import serial

            self._serial = serial.Serial(
                port=self.port,
                baudrate=self.baud_rate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=1,
            )
            logger.info(f"PTZ connected on {self.port}")
        except Exception as e:
            logger.warning(f"PTZ connection failed: {e}")
            self._serial = None

    def _send_command(self, cmd1: int, cmd2: int, data1: int = 0, data2: int = 0):
        """Send a Pelco-D command packet."""
        if not self._serial:
            return

        sync = 0xFF
        checksum = (self.address + cmd1 + cmd2 + data1 + data2) % 256
        packet = struct.pack(
            "BBBBBBB", sync, self.address, cmd1, cmd2, data1, data2, checksum
        )

        try:
            self._serial.write(packet)
        except Exception as e:
            logger.error(f"PTZ send error: {e}")

    def pan(self, angle: float, speed: int = 32):
        """Pan to an angle (-170 to 170 degrees)."""
        angle = max(self.pan_range[0], min(self.pan_range[1], angle))
        speed = max(1, min(63, speed))

        if angle > self._position["pan"]:
            self._send_command(0x00, self.CMD_PAN_RIGHT, speed, 0)
        elif angle < self._position["pan"]:
            self._send_command(0x00, self.CMD_PAN_LEFT, speed, 0)

        # Estimate time to move (simplified)
        delta = abs(angle - self._position["pan"])
        move_time = delta / (speed * 3)  # Approximate degrees/sec
        time.sleep(min(move_time, 5))

        self.stop()
        self._position["pan"] = angle

    def tilt(self, angle: float, speed: int = 32):
        """Tilt to an angle (-30 to 90 degrees)."""
        angle = max(self.tilt_range[0], min(self.tilt_range[1], angle))
        speed = max(1, min(63, speed))

        if angle > self._position["tilt"]:
            self._send_command(0x00, self.CMD_TILT_UP, 0, speed)
        elif angle < self._position["tilt"]:
            self._send_command(0x00, self.CMD_TILT_DOWN, 0, speed)

        delta = abs(angle - self._position["tilt"])
        move_time = delta / (speed * 2)
        time.sleep(min(move_time, 5))

        self.stop()
        self._position["tilt"] = angle

    def zoom(self, level: float):
        """Set zoom level (1 to 30x)."""
        level = max(self.zoom_range[0], min(self.zoom_range[1], level))

        if level > self._position["zoom"]:
            self._send_command(0x00, self.CMD_ZOOM_IN, 0, 0)
        elif level < self._position["zoom"]:
            self._send_command(0x00, self.CMD_ZOOM_OUT, 0, 0)

        time.sleep(0.5)
        self.stop()
        self._position["zoom"] = level

    def move_to(self, pan: float, tilt: float, zoom: float | None = None):
        """Move to absolute position."""
        self.pan(pan)
        self.tilt(tilt)
        if zoom is not None:
            self.zoom(zoom)

    def stop(self):
        """Stop all PTZ movement."""
        self._send_command(0x00, self.CMD_STOP, 0, 0)

    def home(self):
        """Return to home position."""
        self.move_to(0, 0, 1)

    @property
    def position(self) -> dict:
        return self._position.copy()

    def close(self):
        if self._serial:
            self._serial.close()
            self._serial = None
