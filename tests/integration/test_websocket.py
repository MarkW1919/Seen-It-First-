"""Integration tests for the WebSocket endpoint.

The backend exposes a WebSocket at /ws with an optional token query param
for authentication.
"""

import json

import httpx
import pytest
import websockets

pytestmark = pytest.mark.asyncio(loop_scope="session")

WS_BASE = "ws://localhost:8000"


# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------


async def test_ws_connect_with_valid_token(auth_tokens: dict):
    """WebSocket connection with a valid access token should succeed."""
    url = f"{WS_BASE}/ws?token={auth_tokens['access_token']}"
    async with websockets.connect(url) as ws:
        # Send a ping and expect a pong back
        await ws.send(json.dumps({"type": "ping"}))
        response = await ws.recv()
        data = json.loads(response)
        assert data["type"] == "pong"


async def test_ws_connect_with_invalid_token():
    """WebSocket connection with an invalid token should be closed by server."""
    url = f"{WS_BASE}/ws?token=invalid.token.value"
    with pytest.raises((websockets.exceptions.ConnectionClosed, Exception)):
        async with websockets.connect(url) as ws:
            # If the server closes the connection, recv() will raise
            await ws.recv()


async def test_ws_connect_anonymous():
    """WebSocket connection without a token should succeed (anonymous mode)."""
    url = f"{WS_BASE}/ws"
    async with websockets.connect(url) as ws:
        await ws.send(json.dumps({"type": "ping"}))
        response = await ws.recv()
        data = json.loads(response)
        assert data["type"] == "pong"


# ---------------------------------------------------------------------------
# Ping / Pong
# ---------------------------------------------------------------------------


async def test_ws_ping_pong(auth_tokens: dict):
    """Sending a ping message should return a pong."""
    url = f"{WS_BASE}/ws?token={auth_tokens['access_token']}"
    async with websockets.connect(url) as ws:
        await ws.send(json.dumps({"type": "ping"}))
        response = await ws.recv()
        data = json.loads(response)
        assert data == {"type": "pong"}


async def test_ws_multiple_pings(auth_tokens: dict):
    """Multiple pings should each get a pong response."""
    url = f"{WS_BASE}/ws?token={auth_tokens['access_token']}"
    async with websockets.connect(url) as ws:
        for _ in range(3):
            await ws.send(json.dumps({"type": "ping"}))
            response = await ws.recv()
            data = json.loads(response)
            assert data["type"] == "pong"


# ---------------------------------------------------------------------------
# Subscribe
# ---------------------------------------------------------------------------


async def test_ws_subscribe(auth_tokens: dict):
    """Sending a subscribe message should get a subscribed confirmation."""
    url = f"{WS_BASE}/ws?token={auth_tokens['access_token']}"
    async with websockets.connect(url) as ws:
        await ws.send(
            json.dumps({"type": "subscribe", "channel": "alerts"})
        )
        response = await ws.recv()
        data = json.loads(response)
        assert data["type"] == "subscribed"
        assert data["channel"] == "alerts"


async def test_ws_subscribe_multiple_channels(auth_tokens: dict):
    """Subscribing to multiple channels should each return confirmation."""
    url = f"{WS_BASE}/ws?token={auth_tokens['access_token']}"
    channels = ["alerts", "detections", "live_feed"]
    async with websockets.connect(url) as ws:
        for channel in channels:
            await ws.send(
                json.dumps({"type": "subscribe", "channel": channel})
            )
            response = await ws.recv()
            data = json.loads(response)
            assert data["type"] == "subscribed"
            assert data["channel"] == channel
