import uuid
from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import (
    String,
    Float,
    Integer,
    DateTime,
    ForeignKey,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Detection(Base):
    __tablename__ = "detections"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scan_sessions.id"), nullable=True
    )

    # Vehicle detection
    vehicle_type: Mapped[str] = mapped_column(String(50), nullable=True)  # car, truck, suv, van
    vehicle_color: Mapped[str] = mapped_column(String(50), nullable=True)
    vehicle_make: Mapped[str] = mapped_column(String(100), nullable=True)
    vehicle_model: Mapped[str] = mapped_column(String(100), nullable=True)
    vehicle_year: Mapped[int] = mapped_column(Integer, nullable=True)
    vehicle_confidence: Mapped[float] = mapped_column(Float, nullable=True)

    # Bounding box
    bbox_x: Mapped[int] = mapped_column(Integer, nullable=True)
    bbox_y: Mapped[int] = mapped_column(Integer, nullable=True)
    bbox_w: Mapped[int] = mapped_column(Integer, nullable=True)
    bbox_h: Mapped[int] = mapped_column(Integer, nullable=True)

    # Image capture
    image_path: Mapped[str] = mapped_column(String(500), nullable=True)
    thumbnail_path: Mapped[str] = mapped_column(String(500), nullable=True)

    # Location
    latitude: Mapped[float] = mapped_column(Float, nullable=True)
    longitude: Mapped[float] = mapped_column(Float, nullable=True)
    location: Mapped[str] = mapped_column(
        Geometry("POINT", srid=4326), nullable=True
    )
    address: Mapped[str] = mapped_column(Text, nullable=True)
    heading: Mapped[float] = mapped_column(Float, nullable=True)
    speed: Mapped[float] = mapped_column(Float, nullable=True)

    # Metadata
    extra: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    # Relationships
    agent = relationship("User", back_populates="detections")
    session = relationship("ScanSession", back_populates="detections")
    plate_reads = relationship(
        "PlateRead", back_populates="detection", cascade="all, delete-orphan"
    )


class PlateRead(Base):
    __tablename__ = "plate_reads"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    detection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("detections.id", ondelete="CASCADE")
    )

    # Plate data
    plate_text: Mapped[str] = mapped_column(String(20), index=True)
    plate_state: Mapped[str] = mapped_column(String(5), nullable=True)
    plate_type: Mapped[str] = mapped_column(
        String(20), nullable=True
    )  # standard, temp, dealer, etc.
    confidence: Mapped[float] = mapped_column(Float)

    # Plate image region
    plate_image_path: Mapped[str] = mapped_column(String(500), nullable=True)
    plate_bbox_x: Mapped[int] = mapped_column(Integer, nullable=True)
    plate_bbox_y: Mapped[int] = mapped_column(Integer, nullable=True)
    plate_bbox_w: Mapped[int] = mapped_column(Integer, nullable=True)
    plate_bbox_h: Mapped[int] = mapped_column(Integer, nullable=True)

    # OCR details
    raw_ocr: Mapped[str] = mapped_column(String(30), nullable=True)
    ocr_alternatives: Mapped[dict] = mapped_column(JSONB, default=dict)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    detection = relationship("Detection", back_populates="plate_reads")
