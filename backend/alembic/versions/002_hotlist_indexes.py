"""Add composite indexes for hotlist lookup and alert queries

Revision ID: 002_hotlist_indexes
Revises: 001_initial
Create Date: 2026-02-19
"""

from alembic import op

# revision identifiers
revision = "002_hotlist_indexes"
down_revision = "001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Composite index for the primary hotlist lookup query:
    # SELECT ... FROM hotlist_entries WHERE is_active AND plate_text = ? AND (expires_at IS NULL OR ...)
    op.create_index(
        "ix_hotlist_active_plate_expires",
        "hotlist_entries",
        ["is_active", "plate_text", "expires_at"],
    )

    # Index on hotlist_alerts.hotlist_entry_id for FK lookups and dedup queries
    op.create_index(
        "ix_hotlist_alerts_entry_id",
        "hotlist_alerts",
        ["hotlist_entry_id"],
    )

    # Composite index for alert status + created_at (used by list_alerts, frontend polling)
    op.create_index(
        "ix_hotlist_alerts_status_created",
        "hotlist_alerts",
        ["status", "created_at"],
    )

    # Composite index for deduplication: entry + time window
    op.create_index(
        "ix_hotlist_alerts_entry_created",
        "hotlist_alerts",
        ["hotlist_entry_id", "created_at"],
    )

    # Index on plate_text_matched for alert lookups by plate
    op.create_index(
        "ix_hotlist_alerts_plate_matched",
        "hotlist_alerts",
        ["plate_text_matched"],
    )


def downgrade() -> None:
    op.drop_index("ix_hotlist_alerts_plate_matched", "hotlist_alerts")
    op.drop_index("ix_hotlist_alerts_entry_created", "hotlist_alerts")
    op.drop_index("ix_hotlist_alerts_status_created", "hotlist_alerts")
    op.drop_index("ix_hotlist_alerts_entry_id", "hotlist_alerts")
    op.drop_index("ix_hotlist_active_plate_expires", "hotlist_entries")
