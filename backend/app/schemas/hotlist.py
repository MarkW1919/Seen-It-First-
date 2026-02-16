import uuid
from datetime import datetime

from pydantic import BaseModel


class HotListEntryCreate(BaseModel):
    plate_text: str
    plate_state: str | None = None
    case_number: str | None = None
    lender_name: str | None = None
    lender_contact: str | None = None
    order_type: str = "repossession"
    vehicle_year: int | None = None
    vehicle_make: str | None = None
    vehicle_model: str | None = None
    vehicle_color: str | None = None
    vin: str | None = None
    debtor_name: str | None = None
    debtor_address: str | None = None
    debtor_phone: str | None = None
    priority: str = "normal"
    notes: str | None = None
    expires_at: datetime | None = None
    extra: dict = {}


class HotListEntryUpdate(BaseModel):
    plate_text: str | None = None
    plate_state: str | None = None
    case_number: str | None = None
    lender_name: str | None = None
    lender_contact: str | None = None
    order_type: str | None = None
    vehicle_year: int | None = None
    vehicle_make: str | None = None
    vehicle_model: str | None = None
    vehicle_color: str | None = None
    vin: str | None = None
    debtor_name: str | None = None
    debtor_address: str | None = None
    debtor_phone: str | None = None
    is_active: bool | None = None
    priority: str | None = None
    notes: str | None = None
    expires_at: datetime | None = None
    extra: dict | None = None


class HotListEntryResponse(BaseModel):
    id: uuid.UUID
    plate_text: str
    plate_state: str | None
    case_number: str | None
    lender_name: str | None
    order_type: str
    vehicle_year: int | None
    vehicle_make: str | None
    vehicle_model: str | None
    vehicle_color: str | None
    vin: str | None
    debtor_name: str | None
    debtor_address: str | None
    is_active: bool
    priority: str
    notes: str | None
    created_at: datetime
    updated_at: datetime
    expires_at: datetime | None

    model_config = {"from_attributes": True}


class HotListAlertResponse(BaseModel):
    id: uuid.UUID
    hotlist_entry_id: uuid.UUID
    detection_id: uuid.UUID | None
    plate_text_matched: str
    match_confidence: float
    latitude: float | None
    longitude: float | None
    address: str | None
    status: str
    acknowledged_at: datetime | None
    resolved_at: datetime | None
    notes: str | None
    created_at: datetime
    hotlist_entry: HotListEntryResponse | None = None

    model_config = {"from_attributes": True}


class HotListAlertUpdate(BaseModel):
    status: str | None = None
    notes: str | None = None


class HotListImport(BaseModel):
    """For CSV/bulk import of hot list entries."""

    entries: list[HotListEntryCreate]
