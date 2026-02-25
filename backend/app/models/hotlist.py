import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class HotListEntry(Base):
    __tablename__ = "hotlist_entries"
    __table_args__ = (
        # Composite index for the primary lookup query:
        # WHERE is_active = TRUE AND plate_text = ? AND (expires_at IS NULL OR expires_at > ?)
        Index("ix_hotlist_active_plate_expires", "is_active", "plate_text", "expires_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    plate_text: Mapped[str] = mapped_column(String(20), index=True)
    plate_state: Mapped[str] = mapped_column(String(5), nullable=True)

    # Case information
    case_number: Mapped[str] = mapped_column(String(100), nullable=True, index=True)
    lender_name: Mapped[str] = mapped_column(String(255), nullable=True)
    lender_contact: Mapped[str] = mapped_column(String(255), nullable=True)
    order_type: Mapped[str] = mapped_column(
        String(50), default="repossession"
    )  # repossession, investigation, skip_trace

    # Vehicle details from lender
    vehicle_year: Mapped[int] = mapped_column(nullable=True)
    vehicle_make: Mapped[str] = mapped_column(String(100), nullable=True)
    vehicle_model: Mapped[str] = mapped_column(String(100), nullable=True)
    vehicle_color: Mapped[str] = mapped_column(String(50), nullable=True)
    vin: Mapped[str] = mapped_column(String(17), nullable=True, index=True)

    # Debtor info
    debtor_name: Mapped[str] = mapped_column(String(255), nullable=True)
    debtor_address: Mapped[str] = mapped_column(Text, nullable=True)
    debtor_phone: Mapped[str] = mapped_column(String(20), nullable=True)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    priority: Mapped[str] = mapped_column(
        String(20), default="normal"
    )  # low, normal, high, critical
    notes: Mapped[str] = mapped_column(Text, nullable=True)
    extra: Mapped[dict] = mapped_column(JSONB, default=dict)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    alerts = relationship(
        "HotListAlert", back_populates="hotlist_entry", cascade="all, delete-orphan"
    )


class HotListAlert(Base):
    __tablename__ = "hotlist_alerts"
    __table_args__ = (
        # Index for filtering alerts by status (used by list_alerts and frontend polling)
        Index("ix_hotlist_alerts_status_created", "status", "created_at"),
        # Index for deduplication lookups by entry + recent time window
        Index("ix_hotlist_alerts_entry_created", "hotlist_entry_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hotlist_entry_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("hotlist_entries.id", ondelete="CASCADE"), index=True
    )
    detection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("detections.id"), nullable=True
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    # Alert details
    plate_text_matched: Mapped[str] = mapped_column(String(20), index=True)
    match_confidence: Mapped[float] = mapped_column(Float)
    latitude: Mapped[float] = mapped_column(Float, nullable=True)
    longitude: Mapped[float] = mapped_column(Float, nullable=True)
    address: Mapped[str] = mapped_column(Text, nullable=True)

    # Status
    status: Mapped[str] = mapped_column(
        String(30), default="new"
    )  # new, acknowledged, dispatched, resolved, false_positive
    acknowledged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    hotlist_entry = relationship("HotListEntry", back_populates="alerts")
