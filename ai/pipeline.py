"""Complete AI inference pipeline for RepoScan Pro.

Orchestrates vehicle detection, plate detection, OCR, classification,
and multi-object tracking into a single end-to-end pipeline.

Optimized for sustained 25-30 FPS on Jetson Orin Nano Super:
- Non-blocking async API dispatch (fire-and-forget)
- Frame-budget-aware processing with skip logic
- Thermal monitoring with automatic throttling
- Bounded detection history to prevent memory growth
"""
import asyncio
import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np
import yaml
import httpx

from ai.vehicle_detector import VehicleDetector
from ai.plate_detector import PlateDetector
from ai.plate_ocr import PlateOCR
from ai.vehicle_classifier import VehicleClassifier
from ai.tracker import MultiObjectTracker

logger = logging.getLogger(__name__)


class ThermalMonitor:
    """Monitor Jetson GPU/CPU temperature and throttle if needed."""

    THROTTLE_TEMP = 80.0
    RESUME_TEMP = 70.0
    THERMAL_ZONE = "/sys/devices/virtual/thermal/thermal_zone0/temp"

    def __init__(self):
        self._throttled = False
        self._last_check = 0.0
        self._check_interval = 2.0

    @property
    def is_throttled(self) -> bool:
        now = time.monotonic()
        if now - self._last_check < self._check_interval:
            return self._throttled
        self._last_check = now
        temp = self._read_temp()
        if temp is None:
            return False
        if temp >= self.THROTTLE_TEMP and not self._throttled:
            logger.warning(f"Thermal throttle engaged at {temp:.1f}C")
            self._throttled = True
        elif temp < self.RESUME_TEMP and self._throttled:
            logger.info(f"Thermal throttle released at {temp:.1f}C")
            self._throttled = False
        return self._throttled

    @property
    def temperature(self) -> float | None:
        return self._read_temp()

    def _read_temp(self) -> float | None:
        try:
            with open(self.THERMAL_ZONE) as f:
                return int(f.read().strip()) / 1000.0
        except (FileNotFoundError, ValueError, PermissionError):
            return None


