import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User
from app.schemas.detection import DetectionCreate, DetectionList, DetectionResponse
from app.services.alert_service import alert_service
from app.services.detection_service import (
    create_detection,
    get_detection,
    list_detections,
)
from app.services.hotlist_service import check_plate_against_hotlist, create_alert

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/detections", tags=["detections"])


@router.post("/", response_model=DetectionResponse, status_code=status.HTTP_201_CREATED)
async def create_new_detection(
    data: DetectionCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    detection = await create_detection(db, data, agent_id=user.id)

    # Collect alert payloads to publish AFTER commit (prevents race condition
    # where WebSocket clients receive alerts before DB records are visible)
    pending_alert_publishes: list[dict] = []

    # Check each plate read against the hot list
    # The O(1) Redis cache check short-circuits non-matches instantly
    seen_entries: set[uuid.UUID] = set()
    for pr in data.plate_reads:
        matches = await check_plate_against_hotlist(db, pr.plate_text)
        for match in matches:
            # Skip if we already created an alert for this entry in this detection
            if match.id in seen_entries:
                continue
            seen_entries.add(match.id)

            alert = await create_alert(
                db,
                hotlist_entry_id=match.id,
                detection_id=detection.id,
                agent_id=user.id,
                plate_text=pr.plate_text,
                confidence=pr.confidence,
                latitude=data.latitude,
                longitude=data.longitude,
                address=data.address,
            )
            # alert is None if suppressed by cooldown or dedup lock
            if alert is not None:
                pending_alert_publishes.append(
                    {
                        "alert_id": alert.id,
                        "hotlist_entry_id": match.id,
                        "plate_text": pr.plate_text,
                        "confidence": pr.confidence,
                        "vehicle_info": {
                            "type": data.vehicle_type,
                            "color": data.vehicle_color,
                            "make": data.vehicle_make,
                            "model": data.vehicle_model,
                            "year": data.vehicle_year,
                        },
                        "location": {
                            "lat": data.latitude,
                            "lng": data.longitude,
                            "address": data.address,
                        },
                        "image_path": data.image_path,
                    }
                )

    # COMMIT first — ensures all DB records are visible before broadcasting
    await db.commit()

    # Now publish alerts via Redis (post-commit, no race condition)
    for payload in pending_alert_publishes:
        await alert_service.publish_alert(**payload)

    # Publish detection to live feed (also post-commit)
    plate_text = data.plate_reads[0].plate_text if data.plate_reads else None
    await alert_service.publish_detection(
        detection_id=detection.id,
        plate_text=plate_text,
        vehicle_info={
            "type": data.vehicle_type,
            "color": data.vehicle_color,
            "make": data.vehicle_make,
            "model": data.vehicle_model,
            "year": data.vehicle_year,
        },
        location={"lat": data.latitude, "lng": data.longitude},
    )

    return await get_detection(db, detection.id)


@router.get("/", response_model=DetectionList)
async def get_detections(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    session_id: uuid.UUID | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items, total = await list_detections(
        db,
        page=page,
        page_size=page_size,
        agent_id=user.id if user.role == "agent" else None,
        session_id=session_id,
        start_date=start_date,
        end_date=end_date,
    )
    return DetectionList(items=items, total=total, page=page, page_size=page_size)


@router.get("/{detection_id}", response_model=DetectionResponse)
async def get_detection_by_id(
    detection_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    detection = await get_detection(db, detection_id)
    if not detection:
        raise HTTPException(status_code=404, detail="Detection not found")
    return detection
