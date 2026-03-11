"""
FastAPI application factory.

Creates the HTTP + WebSocket server that exposes:
  - Navigation endpoints (/navigation/*)
  - WebSocket for real-time events (/ws)

Run alongside the edge pipeline via uvicorn in a daemon thread:

    from edge.api.app import create_app
    import uvicorn, threading

    app = create_app(scheduler=service.scheduler, config=nav_cfg, api_config=api_cfg)
    t = threading.Thread(
        target=uvicorn.run,
        args=(app,),
        kwargs={"host": "127.0.0.1", "port": 8080, "log_level": "warning"},
        daemon=True,
    )
    t.start()
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING
from urllib.parse import parse_qs

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from edge.api.navigation import router as nav_router
from edge.api.state import NavigationState
from edge.navigation.arrival_detector import ArrivalDetector
from edge.navigation.geocoder import Geocoder
from edge.navigation.router import Router

if TYPE_CHECKING:
    from edge.api.state import GpsState
    from edge.inference.events import EventPublisher
    from edge.inference.scheduler import InferenceScheduler
    from edge.ranking.engine import RankingEngine
    from edge.storage.repository import DetectionRepository

logger = logging.getLogger(__name__)


def _extract_bearer_token(auth_header: str | None) -> str | None:
    """Extract bearer token from Authorization header when present."""
    if not auth_header:
        return None
    prefix = "bearer "
    if auth_header.lower().startswith(prefix):
        return auth_header[len(prefix):].strip()
    return None


def _extract_auth_credentials(
    x_api_key: str | None,
    auth_header: str | None,
    query_token: str | None,
) -> tuple[str | None, str | None, str | None]:
    """Normalize auth credential tuple for re-use by HTTP and WebSocket paths."""
    return x_api_key, _extract_bearer_token(auth_header), query_token


def _is_api_authorized(expected_token: str, header_key: str | None, bearer: str | None, query_key: str | None) -> bool:
    """Return True when provided credentials match expected token."""
    if not expected_token:
        return True
    return expected_token in {header_key, bearer, query_key}


def _is_protected_path(path: str) -> bool:
    """Return True for paths that require API auth when auth is enabled."""
    return path == "/navigation" or path.startswith("/navigation/")


def _normalize_allowed_origins(raw_origins: object) -> list[str]:
    """Parse allowed origins from list/string config into a clean list."""
    if isinstance(raw_origins, str):
        candidates = [part.strip() for part in raw_origins.split(",")]
    elif isinstance(raw_origins, list):
        candidates = [str(origin).strip() for origin in raw_origins]
    else:
        candidates = []

    cleaned = [origin for origin in candidates if origin]
    return cleaned or ["http://localhost:5173"]


# ---------------------------------------------------------------------------
# WebSocket connection manager
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class AuthConfig:
    """Runtime auth settings for HTTP navigation routes and /ws."""

    enabled: bool
    api_key: str | None
    bearer_token: str | None


def _parse_auth_config(api_cfg: dict) -> AuthConfig:
    auth_cfg = api_cfg.get("auth", {}) if isinstance(api_cfg.get("auth", {}), dict) else {}
    api_key = str(auth_cfg.get("api_key", "")).strip() or None
    bearer_token = str(auth_cfg.get("bearer_token", "")).strip() or None
    enabled = bool(auth_cfg.get("enabled", bool(api_key or bearer_token)))
    return AuthConfig(enabled=enabled, api_key=api_key, bearer_token=bearer_token)


def _extract_bearer_token(value: str | None) -> str | None:
    if not value:
        return None
    parts = value.strip().split(" ", 1)
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1].strip() or None
    return None


def _is_authorized(headers: dict[str, str], auth: AuthConfig, query_string: str = "") -> bool:
    if not auth.enabled:
        return True

    api_key = headers.get("x-api-key")
    bearer_token = _extract_bearer_token(headers.get("authorization"))

    if query_string:
        q = parse_qs(query_string)
        api_key = api_key or q.get("api_key", [None])[0]
        bearer_token = bearer_token or q.get("token", [None])[0]

    if auth.api_key and api_key == auth.api_key:
        return True
    if auth.bearer_token and bearer_token == auth.bearer_token:
        return True
    return False


def _resolve_cors_origins(api_cfg: dict) -> list[str]:
    origins = api_cfg.get("allowed_origins", [])
    env = str(api_cfg.get("environment", "production")).lower()

    if not isinstance(origins, list):
        raise ValueError("api.allowed_origins must be a list of origins")

    cleaned = [str(origin).strip() for origin in origins if str(origin).strip()]
    if "*" in cleaned:
        raise ValueError("Wildcard CORS origin '*' is not allowed")

    if env == "production" and not cleaned:
        raise ValueError(
            "api.allowed_origins must contain explicit production origins when api.environment=production"
        )

    return cleaned


def _log_unauthorized_http(request: Request):
    logger.warning(
        "Unauthorized API request: path=%s method=%s client=%s user_agent=%s",
        request.url.path,
        request.method,
        request.client.host if request.client else "unknown",
        request.headers.get("user-agent", "-"),
    )


def _log_unauthorized_ws(ws: WebSocket):
    logger.warning(
        "Unauthorized WS request: path=%s client=%s user_agent=%s",
        ws.url.path,
        ws.client.host if ws.client else "unknown",
        ws.headers.get("user-agent", "-"),
    )


def _is_cors_preflight(request: Request) -> bool:
    return (
        request.method == "OPTIONS"
        and "origin" in request.headers
        and "access-control-request-method" in request.headers
    )



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
    scheduler: "InferenceScheduler",
    config: dict | None = None,
    api_config: dict | None = None,
    ws_manager: ConnectionManager | None = None,
    event_publisher: "EventPublisher | None" = None,
    ranking_engine: "RankingEngine | None" = None,
    gps_state: "GpsState | None" = None,
    repository: "DetectionRepository | None" = None,
) -> FastAPI:
    """Build and return the FastAPI application."""
    cfg = config or {}
    api_cfg = api_config or {}

    allowed_origins = _resolve_cors_origins(api_cfg)
    auth = _parse_auth_config(api_cfg)

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

    api_token = str(api_cfg.get("auth_token", "") or "").strip()
    allowed_origins = _normalize_allowed_origins(api_cfg.get("allowed_origins", ["http://localhost:5173"]))

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        logger.info("Navigation API server starting")
        if api_token:
            logger.info("API auth enabled for /navigation/* and /ws")
        if "*" in allowed_origins:
            logger.warning("CORS allow_origins contains '*' — this is not recommended for production")
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

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def auth_middleware(request: Request, call_next):
        if request.method == "OPTIONS":
            return await call_next(request)

        if api_token and _is_protected_path(request.url.path):
            header_key, bearer, _ = _extract_auth_credentials(
                x_api_key=request.headers.get("x-api-key"),
                auth_header=request.headers.get("authorization"),
                query_token=None,
            )
            if not _is_api_authorized(api_token, header_key, bearer, None):
                return JSONResponse({"detail": "Unauthorized"}, status_code=401)
    async def auth_http_requests(request: Request, call_next):
        if request.url.path.startswith("/navigation") and _is_cors_preflight(request):
            return await call_next(request)

        if request.url.path.startswith("/navigation") and not _is_authorized(request.headers, auth):
            _log_unauthorized_http(request)
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Unauthorized"},
            )
        return await call_next(request)

    app.state.nav = nav_state
    app.include_router(nav_router)

    @app.websocket("/ws")
    async def websocket_endpoint(ws: WebSocket):
        header_key, bearer, query_key = _extract_auth_credentials(
            x_api_key=ws.headers.get("x-api-key"),
            auth_header=ws.headers.get("authorization"),
            query_token=ws.query_params.get("token"),
        )

        if not _is_api_authorized(api_token, header_key, bearer, query_key):
            await ws.close(code=1008)
        if not _is_authorized(dict(ws.headers), auth, ws.url.query):
            _log_unauthorized_ws(ws)
            await ws.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        await ws_manager.connect(ws)
        try:
            await ws.send_json(
                {
                    "event": "STATUS",
                    "navigating": nav_state.is_navigating,
                    "arrived": arrival.has_arrived,
                }
            )
            while True:
                await ws.receive_text()
        except WebSocketDisconnect:
            ws_manager.disconnect(ws)
        except Exception:
            ws_manager.disconnect(ws)

    return app
