import uuid
from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ScanSession(Base):
    __tablename__ = "scan_sessions"
    __table_args__ = (
        # Composite index for querying sessions by agent and status
        Index("ix_scan_sessions_agent_status", "agent_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), index=True
    )

    # Session info
    name: Mapped[str] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(
        String(30), default="active", index=True
    )  # active, paused, completed

    # Route tracking (LineString of GPS points)
    route: Mapped[str] = mapped_column(Geometry("LINESTRING", srid=4326), nullable=True)

    # Stats
    total_detections: Mapped[int] = mapped_column(Integer, default=0)
    total_plates: Mapped[int] = mapped_column(Integer, default=0)
    total_alerts: Mapped[int] = mapped_column(Integer, default=0)
    distance_miles: Mapped[float] = mapped_column(Float, default=0.0)

    # Timestamps
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ended_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

    # Config snapshot
    config: Mapped[dict] = mapped_column(JSONB, default=dict)

    # Relationships
    agent = relationship("User", back_populates="scan_sessions")
    detections = relationship("Detection", back_populates="session")
