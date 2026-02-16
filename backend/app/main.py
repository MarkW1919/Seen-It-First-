import asyncio
import logging

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from prometheus_fastapi_instrumentator import Instrumentator

from app.config import get_settings
from app.database import init_db
from app.routers import auth, detections, hotlist, plates, search, camera, system
from app.services.alert_service import alert_service
from app.websocket.handler import websocket_endpoint, redis_listener

settings = get_settings()
logger = logging.getLogger("reposcan")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting RepoScan Pro backend...")
    await init_db()
    await alert_service.connect()

    # Start Redis listener for WebSocket forwarding
    listener_task = asyncio.create_task(redis_listener())

    yield

    # Shutdown
    listener_task.cancel()
    try:
        await listener_task
    except asyncio.CancelledError:
        pass
    await alert_service.disconnect()
    logger.info("RepoScan Pro backend stopped.")


app = FastAPI(
    title="RepoScan Pro",
    description="AI-powered License Plate Recognition for Repossession Agents",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Prometheus metrics
Instrumentator().instrument(app).expose(app)

# Routers
app.include_router(auth.router)
app.include_router(detections.router)
app.include_router(hotlist.router)
app.include_router(plates.router)
app.include_router(search.router)
app.include_router(camera.router)
app.include_router(system.router)

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
        "docs": "/docs",
    }
