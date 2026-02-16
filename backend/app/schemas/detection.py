import uuid
from datetime import datetime

from pydantic import BaseModel


class PlateReadCreate(BaseModel):
    plate_text: str
    plate_state: str | None = None
    plate_type: str | None = None
    confidence: float
    plate_image_path: str | None = None
    plate_bbox_x: int | None = None
    plate_bbox_y: int | None = None
    plate_bbox_w: int | None = None
    plate_bbox_h: int | None = None
    raw_ocr: str | None = None
    ocr_alternatives: dict = {}


class PlateReadResponse(BaseModel):
    id: uuid.UUID
    plate_text: str
    plate_state: str | None
    plate_type: str | None
    confidence: float
    plate_image_path: str | None
    raw_ocr: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class DetectionCreate(BaseModel):
    session_id: uuid.UUID | None = None
    vehicle_type: str | None = None
    vehicle_color: str | None = None
    vehicle_make: str | None = None
    vehicle_model: str | None = None
    vehicle_year: int | None = None
    vehicle_confidence: float | None = None
    bbox_x: int | None = None
    bbox_y: int | None = None
    bbox_w: int | None = None
    bbox_h: int | None = None
    image_path: str | None = None
    thumbnail_path: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    address: str | None = None
    heading: float | None = None
    speed: float | None = None
    extra: dict = {}
    plate_reads: list[PlateReadCreate] = []


class DetectionResponse(BaseModel):
    id: uuid.UUID
    agent_id: uuid.UUID | None
    session_id: uuid.UUID | None
    vehicle_type: str | None
    vehicle_color: str | None
    vehicle_make: str | None
    vehicle_model: str | None
    vehicle_year: int | None
    vehicle_confidence: float | None
    image_path: str | None
    thumbnail_path: str | None
    latitude: float | None
    longitude: float | None
    address: str | None
    heading: float | None
    speed: float | None
    extra: dict
    created_at: datetime
    plate_reads: list[PlateReadResponse] = []

    model_config = {"from_attributes": True}


class DetectionList(BaseModel):
    items: list[DetectionResponse]
    total: int
    page: int
    page_size: int
