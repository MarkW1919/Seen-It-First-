"""Main camera controller that orchestrates all camera subsystems."""
import asyncio
import json
import logging
import os
import time

import cv2
import numpy as np
import yaml

from camera.capture import VideoCapture
from camera.ptz import PTZController
from camera.night_vision import NightVisionController
from camera.preprocessor import ImagePreprocessor
from camera.rtsp_server import RTSPServer
from camera.calibration import CameraCalibration

logger = logging.getLogger(__name__)


class CameraController:
    """Main controller that integrates all camera subsystems."""

    def __init__(self, config_path: str = "config.yaml"):
        with open(config_path) as f:
            self.config = yaml.safe_load(f)

        self.capture = VideoCapture(self.config)
        self.ptz = PTZController(self.config.get("ptz", {}))
        self.night_vision = NightVisionController(self.config.get("night_vision", {}))
        self.preprocessor = ImagePreprocessor(self.config)
        self.rtsp = RTSPServer(self.config)
        self.calibration = CameraCalibration()

        self._running = False

    def start(self):
        """Start all camera subsystems."""
        logger.info("Starting camera controller...")

        # Start video capture
        if not self.capture.start():
            logger.error("Failed to start video capture")
            return False

        # Start RTSP streaming
        self.rtsp.start()

        # Start night vision auto-monitoring
        self.night_vision.start_auto_monitoring(self.capture.read)

        self._running = True
        logger.info("Camera controller started")
        return True

    def get_frame(self, preprocess: bool = True) -> np.ndarray | None:
        """Get the latest preprocessed frame.

        Args:
            preprocess: Apply CLAHE/denoise preprocessing

        Returns:
            BGR frame or None
        """
        frame = self.capture.read()
        if frame is None:
            return None

        # Apply distortion correction
        if self.calibration.is_calibrated:
            frame = self.calibration.undistort(frame)

        # Apply preprocessing
        if preprocess:
            frame = self.preprocessor.process(frame)

        return frame

    def get_status(self) -> dict:
        """Get current camera status."""
        return {
            "is_connected": self.capture.is_running,
            "resolution": f"{self.config['camera']['width']}x{self.config['camera']['height']}",
            "fps": self.capture.actual_fps,
            "night_mode": self.night_vision.is_night_mode,
            "ir_enabled": self.night_vision.is_ir_enabled,
            "ptz_position": self.ptz.position,
            "streaming": self.rtsp.is_running,
            "rtsp_url": self.rtsp.url if self.rtsp.is_running else None,
        }

    def stop(self):
        """Stop all camera subsystems."""
        self._running = False
        self.capture.stop()
        self.rtsp.stop()
        self.night_vision.stop()
        self.ptz.close()
        logger.info("Camera controller stopped")


async def main():
    """Main entry point for the camera service.

    Captures frames and publishes them to Redis for the AI pipeline.
    Also publishes camera status updates.
    """
    logging.basicConfig(level=logging.INFO)

    config_path = os.environ.get("CAMERA_CONFIG", "config.yaml")
    controller = CameraController(config_path)

    if not controller.start():
        logger.error("Failed to start camera controller")
        return

    # Connect to Redis for frame publishing
    import redis.asyncio as aioredis

    redis_url = os.environ.get("REDIS_URL", "redis://redis:6379/0")
    redis_client = aioredis.from_url(redis_url)

    frame_interval = 1.0 / controller.config["camera"].get("fps", 30)
    status_interval = 5.0
    last_status = 0

    try:
        while True:
            frame = controller.get_frame(preprocess=True)

            if frame is not None:
                # Encode frame for Redis transport
                _, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
                frame_hex = buffer.tobytes().hex()

                frame_data = json.dumps({
                    "frame": frame_hex,
                    "timestamp": time.time(),
                })

                await redis_client.publish("reposcan:frames", frame_data)

            # Publish status periodically
            now = time.time()
            if now - last_status > status_interval:
                status = controller.get_status()
                await redis_client.publish(
                    "reposcan:alerts",
                    json.dumps({"type": "system:camera", "data": status}),
                )
                last_status = now

            await asyncio.sleep(frame_interval)

    except asyncio.CancelledError:
        pass
    finally:
        controller.stop()
        await redis_client.close()


if __name__ == "__main__":
    asyncio.run(main())
