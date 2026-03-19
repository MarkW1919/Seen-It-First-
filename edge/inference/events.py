"""
Event publisher: bridges the sync inference pipeline to async WebSocket clients.

EventPublisher is thread-safe and can be called from any thread (e.g. the
inference thread). It relays events to all connected dashboard WebSocket clients
by scheduling coroutines on the uvicorn event loop via
asyncio.run_coroutine_threadsafe().

Workflow:
    1. EdgeService creates EventPublisher(ws_manager) at startup.
    2. The FastAPI lifespan (running inside the uvicorn event loop) calls
       event_publisher.set_event_loop(asyncio.get_event_loop()).
    3. Inference pipeline calls publish_detection() / publish_alert() from
       its worker thread; events are forwarded to all WebSocket clients.

If set_event_loop() has not yet been called (race at startup), events are
silently dropped — the pipeline never blocks waiting for a client.
"""

import asyncio
import logging
import threading
from collections import deque
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from edge.api.app import ConnectionManager

logger = logging.getLogger(__name__)


class EventPublisher:
    """
    Thread-safe bridge from sync inference code to async WebSocket broadcasts.

    All public methods can be called from any thread.
    """

    def __init__(self, ws_manager: "ConnectionManager | None" = None):
        self._ws_manager = ws_manager
        self._loop: asyncio.AbstractEventLoop | None = None
        self._lock = threading.Lock()
        self._recent_events: deque[dict] = deque(maxlen=200)

    # ------------------------------------------------------------------
    # Wiring
    # ------------------------------------------------------------------

    def set_ws_manager(self, ws_manager: "ConnectionManager"):
        """Attach (or replace) the WebSocket connection manager."""
        with self._lock:
            self._ws_manager = ws_manager

    def set_event_loop(self, loop: asyncio.AbstractEventLoop):
        """
        Store the running event loop so broadcast() can be scheduled.

        Must be called from within an async context on the target loop,
        e.g. inside a FastAPI lifespan function.
        """
        with self._lock:
            self._loop = loop
        logger.debug("EventPublisher: event loop attached")

    # ------------------------------------------------------------------
    # Public publish API
    # ------------------------------------------------------------------

    def publish_detection(self, data: dict):
        """
        Publish a confirmed vehicle detection to WebSocket clients.

        Args:
            data: Dict with keys track_id, plate_text, camera_id, plate_conf,
                  vehicle_class, vehicle_conf, bbox, timestamp.
        """
        logger.info(
            "Detection confirmed: track=%s plate=%s cam=%s conf=%.2f",
            data.get("track_id"),
            data.get("plate_text"),
            data.get("camera_id"),
            data.get("plate_conf", 0.0),
        )
        payload = {"event": "DETECTION", **data}
        self._remember_event(payload)
        self._broadcast(payload)

    def publish_alert(self, data: dict):
        """
        Publish a hotlist-match alert to WebSocket clients.

        Args:
            data: Dict with keys plate, vehicle_class, camera_id, confidence,
                  timestamp, reason, priority, track_id.
        """
        logger.warning(
            "HOTLIST MATCH: plate=%s cam=%s conf=%.2f priority=%s",
            data.get("plate"),
            data.get("camera_id"),
            data.get("confidence", 0.0),
            data.get("priority"),
        )
        payload = {"event": "ALERT", **data}
        self._remember_event(payload)
        self._broadcast(payload)

    def publish_system_event(self, event_type: str, data: dict):
        """
        Publish a generic system event (e.g. camera_start, pipeline_active).

        Args:
            event_type: Short uppercase string identifier.
            data:       Arbitrary event payload.
        """
        payload = {"event": event_type, **data}
        self._remember_event(payload)
        self._broadcast(payload)

    def recent_events(self, event_type: str | None = None, limit: int = 50) -> list[dict]:
        """Return recent events newest-first, optionally filtered by type."""
        normalized_type = event_type.upper().strip() if event_type else None
        safe_limit = max(1, min(int(limit), 200))

        with self._lock:
            events = list(self._recent_events)

        if normalized_type:
            events = [
                event for event in events
                if str(event.get("event", "")).upper() == normalized_type
            ]

        return events[:safe_limit]

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _broadcast(self, payload: dict):
        with self._lock:
            loop = self._loop
            ws_manager = self._ws_manager

        if loop is None or ws_manager is None:
            return  # not yet wired — drop gracefully

        if not loop.is_running():
            return  # uvicorn has shut down

        asyncio.run_coroutine_threadsafe(ws_manager.broadcast(payload), loop)

    def _remember_event(self, payload: dict):
        """Store a bounded in-memory history for dashboard hydration."""
        with self._lock:
            self._recent_events.appendleft(dict(payload))
