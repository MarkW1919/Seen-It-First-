"""Real-time alert service using Redis pub/sub for hot list matches."""

import json
import uuid
from datetime import UTC, datetime

import redis.asyncio as redis

from app.services.redis_client import get_redis


class AlertService:
    CHANNEL = "reposcan:alerts"

    def __init__(self):
        self._redis: redis.Redis | None = None

    async def connect(self):
        self._redis = await get_redis()

    async def disconnect(self):
        # Connection lifecycle managed by redis_client module
        self._redis = None

    async def publish_alert(
        self,
        alert_id: uuid.UUID,
        hotlist_entry_id: uuid.UUID,
        plate_text: str,
        confidence: float,
        vehicle_info: dict | None = None,
        location: dict | None = None,
        image_path: str | None = None,
    ):
        """Publish a hot list match alert to all connected clients."""
        message = {
            "type": "hotlist_alert",
            "alert_id": str(alert_id),
            "hotlist_entry_id": str(hotlist_entry_id),
            "plate_text": plate_text,
            "confidence": confidence,
            "vehicle": vehicle_info or {},
            "location": location or {},
            "image_path": image_path,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        if self._redis:
            await self._redis.publish(self.CHANNEL, json.dumps(message))

    async def publish_detection(
        self,
        detection_id: uuid.UUID,
        plate_text: str | None,
        vehicle_info: dict | None = None,
        location: dict | None = None,
    ):
        """Publish a new detection event (non-alert) for live feed."""
        message = {
            "type": "detection",
            "detection_id": str(detection_id),
            "plate_text": plate_text,
            "vehicle": vehicle_info or {},
            "location": location or {},
            "timestamp": datetime.now(UTC).isoformat(),
        }
        if self._redis:
            await self._redis.publish(self.CHANNEL, json.dumps(message))

    async def publish_system_event(self, event_type: str, data: dict):
        """Publish system events (camera status, AI status, etc.)."""
        message = {
            "type": f"system:{event_type}",
            "data": data,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        if self._redis:
            await self._redis.publish(self.CHANNEL, json.dumps(message))

    async def get_subscriber(self):
        """Get a pub/sub subscriber for the alerts channel."""
        if not self._redis:
            await self.connect()
        pubsub = self._redis.pubsub()
        await pubsub.subscribe(self.CHANNEL)
        return pubsub


# Singleton
alert_service = AlertService()
