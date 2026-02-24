import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.route import Route, RouteStop
from app.models.user import User
from app.routers.auth import get_current_user

router = APIRouter(prefix="/api/routes", tags=["routes"])


# ── Schemas ──────────────────────────────────────────────────────────────────


class StopCreate(BaseModel):
    address: str
    latitude: float
    longitude: float
    geofence_radius_m: float = Field(default=50.0, ge=10.0, le=500.0)


class RouteCreate(BaseModel):
    name: str | None = None
    stops: list[StopCreate] = Field(..., min_length=1, max_length=200)


class StopResponse(BaseModel):
    id: str
    order_index: int
    address: str
    latitude: float
    longitude: float
    geofence_radius_m: float
    status: str
    arrived_at: str | None = None
    scan_started_at: str | None = None
    completed_at: str | None = None
    plates_found: int = 0
    notes: str | None = None

    class Config:
        from_attributes = True


class RouteResponse(BaseModel):
    id: str
    name: str | None
    status: str
    current_stop_index: int
    total_stops: int
    created_at: str
    completed_at: str | None = None
    stops: list[StopResponse] = []

    class Config:
        from_attributes = True


class StopUpdate(BaseModel):
    notes: str | None = None
    plates_found: int | None = None


# ── Endpoints ────────────────────────────────────────────────────────────────


