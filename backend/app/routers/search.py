from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User
from app.schemas.detection import DetectionList
from app.services.detection_service import search_by_plate, search_nearby

router = APIRouter(prefix="/api/search", tags=["search"])


@router.get("/plate", response_model=DetectionList)
async def search_plate(
    q: str = Query(..., min_length=1, description="Plate text to search"),
    exact: bool = Query(False, description="Exact match only"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    items, total = await search_by_plate(
        db, plate_text=q, exact=exact, page=page, page_size=page_size
    )
    return DetectionList(items=items, total=total, page=page, page_size=page_size)


@router.get("/nearby", response_model=DetectionList)
async def search_nearby_detections(
    lat: float = Query(..., description="Latitude"),
    lng: float = Query(..., description="Longitude"),
    radius: float = Query(1.0, ge=0.1, le=50.0, description="Radius in miles"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    items, total = await search_nearby(
        db,
        latitude=lat,
        longitude=lng,
        radius_miles=radius,
        page=page,
        page_size=page_size,
    )
    return DetectionList(items=items, total=total, page=page, page_size=page_size)
