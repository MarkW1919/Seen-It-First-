import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from app.config import get_settings
from app.database import async_session, init_db
from app.routers import auth, camera, detections, hotlist, plates, routes, search, system
from app.services.alert_service import alert_service
from app.services.hotlist_service import hotlist_cache
from app.services.redis_client import close_redis
from app.websocket.handler import redis_listener, websocket_endpoint

settings = get_settings()
logger = logging.getLogger("reposcan")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting RepoScan Pro backend...")
    await init_db()
    await alert_service.connect()

    # Initialize the hotlist Redis cache with current DB data
    await hotlist_cache.connect()
    async with async_session() as db:
        await hotlist_cache.load_from_db(db)

    # Start Redis listener for WebSocket forwarding
    listener_task = asyncio.create_task(redis_listener())

    yield

    # Shutdown
    listener_task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await listener_task
    await hotlist_cache.disconnect()
    await alert_service.disconnect()
    await close_redis()
    logger.info("RepoScan Pro backend stopped.")


# Disable Swagger UI and ReDoc in production (prevents API enumeration)
app = FastAPI(
    title="RepoScan Pro",
    description="AI-powered License Plate Recognition for Repossession Agents",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    openapi_url="/openapi.json" if settings.debug else None,
)

# CORS — restrict methods and headers to what's actually used
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)

# Prometheus metrics (exposed only on internal path, protected by Nginx)
Instrumentator().instrument(app).expose(app)

# Routers
app.include_router(auth.router)
app.include_router(detections.router)
app.include_router(hotlist.router)
app.include_router(plates.router)
app.include_router(search.router)
app.include_router(camera.router)
app.include_router(system.router)
app.include_router(routes.router)

# WebSocket
app.websocket("/ws")(websocket_endpoint)


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "reposcan-backend"}


@app.get("/")
async def root():
    return {
        "service": "RepoScan Pro",
        "version": "1.0.0",
    }
