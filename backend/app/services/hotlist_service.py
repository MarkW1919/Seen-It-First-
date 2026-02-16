import uuid
from datetime import datetime, timezone

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.hotlist import HotListEntry, HotListAlert
from app.schemas.hotlist import HotListEntryCreate, HotListEntryUpdate, HotListAlertUpdate


async def create_entry(db: AsyncSession, data: HotListEntryCreate) -> HotListEntry:
    entry = HotListEntry(
        plate_text=data.plate_text.upper().strip(),
        plate_state=data.plate_state,
        case_number=data.case_number,
        lender_name=data.lender_name,
        lender_contact=data.lender_contact,
        order_type=data.order_type,
        vehicle_year=data.vehicle_year,
        vehicle_make=data.vehicle_make,
        vehicle_model=data.vehicle_model,
        vehicle_color=data.vehicle_color,
        vin=data.vin,
        debtor_name=data.debtor_name,
        debtor_address=data.debtor_address,
        debtor_phone=data.debtor_phone,
        priority=data.priority,
        notes=data.notes,
        expires_at=data.expires_at,
        extra=data.extra,
    )
    db.add(entry)
    await db.flush()
    return entry


async def update_entry(
    db: AsyncSession, entry_id: uuid.UUID, data: HotListEntryUpdate
) -> HotListEntry | None:
    entry = await db.get(HotListEntry, entry_id)
    if not entry:
        return None

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if field == "plate_text" and value:
            value = value.upper().strip()
        setattr(entry, field, value)

    await db.flush()
    return entry


async def get_entry(db: AsyncSession, entry_id: uuid.UUID) -> HotListEntry | None:
    result = await db.execute(
        select(HotListEntry)
        .options(selectinload(HotListEntry.alerts))
        .where(HotListEntry.id == entry_id)
    )
    return result.scalar_one_or_none()


async def list_entries(
    db: AsyncSession,
    active_only: bool = True,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[HotListEntry], int]:
    query = select(HotListEntry)
    count_query = select(func.count(HotListEntry.id))

    if active_only:
        query = query.where(HotListEntry.is_active.is_(True))
        count_query = count_query.where(HotListEntry.is_active.is_(True))

    total = (await db.execute(count_query)).scalar() or 0

    query = (
        query.order_by(HotListEntry.priority.desc(), HotListEntry.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    result = await db.execute(query)
    return list(result.scalars().all()), total


async def delete_entry(db: AsyncSession, entry_id: uuid.UUID) -> bool:
    entry = await db.get(HotListEntry, entry_id)
    if not entry:
        return False
    await db.delete(entry)
    await db.flush()
    return True


async def check_plate_against_hotlist(
    db: AsyncSession, plate_text: str
) -> list[HotListEntry]:
    """Check if a plate matches any active hot list entries."""
    plate_upper = plate_text.upper().strip()
    now = datetime.now(timezone.utc)

    result = await db.execute(
        select(HotListEntry).where(
            and_(
                HotListEntry.is_active.is_(True),
                HotListEntry.plate_text == plate_upper,
                (HotListEntry.expires_at.is_(None)) | (HotListEntry.expires_at > now),
            )
        )
    )
    return list(result.scalars().all())


async def create_alert(
    db: AsyncSession,
    hotlist_entry_id: uuid.UUID,
    detection_id: uuid.UUID | None,
    agent_id: uuid.UUID | None,
    plate_text: str,
    confidence: float,
    latitude: float | None = None,
    longitude: float | None = None,
    address: str | None = None,
) -> HotListAlert:
    alert = HotListAlert(
        hotlist_entry_id=hotlist_entry_id,
        detection_id=detection_id,
        agent_id=agent_id,
        plate_text_matched=plate_text,
        match_confidence=confidence,
        latitude=latitude,
        longitude=longitude,
        address=address,
    )
    db.add(alert)
    await db.flush()
    return alert


async def list_alerts(
    db: AsyncSession,
    status: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[HotListAlert], int]:
    query = select(HotListAlert).options(selectinload(HotListAlert.hotlist_entry))
    count_query = select(func.count(HotListAlert.id))

    if status:
        query = query.where(HotListAlert.status == status)
        count_query = count_query.where(HotListAlert.status == status)

    total = (await db.execute(count_query)).scalar() or 0

    query = (
        query.order_by(HotListAlert.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    result = await db.execute(query)
    return list(result.scalars().all()), total


async def update_alert(
    db: AsyncSession, alert_id: uuid.UUID, data: HotListAlertUpdate
) -> HotListAlert | None:
    alert = await db.get(HotListAlert, alert_id)
    if not alert:
        return None

    if data.status:
        alert.status = data.status
        if data.status == "acknowledged":
            alert.acknowledged_at = datetime.now(timezone.utc)
        elif data.status in ("resolved", "false_positive"):
            alert.resolved_at = datetime.now(timezone.utc)
    if data.notes is not None:
        alert.notes = data.notes

    await db.flush()
    return alert
