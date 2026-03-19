"""
FastAPI application factory for the navigation API and WebSocket endpoint.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING
from urllib.parse import parse_qs

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware
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


def _is_public_endpoint(url: str) -> bool:
    return "openstreetmap.org" in url or "project-osrm.org" in url


def _resolve_navigation_endpoints(cfg: dict) -> tuple[str, str]:
    mode = str(cfg.get("mode", "hybrid")).lower()
    allow_public = bool(cfg.get("allow_public_endpoints", False))

    self_geocoder = str(cfg.get("nominatim_url", "")).strip()
    self_router = str(cfg.get("osrm_url", "")).strip()
    public_geocoder = str(
        cfg.get("public_nominatim_url", "https://nominatim.openstreetmap.org/search")
    ).strip()
    public_router = str(
        cfg.get("public_osrm_url", "https://router.project-osrm.org")
    ).strip()

    geocoder_url = ""
    router_url = ""

    if mode == "offline":
        logger.info("Navigation mode=offline: remote geocode/route lookups disabled")
    elif mode == "online":
        geocoder_url = public_geocoder or self_geocoder
        router_url = public_router or self_router
    else:
        geocoder_url = self_geocoder
        router_url = self_router
        if allow_public and not geocoder_url:
            geocoder_url = public_geocoder
        if allow_public and not router_url:
            router_url = public_router

    if not allow_public:
        if _is_public_endpoint(geocoder_url):
            geocoder_url = ""
        if _is_public_endpoint(router_url):
            router_url = ""

    return geocoder_url, router_url


def _extract_bearer_token(auth_header: str | None) -> str | None:
    """Extract a bearer token from an Authorization header."""
    if not auth_header:
        return None
    prefix = "bearer "
    if auth_header.lower().startswith(prefix):
        token = auth_header[len(prefix) :].strip()
        return token or None
    return None


def _extract_auth_credentials(
    x_api_key: str | None,
    auth_header: str | None,
    query_token: str | None,
) -> tuple[str | None, str | None, str | None]:
    """Normalize auth credentials for shared HTTP and WS checks."""
    return x_api_key, _extract_bearer_token(auth_header), query_token


def _is_api_authorized(
    expected_token: str,
    header_key: str | None,
    bearer: str | None,
    query_key: str | None,
) -> bool:
    """Return True when provided credentials match the expected token."""
    if not expected_token:
        return True
    return expected_token in {header_key, bearer, query_key}


def _is_protected_path(path: str) -> bool:
    """Return True for HTTP routes that require auth when enabled."""
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
    return cleaned


def _resolve_cors_origins(api_cfg: dict) -> list[str]:
    """Validate and resolve CORS origins from API config."""
    raw_origins = api_cfg.get("allowed_origins")
    allowed_origins = _normalize_allowed_origins(raw_origins) if raw_origins is not None else []

    if "*" in allowed_origins:
        raise ValueError("api.allowed_origins must not contain '*'")

    env = str(api_cfg.get("environment", "development")).lower()
    if env == "production" and not allowed_origins:
        raise ValueError("api.allowed_origins must contain explicit production origins")

    return allowed_origins or ["http://localhost:5173"]


@dataclass(frozen=True)
class AuthConfig:
    """Runtime auth settings for nested api.auth config."""

    enabled: bool
    api_key: str | None
    bearer_token: str | None


def _parse_auth_config(api_cfg: dict) -> AuthConfig:
    auth_cfg = api_cfg.get("auth", {})
    if not isinstance(auth_cfg, dict):
        auth_cfg = {}

    api_key = str(auth_cfg.get("api_key", "")).strip() or None
    bearer_token = str(auth_cfg.get("bearer_token", "")).strip() or None
    enabled = bool(auth_cfg.get("enabled", bool(api_key or bearer_token)))
    return AuthConfig(enabled=enabled, api_key=api_key, bearer_token=bearer_token)


def _is_cors_preflight(request: Request) -> bool:
    return (
        request.method == "OPTIONS"
        and "origin" in request.headers
        and "access-control-request-method" in request.headers
    )


def _is_nested_auth_authorized(
    headers: Request.headers.__class__ | dict[str, str],
    auth: AuthConfig,
    query_string: str = "",
) -> bool:
    if not auth.enabled:
        return True

    api_key = headers.get("x-api-key")
    bearer_token = _extract_bearer_token(headers.get("authorization"))

    if query_string:
        query = parse_qs(query_string)
        api_key = api_key or query.get("api_key", [None])[0]
        bearer_token = bearer_token or query.get("token", [None])[0]

    if auth.api_key and api_key == auth.api_key:
        return True
    if auth.bearer_token and bearer_token == auth.bearer_token:
        return True
    return False


def _log_unauthorized_http(request: Request) -> None:
    logger.warning(
        "Unauthorized API request: path=%s method=%s client=%s user_agent=%s",
        request.url.path,
        request.method,
        request.client.host if request.client else "unknown",
        request.headers.get("user-agent", "-"),
    )


def _log_unauthorized_ws(ws: WebSocket) -> None:
    logger.warning(
        "Unauthorized WS request: path=%s client=%s user_agent=%s",
        ws.url.path,
        ws.client.host if ws.client else "unknown",
        ws.headers.get("user-agent", "-"),
    )


class ConnectionManager:
    """Broadcast JSON events to all connected WebSocket clients."""

    def __init__(self):
        self._clients: list[WebSocket] = []

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._clients.append(ws)
        logger.debug("WS client connected (total=%d)", len(self._clients))

    def disconnect(self, ws: WebSocket) -> None:
        if ws in self._clients:
            self._clients.remove(ws)
        logger.debug("WS client disconnected (total=%d)", len(self._clients))

    async def broadcast(self, data: dict) -> None:
        dead: list[WebSocket] = []
        for ws in list(self._clients):
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)

        for ws in dead:
            self.disconnect(ws)

    @property
    def client_count(self) -> int:
        return len(self._clients)


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

    geocoder_url, router_url = _resolve_navigation_endpoints(cfg)
    allowed_origins = _resolve_cors_origins(api_cfg)

    legacy_token = str(api_cfg.get("auth_token", "") or "").strip()
    auth = _parse_auth_config(api_cfg)

    geocoder = Geocoder(
        nominatim_url=geocoder_url,
        cache_path=cfg.get("geocode_cache_path", "data/geocode_cache.json"),
        rate_limit_delay=float(cfg.get("min_request_interval_sec", 1.1)),
        timeout_sec=float(cfg.get("timeout_sec", 10)),
        max_retries=int(cfg.get("max_retries", 3)),
        backoff_base_sec=float(cfg.get("backoff_base_sec", 0.75)),
        user_agent=cfg.get(
            "user_agent",
            "Seen-It-First-Edge/1.0 (edge-navigation; ops@example.local)",
        ),
    )
    router_svc = Router(
        osrm_url=router_url,
        timeout_sec=float(cfg.get("timeout_sec", 10)),
        max_retries=int(cfg.get("max_retries", 3)),
        backoff_base_sec=float(cfg.get("backoff_base_sec", 0.75)),
        user_agent=cfg.get(
            "user_agent",
            "Seen-It-First-Edge/1.0 (edge-navigation; ops@example.local)",
        ),
        min_request_interval_sec=float(cfg.get("min_request_interval_sec", 1.1)),
    )
    arrival = ArrivalDetector(radius_m=float(cfg.get("arrival_radius_m", 80.0)))

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
        event_publisher=event_publisher,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        logger.info("Navigation API server starting")
        if legacy_token or auth.enabled:
            logger.info("API auth enabled for /navigation/* and /ws")
        if event_publisher is not None:
            event_publisher.set_event_loop(asyncio.get_running_loop())
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
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def auth_middleware(request: Request, call_next):
        if not _is_protected_path(request.url.path):
            return await call_next(request)

        if _is_cors_preflight(request):
            return await call_next(request)

        header_key, bearer, _ = _extract_auth_credentials(
            x_api_key=request.headers.get("x-api-key"),
            auth_header=request.headers.get("authorization"),
            query_token=None,
        )

        authorized = True
        if legacy_token:
            authorized = _is_api_authorized(legacy_token, header_key, bearer, None)
        elif auth.enabled:
            authorized = _is_nested_auth_authorized(request.headers, auth)

        if not authorized:
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

        authorized = True
        if legacy_token:
            authorized = _is_api_authorized(legacy_token, header_key, bearer, query_key)
        elif auth.enabled:
            authorized = _is_nested_auth_authorized(ws.headers, auth, ws.url.query)

        if not authorized:
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
            logger.exception("WebSocket client failed")
            ws_manager.disconnect(ws)

    return app
