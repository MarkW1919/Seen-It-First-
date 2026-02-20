"""Initial schema - all tables

Revision ID: 001_initial
Revises:
Create Date: 2026-02-16
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB
import geoalchemy2

# revision identifiers
revision = "001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- users ---
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), unique=True, index=True, nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("role", sa.String(50), server_default="agent", nullable=False),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # --- scan_sessions ---
    op.create_table(
        "scan_sessions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("agent_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("status", sa.String(30), server_default="active", nullable=False),
        sa.Column(
            "route",
            geoalchemy2.types.Geometry(geometry_type="LINESTRING", srid=4326),
            nullable=True,
        ),
        sa.Column("total_detections", sa.Integer, server_default="0"),
        sa.Column("total_plates", sa.Integer, server_default="0"),
        sa.Column("total_alerts", sa.Integer, server_default="0"),
        sa.Column("distance_miles", sa.Float, server_default="0.0"),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("config", JSONB, server_default="{}"),
    )

    # --- detections ---
    op.create_table(
        "detections",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("agent_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column(
            "session_id",
            UUID(as_uuid=True),
            sa.ForeignKey("scan_sessions.id"),
            nullable=True,
        ),
        sa.Column("vehicle_type", sa.String(50), nullable=True),
        sa.Column("vehicle_color", sa.String(50), nullable=True),
        sa.Column("vehicle_make", sa.String(100), nullable=True),
        sa.Column("vehicle_model", sa.String(100), nullable=True),
        sa.Column("vehicle_year", sa.Integer, nullable=True),
        sa.Column("vehicle_confidence", sa.Float, nullable=True),
        sa.Column("bbox_x", sa.Integer, nullable=True),
        sa.Column("bbox_y", sa.Integer, nullable=True),
        sa.Column("bbox_w", sa.Integer, nullable=True),
        sa.Column("bbox_h", sa.Integer, nullable=True),
        sa.Column("image_path", sa.String(500), nullable=True),
        sa.Column("thumbnail_path", sa.String(500), nullable=True),
        sa.Column("latitude", sa.Float, nullable=True),
        sa.Column("longitude", sa.Float, nullable=True),
        sa.Column(
            "location",
            geoalchemy2.types.Geometry(geometry_type="POINT", srid=4326),
            nullable=True,
        ),
        sa.Column("address", sa.Text, nullable=True),
        sa.Column("heading", sa.Float, nullable=True),
        sa.Column("speed", sa.Float, nullable=True),
        sa.Column("extra", JSONB, server_default="{}"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            index=True,
        ),
    )

    # --- plate_reads ---
    op.create_table(
        "plate_reads",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "detection_id",
            UUID(as_uuid=True),
            sa.ForeignKey("detections.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("plate_text", sa.String(20), index=True, nullable=False),
        sa.Column("plate_state", sa.String(5), nullable=True),
        sa.Column("plate_type", sa.String(20), nullable=True),
        sa.Column("confidence", sa.Float, nullable=False),
        sa.Column("plate_image_path", sa.String(500), nullable=True),
        sa.Column("plate_bbox_x", sa.Integer, nullable=True),
        sa.Column("plate_bbox_y", sa.Integer, nullable=True),
        sa.Column("plate_bbox_w", sa.Integer, nullable=True),
        sa.Column("plate_bbox_h", sa.Integer, nullable=True),
        sa.Column("raw_ocr", sa.String(30), nullable=True),
        sa.Column("ocr_alternatives", JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # --- hotlist_entries ---
    op.create_table(
        "hotlist_entries",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("plate_text", sa.String(20), index=True, nullable=False),
        sa.Column("plate_state", sa.String(5), nullable=True),
        sa.Column("case_number", sa.String(100), index=True, nullable=True),
        sa.Column("lender_name", sa.String(255), nullable=True),
        sa.Column("lender_contact", sa.String(255), nullable=True),
        sa.Column("order_type", sa.String(50), server_default="repossession"),
        sa.Column("vehicle_year", sa.Integer, nullable=True),
        sa.Column("vehicle_make", sa.String(100), nullable=True),
        sa.Column("vehicle_model", sa.String(100), nullable=True),
        sa.Column("vehicle_color", sa.String(50), nullable=True),
        sa.Column("vin", sa.String(17), index=True, nullable=True),
        sa.Column("debtor_name", sa.String(255), nullable=True),
        sa.Column("debtor_address", sa.Text, nullable=True),
        sa.Column("debtor_phone", sa.String(20), nullable=True),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true"), index=True),
        sa.Column("priority", sa.String(20), server_default="normal"),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("extra", JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )

    # --- hotlist_alerts ---
    op.create_table(
        "hotlist_alerts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "hotlist_entry_id",
            UUID(as_uuid=True),
            sa.ForeignKey("hotlist_entries.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("detection_id", UUID(as_uuid=True), sa.ForeignKey("detections.id"), nullable=True),
        sa.Column("agent_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("plate_text_matched", sa.String(20), nullable=False),
        sa.Column("match_confidence", sa.Float, nullable=False),
        sa.Column("latitude", sa.Float, nullable=True),
        sa.Column("longitude", sa.Float, nullable=True),
        sa.Column("address", sa.Text, nullable=True),
        sa.Column("status", sa.String(30), server_default="new"),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("hotlist_alerts")
    op.drop_table("hotlist_entries")
    op.drop_table("plate_reads")
    op.drop_table("detections")
    op.drop_table("scan_sessions")
    op.drop_table("users")
