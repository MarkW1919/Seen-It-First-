"""
FastAPI application factory.

Creates the HTTP + WebSocket server that exposes:
  - Navigation endpoints (/navigation/*)
  - WebSocket for real-time events (/ws)

Run alongside the edge pipeline via uvicorn in a daemon thread:

    from edge.api.app import create_app
    import uvicorn, threading

    app = create_app(scheduler=service.scheduler, config=nav_cfg)
    t = threading.Thread(
        target=uvicorn.run,
        args=(app,),
        kwargs={"host": "0.0.0.0", "port": 8080, "log_level": "warning"},
        daemon=True,
    )
    t.start()
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from edge.navigation.geocoder import Geocoder
from edge.navigation.router import Router
from edge.navigation.arrival_detector import ArrivalDetector
from edge.api.state import NavigationState
from edge.api.navigation import router as nav_router

if TYPE_CHECKING:
    from edge.inference.scheduler import InferenceScheduler
    from edge.inference.events import EventPublisher
    from edge.ranking.engine import RankingEngine
    from edge.api.state import GpsState
    from edge.storage.repository import DetectionRepository

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# WebSocket connection manager
# ---------------------------------------------------------------------------

class ConnectionManager:
    """Broadcast JSON events to all connected WebSocket clients."""

    def __init__(self):
        self._clients: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self._clients.append(ws)
        logger.debug("WS client connected (total=%d)", len(self._clients))

    def disconnect(self, ws: WebSocket):
        if ws in self._clients:
            self._clients.remove(ws)
        logger.debug("WS client disconnected (total=%d)", len(self._clients))

    async def broadcast(self, data: dict):
        """Send data to all connected clients, removing dead connections."""
        dead: list[WebSocket] = []
        for ws in list(self._clients):
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            if ws in self._clients:
                self._clients.remove(ws)

    @property
    def client_count(self) -> int:
        return len(self._clients)


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

def create_app(
    scheduler:        "InferenceScheduler",
    config:           dict | None = None,
    ws_manager:       ConnectionManager | None = None,
    event_publisher:  "EventPublisher | None" = None,
    ranking_engine:   "RankingEngine | None" = None,
    gps_state:        "GpsState | None" = None,
    repository:       "DetectionRepository | None" = None,
) -> FastAPI:
    """
    Build and return the FastAPI application.

    Args:
        scheduler:       The active InferenceScheduler from EdgeService.
        config:          Navigation config section from system.yaml.
        ws_manager:      Optional pre-created ConnectionManager.  If not
                         provided a new one is created internally.
        event_publisher: Optional EventPublisher whose event loop will be
                         set to the uvicorn loop inside the lifespan so that
                         inference events can be broadcast to WebSocket clients.
    """
    cfg = config or {}

    geocoder = Geocoder(
        nominatim_url=cfg.get("nominatim_url", "https://nominatim.openstreetmap.org"),
        cache_path=cfg.get("geocode_cache_path", "data/geocode_cache.json"),
    )
    router_svc = Router(
        osrm_url=cfg.get("osrm_url", "https://router.project-osrm.org"),
    )
    arrival = ArrivalDetector(
        radius_m=cfg.get("arrival_radius_m", 80.0),
    )

    if ws_manager is None:
        ws_manager = ConnectionManager()

    nav_state = NavigationState(
        scheduler=scheduler,
        geocoder=geocoder,
        router=router_svc,
        arrival_detector=arrival,
        ws_manager=ws_manager,
        ranking_engine=ranking_engine,
        gps_state=gps_state,
        repository=repository,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        logger.info("Navigation API server starting")
        # Wire the inference event publisher to this (uvicorn) event loop so
        # that detections and alerts can be broadcast to WebSocket clients from
        # the inference thread.
        if event_publisher is not None:
            event_publisher.set_event_loop(asyncio.get_event_loop())
            logger.info("EventPublisher wired to uvicorn event loop")
        yield
        logger.info("Navigation API server stopping")
        arrival.clear()

    app = FastAPI(
        title="Seen-It-First Navigation API",
        version="1.0.0",
        lifespan=lifespan,
    )

    # CORS — allow dashboard dev server and same-origin production
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    # Attach shared state
    app.state.nav = nav_state

    # Mount navigation routes
    app.include_router(nav_router)

    # WebSocket endpoint
    @app.websocket("/ws")
    async def websocket_endpoint(ws: WebSocket):
        await ws_manager.connect(ws)
        # Send current navigation status immediately on connect
        try:
            await ws.send_json({
                "event": "STATUS",
                "navigating": nav_state.is_navigating,
                "arrived": arrival.has_arrived,
            })
            while True:
                # Keep alive — client may send pings; we just discard
                await ws.receive_text()
        except WebSocketDisconnect:
            ws_manager.disconnect(ws)
        except Exception:
            ws_manager.disconnect(ws)

    return app
