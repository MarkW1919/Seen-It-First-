"""
SEEN IT FIRST - Edge AI Vehicle LPR System
In-process asyncio pub/sub event bus.

Provides a lightweight channel-based publish/subscribe mechanism for
real-time event distribution between system components (inference pipeline,
WebSocket handler, alert dispatcher, etc.).

Usage:
    bus = EventBus()
    q = bus.subscribe("detections")
    await bus.publish("detections", {"plate": "ABC1234", "confidence": 0.95})
    event = await q.get()
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List

logger = logging.getLogger("sif.api.event_bus")

# Predefined channel names used throughout the system.
CHANNEL_DETECTIONS = "detections"
CHANNEL_ALERTS = "alerts"
CHANNEL_SYSTEM_STATUS = "system_status"

_PREDEFINED_CHANNELS = (
    CHANNEL_DETECTIONS,
    CHANNEL_ALERTS,
    CHANNEL_SYSTEM_STATUS,
)

# Maximum number of items a subscriber queue will buffer before the oldest
# event is discarded to make room for a new one.
_DEFAULT_QUEUE_MAXSIZE = 100


class EventBus:
    """In-process asyncio pub/sub event bus.

    Each *channel* maintains a list of :class:`asyncio.Queue` instances -- one
    per subscriber.  Publishing to a channel enqueues the data dict into every
    subscriber queue in a non-blocking fashion.  If a subscriber's queue is
    full the oldest item is discarded before adding the new one, ensuring that
    slow consumers never block the publisher.
    """

    def __init__(self) -> None:
        self._channels: Dict[str, List[asyncio.Queue]] = {}

        # Pre-create the predefined channels so they always exist.
        for channel in _PREDEFINED_CHANNELS:
            self._channels[channel] = []

        logger.info(
            "EventBus initialised with predefined channels: %s",
            ", ".join(_PREDEFINED_CHANNELS),
        )

    # ------------------------------------------------------------------
    # Publish
    # ------------------------------------------------------------------

    async def publish(self, channel: str, data: Dict[str, Any]) -> None:
        """Publish *data* to every subscriber on *channel*.

        Non-blocking.  If a subscriber queue is full (maxsize=100) the oldest
        item is removed before the new item is added so that the publisher
        is never stalled.

        Parameters
        ----------
        channel:
            Name of the channel to publish on.
        data:
            Arbitrary JSON-serializable dict payload.
        """
        subscribers = self._channels.get(channel)
        if subscribers is None:
            # Lazily create channels that are not predefined.
            self._channels[channel] = []
            subscribers = self._channels[channel]

        logger.debug(
            "EventBus publish channel=%s subscribers=%d",
            channel,
            len(subscribers),
        )

        for q in subscribers:
            if q.full():
                # Discard the oldest item to make room.
                try:
                    q.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            try:
                q.put_nowait(data)
            except asyncio.QueueFull:
                # Should not happen after discarding, but guard defensively.
                logger.warning(
                    "EventBus: queue still full after discard on channel=%s",
                    channel,
                )

    # ------------------------------------------------------------------
    # Subscribe / Unsubscribe
    # ------------------------------------------------------------------

    def subscribe(self, channel: str) -> asyncio.Queue:
        """Register a new subscriber for *channel* and return its queue.

        The returned :class:`asyncio.Queue` has ``maxsize=100``.  Callers
        should ``await queue.get()`` in a loop to receive events.

        Parameters
        ----------
        channel:
            Name of the channel to subscribe to.

        Returns
        -------
        asyncio.Queue
            A bounded queue that will receive published events.
        """
        if channel not in self._channels:
            self._channels[channel] = []

        q: asyncio.Queue = asyncio.Queue(maxsize=_DEFAULT_QUEUE_MAXSIZE)
        self._channels[channel].append(q)

        logger.info(
            "EventBus subscriber added channel=%s (total=%d)",
            channel,
            len(self._channels[channel]),
        )
        return q

    def unsubscribe(self, channel: str, q: asyncio.Queue) -> None:
        """Remove a subscriber queue from *channel*.

        Safe to call even if the queue is not currently registered.

        Parameters
        ----------
        channel:
            Channel name.
        q:
            The queue previously returned by :meth:`subscribe`.
        """
        subscribers = self._channels.get(channel)
        if subscribers is None:
            return

        try:
            subscribers.remove(q)
            logger.info(
                "EventBus subscriber removed channel=%s (remaining=%d)",
                channel,
                len(subscribers),
            )
        except ValueError:
            logger.debug(
                "EventBus unsubscribe: queue not found in channel=%s",
                channel,
            )
