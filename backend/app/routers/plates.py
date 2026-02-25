from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.detection import PlateRead
from app.models.user import User
from app.schemas.detection import PlateReadResponse

router = APIRouter(prefix="/api/plates", tags=["plates"])


@router.get("/recent", response_model=list[PlateReadResponse])
async def get_recent_plates(
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    result = await db.execute(select(PlateRead).order_by(PlateRead.created_at.desc()).limit(limit))
    return list(result.scalars().all())


@router.get("/stats")
async def get_plate_stats(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    total = (await db.execute(select(func.count(PlateRead.id)))).scalar() or 0
    unique = (await db.execute(select(func.count(PlateRead.plate_text.distinct())))).scalar() or 0

    # State breakdown
    state_counts = await db.execute(
        select(PlateRead.plate_state, func.count(PlateRead.id))
        .where(PlateRead.plate_state.isnot(None))
        .group_by(PlateRead.plate_state)
        .order_by(func.count(PlateRead.id).desc())
        .limit(10)
    )

    return {
        "total_reads": total,
        "unique_plates": unique,
        "top_states": [{"state": row[0], "count": row[1]} for row in state_counts.all()],
    }


@router.get("/by-state/{state}", response_model=list[PlateReadResponse])
async def get_plates_by_state(
    state: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(PlateRead)
        .where(PlateRead.plate_state == state.upper())
        .order_by(PlateRead.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(result.scalars().all())
