import uuid
from datetime import datetime

from pydantic import BaseModel


class ScanSessionCreate(BaseModel):
    name: str | None = None
    config: dict = {}


class ScanSessionUpdate(BaseModel):
    name: str | None = None
    status: str | None = None


class ScanSessionResponse(BaseModel):
    id: uuid.UUID
    agent_id: uuid.UUID
    name: str | None
    status: str
    total_detections: int
    total_plates: int
    total_alerts: int
    distance_miles: float
    started_at: datetime
    ended_at: datetime | None
    config: dict

    model_config = {"from_attributes": True}
