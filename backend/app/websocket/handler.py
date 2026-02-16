import asyncio
import json
import logging

from fastapi import WebSocket, WebSocketDisconnect

from app.services.alert_service import alert_service
from app.services.auth_service import decode_token

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        self.active_connections[client_id] = websocket
        logger.info(f"WebSocket client connected: {client_id}")

    def disconnect(self, client_id: str):
        self.active_connections.pop(client_id, None)
        logger.info(f"WebSocket client disconnected: {client_id}")

    async def send_to_client(self, client_id: str, message: dict):
        ws = self.active_connections.get(client_id)
        if ws:
            try:
                await ws.send_json(message)
            except Exception:
                self.disconnect(client_id)

    async def broadcast(self, message: dict):
        disconnected = []
        for client_id, ws in self.active_connections.items():
            try:
                await ws.send_json(message)
            except Exception:
                disconnected.append(client_id)
        for cid in disconnected:
            self.disconnect(cid)


manager = ConnectionManager()


async def redis_listener():
    """Background task that listens to Redis pub/sub and forwards to WebSocket clients."""
    try:
        pubsub = await alert_service.get_subscriber()
        async for message in pubsub.listen():
            if message["type"] == "message":
                data = json.loads(message["data"])
                await manager.broadcast(data)
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.error(f"Redis listener error: {e}")


async def websocket_endpoint(websocket: WebSocket, token: str | None = None):
    """WebSocket endpoint for real-time alerts and detection feed."""
    # Authenticate via token query param
    client_id = "anonymous"
    if token:
        payload = decode_token(token)
        if payload and payload.get("type") == "access":
            client_id = payload["sub"]
        else:
            await websocket.close(code=4001, reason="Invalid token")
            return

    await manager.connect(websocket, client_id)
    try:
        while True:
            # Keep connection alive; handle client messages
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                msg_type = msg.get("type")

                if msg_type == "ping":
                    await websocket.send_json({"type": "pong"})
                elif msg_type == "subscribe":
                    # Client can subscribe to specific event types
                    await websocket.send_json(
                        {"type": "subscribed", "channel": msg.get("channel")}
                    )
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        manager.disconnect(client_id)
