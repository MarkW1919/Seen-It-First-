import uuid
from datetime import datetime

from geoalchemy2.functions import ST_MakePoint
from sqlalchemy import select, func, and_, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.detection import Detection, PlateRead
from app.models.scan_session import ScanSession
from app.schemas.detection import DetectionCreate


async def create_detection(
    db: AsyncSession,
    data: DetectionCreate,
    agent_id: uuid.UUID | None = None,
) -> Detection:
    detection = Detection(
        agent_id=agent_id,
        session_id=data.session_id,
        vehicle_type=data.vehicle_type,
        vehicle_color=data.vehicle_color,
        vehicle_make=data.vehicle_make,
        vehicle_model=data.vehicle_model,
        vehicle_year=data.vehicle_year,
        vehicle_confidence=data.vehicle_confidence,
        bbox_x=data.bbox_x,
        bbox_y=data.bbox_y,
        bbox_w=data.bbox_w,
        bbox_h=data.bbox_h,
        image_path=data.image_path,
        thumbnail_path=data.thumbnail_path,
        latitude=data.latitude,
        longitude=data.longitude,
        address=data.address,
        heading=data.heading,
        speed=data.speed,
        extra=data.extra,
    )

    # Set PostGIS point if coordinates provided
    if data.latitude is not None and data.longitude is not None:
        detection.location = ST_MakePoint(data.longitude, data.latitude)

    db.add(detection)
    await db.flush()

    # Bulk-create plate reads via add_all (single batch instead of per-row add)
    if data.plate_reads:
        plate_reads = [
            PlateRead(
                detection_id=detection.id,
                plate_text=pr.plate_text.upper().strip(),
                plate_state=pr.plate_state,
                plate_type=pr.plate_type,
                confidence=pr.confidence,
                plate_image_path=pr.plate_image_path,
                plate_bbox_x=pr.plate_bbox_x,
                plate_bbox_y=pr.plate_bbox_y,
                plate_bbox_w=pr.plate_bbox_w,
                plate_bbox_h=pr.plate_bbox_h,
                raw_ocr=pr.raw_ocr,
                ocr_alternatives=pr.ocr_alternatives,
            )
            for pr in data.plate_reads
        ]
        db.add_all(plate_reads)

    # Update session counters using SQL-level atomic increment.
    # The previous Python-level `session.total_detections += 1` caused a
    # lost-update race: two concurrent requests read the same value, both
    # increment to N+1, and the last write wins (losing a count).
    # SQL `SET col = col + 1` is atomic within the transaction.
    if data.session_id:
        plate_count = len(data.plate_reads)
        await db.execute(
            update(ScanSession)
            .where(ScanSession.id == data.session_id)
            .values(
                total_detections=ScanSession.total_detections + 1,
                total_plates=ScanSession.total_plates + plate_count,
            )
        )

    await db.flush()
    return detection


async def get_detection(db: AsyncSession, detection_id: uuid.UUID) -> Detection | None:
    result = await db.execute(
        select(Detection)
        .options(selectinload(Detection.plate_reads))
        .where(Detection.id == detection_id)
    )
    return result.scalar_one_or_none()


async def list_detections(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 50,
    agent_id: uuid.UUID | None = None,
    session_id: uuid.UUID | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
) -> tuple[list[Detection], int]:
    query = select(Detection).options(selectinload(Detection.plate_reads))
    count_query = select(func.count(Detection.id))

    filters = []
    if agent_id:
        filters.append(Detection.agent_id == agent_id)
    if session_id:
        filters.append(Detection.session_id == session_id)
    if start_date:
        filters.append(Detection.created_at >= start_date)
    if end_date:
        filters.append(Detection.created_at <= end_date)

    if filters:
        query = query.where(and_(*filters))
        count_query = count_query.where(and_(*filters))

    total = (await db.execute(count_query)).scalar() or 0

    query = (
        query.order_by(Detection.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    result = await db.execute(query)
    return list(result.scalars().all()), total


async def search_by_plate(
    db: AsyncSession,
    plate_text: str,
    exact: bool = False,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[Detection], int]:
    plate_upper = plate_text.upper().strip()
    if exact:
        plate_filter = PlateRead.plate_text == plate_upper
    else:
        plate_filter = PlateRead.plate_text.ilike(f"%{plate_upper}%")

    # Use DISTINCT on the main query to avoid duplicate Detection rows when
    # a detection has multiple plate reads matching the filter.  Previously
    # the deduplication was done in Python via result.unique() which wasted
    # bandwidth sending duplicate rows from DB to application.
    query = (
        select(Detection)
        .join(PlateRead)
        .options(selectinload(Detection.plate_reads))
        .where(plate_filter)
        .distinct()
    )
    count_query = (
        select(func.count(Detection.id.distinct()))
        .join(PlateRead)
        .where(plate_filter)
    )

    total = (await db.execute(count_query)).scalar() or 0

    query = (
        query.order_by(Detection.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    result = await db.execute(query)
    return list(result.scalars().all()), total


async def search_nearby(
    db: AsyncSession,
    latitude: float,
    longitude: float,
    radius_miles: float = 1.0,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[Detection], int]:
    from geoalchemy2.functions import ST_DWithin, ST_MakePoint
    from sqlalchemy import cast
    from geoalchemy2 import Geography

    point = ST_MakePoint(longitude, latitude)
    radius_meters = radius_miles * 1609.34

    spatial_filter = ST_DWithin(
        cast(Detection.location, Geography),
        cast(point, Geography),
        radius_meters,
    )

    query = (
        select(Detection)
        .options(selectinload(Detection.plate_reads))
        .where(Detection.location.isnot(None))
        .where(spatial_filter)
    )
    count_query = (
        select(func.count(Detection.id))
        .where(Detection.location.isnot(None))
        .where(spatial_filter)
    )

    total = (await db.execute(count_query)).scalar() or 0

    query = (
        query.order_by(Detection.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    result = await db.execute(query)
    return list(result.scalars().all()), total