class InferencePipeline:
    """End-to-end AI pipeline for vehicle and plate detection."""

    def __init__(self, config_path: str = "config.yaml"):
        try:
            with open(config_path) as f:
                self.config = yaml.safe_load(f)
        except FileNotFoundError:
            logger.error(f"Config file not found: {config_path}")
            raise
        except yaml.YAMLError as e:
            logger.error(f"Invalid YAML in {config_path}: {e}")
            raise

        precision = self.config.get("precision", "fp16")

        pipeline_cfg = self.config.get("pipeline", {})
        self.max_fps = pipeline_cfg.get("max_fps", 30)
        self.skip_frames = pipeline_cfg.get("skip_frames", 0)
        self.save_captures = pipeline_cfg.get("save_captures", True)
        self.capture_dir = Path(
            os.environ.get("CAPTURE_DIR", pipeline_cfg.get("capture_dir", "/data/captures"))
        )
        self.thumbnail_size = tuple(pipeline_cfg.get("thumbnail_size", [320, 240]))
        self.api_endpoint = pipeline_cfg.get(
            "api_endpoint", "http://backend:8000/api/detections/"
        )

        self.capture_dir.mkdir(parents=True, exist_ok=True)

        # Initialize models
        logger.info("Initializing AI pipeline...")
        self.vehicle_detector = VehicleDetector(self.config["vehicle_detector"])
        self.plate_detector = PlateDetector(self.config["plate_detector"])
        self.plate_ocr = PlateOCR(self.config["plate_ocr"])
        self.vehicle_classifier = VehicleClassifier(self.config["vehicle_classifier"])
        self.tracker = MultiObjectTracker(self.config.get("tracker", {}))
        self.thermal = ThermalMonitor()

        self._frame_count = 0
        self._api_token: str | None = None
        self._http_client = httpx.AsyncClient(
            timeout=5.0,
            limits=httpx.Limits(max_connections=4, max_keepalive_connections=2),
        )

        # Async detection dispatch queue (non-blocking sends)
        self._dispatch_queue: asyncio.Queue[dict] = asyncio.Queue(maxsize=64)
        self._dispatcher_task: asyncio.Task | None = None

        # Performance counters
        self._perf_sum_ms = 0.0
        self._perf_count = 0

        logger.info("AI pipeline initialized")

    async def start_dispatcher(self):
        """Start the background API dispatch task."""
        self._dispatcher_task = asyncio.create_task(self._dispatch_loop())

    async def _dispatch_loop(self):
        """Background task that sends detections to API without blocking pipeline."""
        while True:
            try:
                result = await self._dispatch_queue.get()
                await self._send_detection(result)
                self._dispatch_queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"Dispatch error: {e}")

    async def process_frame(
        self,
        frame: np.ndarray,
        timestamp: float | None = None,
        latitude: float | None = None,
        longitude: float | None = None,
        heading: float | None = None,
        speed: float | None = None,
        is_night: bool = False,
    ) -> list[dict]:
        """Process a single frame through the complete pipeline.

        Args:
            frame: BGR image from camera
            timestamp: Frame capture wall-clock time (epoch seconds)
            latitude: GPS latitude
            longitude: GPS longitude
            heading: GPS heading in degrees
            speed: Speed in mph
            is_night: Whether the camera is in night/IR mode

        Returns:
            List of detection results (duplicates filtered)
        """
        self._frame_count += 1

        # Thermal-aware frame skipping
        effective_skip = self.skip_frames
        if self.thermal.is_throttled:
            effective_skip = max(effective_skip, 2)

        if effective_skip > 0 and self._frame_count % (effective_skip + 1) != 0:
            return []

        start_time = time.monotonic()
        results = []

        # 1. Detect vehicles
        vehicle_detections = self.vehicle_detector.detect(frame)

        # 2. Update tracker
        confirmed_tracks = self.tracker.update(vehicle_detections)

        # 3. For each detected vehicle, detect plates and classify
        for det in vehicle_detections:
            bbox = det["bbox"]
            vehicle_img = self._crop(frame, bbox)

            if vehicle_img.size == 0:
                continue

            frame_ts = timestamp or time.time()

            result = {
                "id": str(uuid.uuid4()),
                "vehicle_type": det.get("class"),
                "vehicle_confidence": det["confidence"],
                "bbox": bbox,
                "latitude": latitude,
                "longitude": longitude,
                "heading": heading,
                "speed": speed,
                "plate_reads": [],
                "timestamp": datetime.fromtimestamp(frame_ts, tz=timezone.utc).isoformat(),
            }

            # 3a. Classify vehicle
            classification = self.vehicle_classifier.classify(vehicle_img)
            if classification:
                result["vehicle_make"] = classification.get("make")
                result["vehicle_model"] = classification.get("model")
                result["vehicle_year"] = classification.get("year")
                result["vehicle_color"] = classification.get("color")

            # 3b. Detect plates within vehicle region
            plate_detections = self.plate_detector.detect(vehicle_img)

            for plate_det in plate_detections:
                plate_bbox = plate_det["bbox"]
                plate_img = self.plate_detector.extract_plate_image(
                    vehicle_img, plate_bbox, is_night=is_night
                )

                # Compute full-frame plate bbox (accounting for padding offset)
                pad_frac = 0.1  # matches extract_plate_image default
                pad_x = int(plate_bbox[2] * pad_frac)
                pad_y = int(plate_bbox[3] * pad_frac)
                full_plate_bbox = [
                    bbox[0] + max(0, plate_bbox[0] - pad_x),
                    bbox[1] + max(0, plate_bbox[1] - pad_y),
                    plate_bbox[2] + 2 * pad_x,
                    plate_bbox[3] + 2 * pad_y,
                ]

                # 3c. OCR the plate (with state, bbox for merging)
                ocr_result = self.plate_ocr.read(
                    plate_img,
                    plate_bbox=full_plate_bbox,
                )
                if ocr_result:
                    # Skip duplicates (same plate seen within TTL)
                    if ocr_result.get("is_duplicate"):
                        continue

                    plate_read = {
                        "plate_text": ocr_result["plate_text"],
                        "confidence": ocr_result["confidence"],
                        "raw_ocr": ocr_result["raw_ocr"],
                        "plate_bbox": full_plate_bbox,
                    }

                    if self.save_captures:
                        plate_path = self._save_plate_image(plate_img)
                        plate_read["plate_image_path"] = plate_path

                    result["plate_reads"].append(plate_read)

            if self.save_captures and (result["plate_reads"] or det["confidence"] > 0.8):
                img_path, thumb_path = self._save_capture(frame, bbox)
                result["image_path"] = img_path
                result["thumbnail_path"] = thumb_path

            results.append(result)

            # Non-blocking dispatch to API (only if we have plate reads or high-conf vehicle)
            if result["plate_reads"] or det["confidence"] > 0.8:
                try:
                    self._dispatch_queue.put_nowait(result)
                except asyncio.QueueFull:
                    logger.debug("Dispatch queue full, dropping oldest detection")
                    try:
                        self._dispatch_queue.get_nowait()
                        self._dispatch_queue.put_nowait(result)
                    except asyncio.QueueEmpty:
                        pass

        # Performance tracking
        elapsed_ms = (time.monotonic() - start_time) * 1000
        self._perf_sum_ms += elapsed_ms
        self._perf_count += 1

        if self._frame_count % 30 == 0:
            avg_ms = self._perf_sum_ms / max(self._perf_count, 1)
            temp = self.thermal.temperature
            temp_str = f", {temp:.0f}C" if temp is not None else ""
            logger.info(
                f"Pipeline: {len(vehicle_detections)} vehicles, "
                f"{sum(len(r['plate_reads']) for r in results)} plates, "
                f"{elapsed_ms:.1f}ms (avg {avg_ms:.1f}ms){temp_str}"
            )
            self._perf_sum_ms = 0.0
            self._perf_count = 0

        return results

    async def _send_detection(self, result: dict):
        """Send detection to backend API."""
        try:
            payload = {
                "vehicle_type": result.get("vehicle_type"),
                "vehicle_color": result.get("vehicle_color"),
                "vehicle_make": result.get("vehicle_make"),
                "vehicle_model": result.get("vehicle_model"),
                "vehicle_year": result.get("vehicle_year"),
                "vehicle_confidence": result.get("vehicle_confidence"),
                "bbox_x": result["bbox"][0],
                "bbox_y": result["bbox"][1],
                "bbox_w": result["bbox"][2],
                "bbox_h": result["bbox"][3],
                "image_path": result.get("image_path"),
                "thumbnail_path": result.get("thumbnail_path"),
                "latitude": result.get("latitude"),
                "longitude": result.get("longitude"),
                "heading": result.get("heading"),
                "speed": result.get("speed"),
                "plate_reads": [
                    {
                        "plate_text": pr["plate_text"],
                        "confidence": pr["confidence"],
                        "raw_ocr": pr.get("raw_ocr"),
                        "plate_image_path": pr.get("plate_image_path"),
                        "plate_bbox_x": pr.get("plate_bbox", [0])[0],
                        "plate_bbox_y": pr["plate_bbox"][1] if pr.get("plate_bbox") else None,
                        "plate_bbox_w": pr["plate_bbox"][2] if pr.get("plate_bbox") else None,
                        "plate_bbox_h": pr["plate_bbox"][3] if pr.get("plate_bbox") else None,
                    }
                    for pr in result.get("plate_reads", [])
                ],
            }

            headers = {}
            if self._api_token:
                headers["Authorization"] = f"Bearer {self._api_token}"

            await self._http_client.post(
                self.api_endpoint, json=payload, headers=headers
            )
        except httpx.RequestError as e:
            logger.warning(f"Failed to send detection to API: {e}")
        except Exception as e:
            logger.warning(f"Unexpected dispatch error: {e}")

    def _crop(self, frame: np.ndarray, bbox: list[int]) -> np.ndarray:
        h, w = frame.shape[:2]
        x, y, bw, bh = bbox
        x1 = max(0, x)
        y1 = max(0, y)
        x2 = min(w, x + bw)
        y2 = min(h, y + bh)
        return frame[y1:y2, x1:x2]

    def _save_capture(
        self, frame: np.ndarray, bbox: list[int]
    ) -> tuple[str, str]:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        day_dir = self.capture_dir / datetime.now().strftime("%Y-%m-%d")
        day_dir.mkdir(parents=True, exist_ok=True)

        annotated = frame.copy()
        x, y, w, h = bbox
        cv2.rectangle(annotated, (x, y), (x + w, y + h), (0, 255, 0), 2)

        img_path = str(day_dir / f"{ts}_full.jpg")
        cv2.imwrite(img_path, annotated, [cv2.IMWRITE_JPEG_QUALITY, 85])

        thumb = cv2.resize(annotated, self.thumbnail_size)
        thumb_path = str(day_dir / f"{ts}_thumb.jpg")
        cv2.imwrite(thumb_path, thumb, [cv2.IMWRITE_JPEG_QUALITY, 70])

        return img_path, thumb_path

    def _save_plate_image(self, plate_img: np.ndarray) -> str:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        day_dir = self.capture_dir / datetime.now().strftime("%Y-%m-%d") / "plates"
        day_dir.mkdir(parents=True, exist_ok=True)

        path = str(day_dir / f"{ts}_plate.jpg")
        cv2.imwrite(path, plate_img, [cv2.IMWRITE_JPEG_QUALITY, 90])
        return path

    def set_api_token(self, token: str):
        self._api_token = token

    def reset(self):
        self.tracker.reset()
        self._frame_count = 0

    async def cleanup(self):
        if self._dispatcher_task:
            self._dispatcher_task.cancel()
            try:
                await self._dispatcher_task
            except asyncio.CancelledError:
                pass
        await self._http_client.aclose()

        # Release GPU resources
        self.vehicle_detector.engine.close()
        self.plate_detector.engine.close()
        self.plate_ocr.engine.close()
        self.vehicle_classifier.engine.close()


