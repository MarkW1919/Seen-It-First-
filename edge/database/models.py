"""
SEEN IT FIRST - Edge AI Vehicle LPR System
Dataclass models for every database table.

Pure Python dataclasses -- no ORM.  Each model carries:
  * ``to_dict()``  - serialise to a plain dict (safe for JSON / INSERT)
  * ``from_row()`` - class-method to hydrate from an ``sqlite3.Row``
  * Auto-generated ``id`` (UUID4) and ``created_at`` (UTC ISO 8601)
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

logger = logging.getLogger("sif.database.models")


def _new_id() -> str:
    """Generate a new UUID4 primary key as a string."""
    return str(uuid4())


def _now_iso() -> str:
    """Current UTC time in ISO 8601 format with millisecond precision."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]


# ---------------------------------------------------------------------------
# Vehicle
# ---------------------------------------------------------------------------

@dataclass
class Vehicle:
    """A single vehicle detection frame."""

    camera_id: str
    housing_id: str
    vehicle_type: str
    detection_confidence: float
    id: str = field(default_factory=_new_id)
    color: Optional[str] = None
    make: Optional[str] = None
    model: Optional[str] = None
    year_bucket: Optional[str] = None
    bbox_x: Optional[int] = None
    bbox_y: Optional[int] = None
    bbox_w: Optional[int] = None
    bbox_h: Optional[int] = None
    image_path: Optional[str] = None
    thumbnail_path: Optional[str] = None
    created_at: str = field(default_factory=_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_row(cls, row) -> Vehicle:  # noqa: ANN001 – sqlite3.Row
        """Construct a Vehicle from an ``sqlite3.Row`` or dict-like object."""
        keys = cls.__dataclass_fields__.keys()
        data = {k: row[k] for k in keys if k in row.keys()}
        return cls(**data)


# ---------------------------------------------------------------------------
# Plate
# ---------------------------------------------------------------------------

@dataclass
class Plate:
    """OCR result for a license plate linked to a vehicle."""

    vehicle_id: str
    plate_text: str
    ocr_confidence: float
    id: str = field(default_factory=_new_id)
    plate_state: Optional[str] = None
    plate_image_path: Optional[str] = None
    raw_ocr: Optional[str] = None
    created_at: str = field(default_factory=_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_row(cls, row) -> Plate:  # noqa: ANN001
        keys = cls.__dataclass_fields__.keys()
        data = {k: row[k] for k in keys if k in row.keys()}
        return cls(**data)


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------

@dataclass
class Detection:
    """Fused vehicle + plate event record."""

    vehicle_id: str
    fused_confidence: float
    id: str = field(default_factory=_new_id)
    plate_id: Optional[str] = None
    hotlist_match: int = 0
    alert_sent: int = 0
    video_clip_path: Optional[str] = None
    created_at: str = field(default_factory=_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_row(cls, row) -> Detection:  # noqa: ANN001
        keys = cls.__dataclass_fields__.keys()
        data = {k: row[k] for k in keys if k in row.keys()}
        return cls(**data)


# ---------------------------------------------------------------------------
# Address
# ---------------------------------------------------------------------------

@dataclass
class Address:
    """Geo-fenced location for a camera housing."""

    label: str
    id: str = field(default_factory=_new_id)
    address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    radius_meters: float = 100.0
    created_at: str = field(default_factory=_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_row(cls, row) -> Address:  # noqa: ANN001
        keys = cls.__dataclass_fields__.keys()
        data = {k: row[k] for k in keys if k in row.keys()}
        return cls(**data)


# ---------------------------------------------------------------------------
# HotlistEntry
# ---------------------------------------------------------------------------

@dataclass
class HotlistEntry:
    """A plate of interest (repo order, stolen, BOLO, etc.)."""

    plate_text: str
    id: str = field(default_factory=_new_id)
    plate_state: Optional[str] = None
    case_number: Optional[str] = None
    lender_name: Optional[str] = None
    order_type: Optional[str] = None
    vehicle_year: Optional[str] = None
    vehicle_make: Optional[str] = None
    vehicle_model: Optional[str] = None
    vehicle_color: Optional[str] = None
    vin: Optional[str] = None
    debtor_name: Optional[str] = None
    debtor_address: Optional[str] = None
    is_active: int = 1
    priority: int = 3
    notes: Optional[str] = None
    created_at: str = field(default_factory=_now_iso)
    updated_at: str = field(default_factory=_now_iso)
    expires_at: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_row(cls, row) -> HotlistEntry:  # noqa: ANN001
        keys = cls.__dataclass_fields__.keys()
        data = {k: row[k] for k in keys if k in row.keys()}
        return cls(**data)


# ---------------------------------------------------------------------------
# SystemLog
# ---------------------------------------------------------------------------

@dataclass
class SystemLog:
    """Structured application log entry persisted to the database."""

    level: str
    source: str
    message: str
    id: str = field(default_factory=_new_id)
    details: Optional[str] = None
    created_at: str = field(default_factory=_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_row(cls, row) -> SystemLog:  # noqa: ANN001
        keys = cls.__dataclass_fields__.keys()
        data = {k: row[k] for k in keys if k in row.keys()}
        return cls(**data)
