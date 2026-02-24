import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User
from app.schemas.hotlist import (
    HotListAlertResponse,
    HotListAlertUpdate,
    HotListEntryCreate,
    HotListEntryResponse,
    HotListEntryUpdate,
    HotListImport,
)
from app.services.hotlist_service import (
    create_entry,
    delete_entry,
    get_entry,
    list_alerts,
    list_entries,
    update_alert,
    update_entry,
)

router = APIRouter(prefix="/api/hotlist", tags=["hotlist"])


# ─── Hot List Entries ───


@router.post("/entries", response_model=HotListEntryResponse, status_code=201)
async def create_hotlist_entry(
    data: HotListEntryCreate,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    entry = await create_entry(db, data)
    await db.commit()
    return entry


@router.post("/entries/import", status_code=201)
async def import_hotlist_entries(
    data: HotListImport,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Bulk import with batched commits to avoid holding a single long transaction.

    Commits every 100 entries so large imports don't accumulate thousands of
    unflushed objects in memory or hold locks for extended periods.
    """
    batch_size = 100
    total_imported = 0

    for i in range(0, len(data.entries), batch_size):
        batch = data.entries[i : i + batch_size]
        for entry_data in batch:
            await create_entry(db, entry_data)
        await db.commit()
        total_imported += len(batch)

    return {"imported": total_imported}


@router.get("/entries", response_model=list[HotListEntryResponse])
async def get_hotlist_entries(
    active_only: bool = True,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    entries, _ = await list_entries(db, active_only=active_only, page=page, page_size=page_size)
    return entries


@router.get("/entries/{entry_id}", response_model=HotListEntryResponse)
async def get_hotlist_entry(
    entry_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    entry = await get_entry(db, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Hot list entry not found")
    return entry


@router.patch("/entries/{entry_id}", response_model=HotListEntryResponse)
async def update_hotlist_entry(
    entry_id: uuid.UUID,
    data: HotListEntryUpdate,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    entry = await update_entry(db, entry_id, data)
    if not entry:
        raise HTTPException(status_code=404, detail="Hot list entry not found")
    await db.commit()
    return entry


@router.delete("/entries/{entry_id}", status_code=204)
async def delete_hotlist_entry(
    entry_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    deleted = await delete_entry(db, entry_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Hot list entry not found")
    await db.commit()


# ─── Alerts ───


@router.get("/alerts", response_model=list[HotListAlertResponse])
async def get_hotlist_alerts(
    status: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    alerts, _ = await list_alerts(db, status=status, page=page, page_size=page_size)
    return alerts


@router.patch("/alerts/{alert_id}", response_model=HotListAlertResponse)
async def update_hotlist_alert(
    alert_id: uuid.UUID,
    data: HotListAlertUpdate,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    alert = await update_alert(db, alert_id, data)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    await db.commit()
    return alert