async def main():
    """Main entry point for the AI pipeline service."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    config_path = os.environ.get("AI_CONFIG", "config.yaml")
    pipeline = InferencePipeline(config_path)

    await pipeline.start_dispatcher()

    import redis.asyncio as aioredis

    redis_url = os.environ.get("REDIS_URL", "redis://redis:6379/0")
    redis_client = aioredis.from_url(redis_url)

    logger.info("AI pipeline waiting for frames...")

    pubsub = redis_client.pubsub()
    await pubsub.subscribe("reposcan:frames")

    frame_min_interval = 1.0 / pipeline.max_fps
    last_process_time = 0.0

    try:
        async for message in pubsub.listen():
            if message["type"] != "message":
                continue

            # Backpressure: skip frame if still within budget
            now = time.monotonic()
            if now - last_process_time < frame_min_interval:
                continue

            frame_data = json.loads(message["data"])
            frame_bytes = np.frombuffer(
                bytes.fromhex(frame_data["frame"]), dtype=np.uint8
            )
            frame = cv2.imdecode(frame_bytes, cv2.IMREAD_COLOR)

            if frame is not None:
                last_process_time = time.monotonic()
                await pipeline.process_frame(
                    frame,
                    timestamp=frame_data.get("timestamp"),
                    latitude=frame_data.get("latitude"),
                    longitude=frame_data.get("longitude"),
                    heading=frame_data.get("heading"),
                    speed=frame_data.get("speed"),
                )
    except asyncio.CancelledError:
        pass
    finally:
        await pipeline.cleanup()
        await redis_client.close()


if __name__ == "__main__":
    asyncio.run(main())