@router.post("", response_model=RouteResponse, status_code=status.HTTP_201_CREATED)
async def create_route(
    body: RouteCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    route = Route(
        agent_id=user.id,
        name=body.name,
        status="active",
        current_stop_index=0,
        total_stops=len(body.stops),
    )
    for idx, stop_data in enumerate(body.stops):
        stop = RouteStop(
            route=route,
            order_index=idx,
            address=stop_data.address,
            latitude=stop_data.latitude,
            longitude=stop_data.longitude,
            geofence_radius_m=stop_data.geofence_radius_m,
            status="pending",
        )
        route.stops.append(stop)

    db.add(route)
    await db.commit()
    await db.refresh(route, attribute_names=["stops"])
    return _route_to_response(route)


@router.get("", response_model=list[RouteResponse])
async def list_routes(
    status_filter: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    stmt = (
        select(Route)
        .where(Route.agent_id == user.id)
        .options(selectinload(Route.stops))
        .order_by(Route.created_at.desc())
    )
    if status_filter:
        stmt = stmt.where(Route.status == status_filter)

    result = await db.execute(stmt)
    routes = result.scalars().all()
    return [_route_to_response(r) for r in routes]


@router.get("/active", response_model=RouteResponse | None)
async def get_active_route(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    stmt = (
        select(Route)
        .where(Route.agent_id == user.id, Route.status == "active")
        .options(selectinload(Route.stops))
        .order_by(Route.created_at.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    route = result.scalar_one_or_none()
    if not route:
        return None
    return _route_to_response(route)


@router.get("/{route_id}", response_model=RouteResponse)
async def get_route(
    route_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    route = await _get_route_or_404(route_id, user.id, db)
    return _route_to_response(route)


@router.post("/{route_id}/stops/{stop_index}/arrive")
async def mark_arrival(
    route_id: str,
    stop_index: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    route = await _get_route_or_404(route_id, user.id, db)
    stop = _get_stop_by_index(route, stop_index)

    if stop.status not in ("pending", "arrived"):
        raise HTTPException(400, f"Stop is already {stop.status}")

    stop.status = "arrived"
    stop.arrived_at = datetime.now(UTC)
    route.current_stop_index = stop_index
    await db.commit()
    return {"status": "arrived", "stop_index": stop_index}


@router.post("/{route_id}/stops/{stop_index}/scan-start")
async def start_scan_at_stop(
    route_id: str,
    stop_index: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    route = await _get_route_or_404(route_id, user.id, db)
    stop = _get_stop_by_index(route, stop_index)

    if stop.status not in ("arrived", "scanning"):
        raise HTTPException(400, f"Must arrive before scanning (current: {stop.status})")

    stop.status = "scanning"
    stop.scan_started_at = datetime.now(UTC)
    await db.commit()
    return {"status": "scanning", "stop_index": stop_index}


@router.post("/{route_id}/stops/{stop_index}/complete")
async def complete_stop(
    route_id: str,
    stop_index: int,
    body: StopUpdate | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    route = await _get_route_or_404(route_id, user.id, db)
    stop = _get_stop_by_index(route, stop_index)

    stop.status = "completed"
    stop.completed_at = datetime.now(UTC)
    if body:
        if body.plates_found is not None:
            stop.plates_found = body.plates_found
        if body.notes is not None:
            stop.notes = body.notes

    # Auto-advance to next pending stop
    next_stop = None
    for s in route.stops:
        if s.order_index > stop_index and s.status == "pending":
            next_stop = s
            break

    if next_stop:
        route.current_stop_index = next_stop.order_index
    else:
        all_done = all(s.status in ("completed", "skipped") for s in route.stops)
        if all_done:
            route.status = "completed"
            route.completed_at = datetime.now(UTC)

    await db.commit()
    return {
        "status": "completed",
        "stop_index": stop_index,
        "next_stop_index": next_stop.order_index if next_stop else None,
        "route_completed": route.status == "completed",
    }


@router.post("/{route_id}/stops/{stop_index}/skip")
async def skip_stop(
    route_id: str,
    stop_index: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    route = await _get_route_or_404(route_id, user.id, db)
    stop = _get_stop_by_index(route, stop_index)

    stop.status = "skipped"
    stop.completed_at = datetime.now(UTC)

    next_stop = None
    for s in route.stops:
        if s.order_index > stop_index and s.status == "pending":
            next_stop = s
            break

    if next_stop:
        route.current_stop_index = next_stop.order_index

    await db.commit()
    return {
        "status": "skipped",
        "next_stop_index": next_stop.order_index if next_stop else None,
    }


@router.delete("/{route_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_route(
    route_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    route = await _get_route_or_404(route_id, user.id, db)
    await db.delete(route)
    await db.commit()


# ── Helpers ──────────────────────────────────────────────────────────────────


async def _get_route_or_404(route_id: str, agent_id: uuid.UUID, db: AsyncSession) -> Route:
    stmt = (
        select(Route)
        .where(Route.id == uuid.UUID(route_id), Route.agent_id == agent_id)
        .options(selectinload(Route.stops))
    )
    result = await db.execute(stmt)
    route = result.scalar_one_or_none()
    if not route:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Route not found")
    return route


def _get_stop_by_index(route: Route, index: int) -> RouteStop:
    for stop in route.stops:
        if stop.order_index == index:
            return stop
    raise HTTPException(status.HTTP_404_NOT_FOUND, f"Stop index {index} not found")


def _route_to_response(route: Route) -> RouteResponse:
    return RouteResponse(
        id=str(route.id),
        name=route.name,
        status=route.status,
        current_stop_index=route.current_stop_index,
        total_stops=route.total_stops,
        created_at=route.created_at.isoformat() if route.created_at else "",
        completed_at=route.completed_at.isoformat() if route.completed_at else None,
        stops=[
            StopResponse(
                id=str(s.id),
                order_index=s.order_index,
                address=s.address,
                latitude=s.latitude,
                longitude=s.longitude,
                geofence_radius_m=s.geofence_radius_m,
                status=s.status,
                arrived_at=s.arrived_at.isoformat() if s.arrived_at else None,
                scan_started_at=(s.scan_started_at.isoformat() if s.scan_started_at else None),
                completed_at=s.completed_at.isoformat() if s.completed_at else None,
                plates_found=s.plates_found or 0,
                notes=s.notes,
            )
            for s in route.stops
        ],
    )
