"""Add missing FK indexes and query-optimizing indexes across all tables

Revision ID: 003_missing_indexes
Revises: 002_hotlist_indexes
Create Date: 2026-02-19

Tables affected:
- detections: FK indexes on agent_id, session_id; composite (agent_id, created_at),
  (session_id, created_at) for list_detections filtered queries
- plate_reads: FK index on detection_id (critical for CASCADE deletes and
  selectinload); index on plate_state for by-state queries; composite
  (plate_text, detection_id) for plate search joins
- scan_sessions: FK index on agent_id; index on status; composite
  (agent_id, status) for filtered session queries

Non-destructive: all operations are CREATE INDEX (additive only).
"""

from alembic import op

# revision identifiers
revision = "003_missing_indexes"
down_revision = "002_hotlist_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ─── detections ───

    # FK index on agent_id (used by list_detections agent filter, FK joins)
    op.create_index("ix_detections_agent_id", "detections", ["agent_id"])

    # FK index on session_id (used by list_detections session filter, FK joins)
    op.create_index("ix_detections_session_id", "detections", ["session_id"])

    # Composite: agent + created_at for paginated list filtered by agent
    op.create_index("ix_detections_agent_created", "detections", ["agent_id", "created_at"])

    # Composite: session + created_at for paginated list filtered by session
    op.create_index("ix_detections_session_created", "detections", ["session_id", "created_at"])

    # ─── plate_reads ───

    # FK index on detection_id — critical for:
    # 1. CASCADE DELETE performance (without this, deleting a detection scans the full table)
    # 2. selectinload(Detection.plate_reads) performance
    op.create_index("ix_plate_reads_detection_id", "plate_reads", ["detection_id"])

    # Index on plate_state for the /api/plates/by-state/{state} endpoint
    op.create_index("ix_plate_reads_plate_state", "plate_reads", ["plate_state"])

    # Composite: plate_text + detection_id for plate search JOINs
    op.create_index(
        "ix_plate_reads_text_detection",
        "plate_reads",
        ["plate_text", "detection_id"],
    )

    # ─── scan_sessions ───

    # FK index on agent_id
    op.create_index("ix_scan_sessions_agent_id", "scan_sessions", ["agent_id"])

    # Index on status for filtering active/completed sessions
    op.create_index("ix_scan_sessions_status", "scan_sessions", ["status"])

    # Composite: agent_id + status for "my active sessions" queries
    op.create_index(
        "ix_scan_sessions_agent_status",
        "scan_sessions",
        ["agent_id", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_scan_sessions_agent_status", "scan_sessions")
    op.drop_index("ix_scan_sessions_status", "scan_sessions")
    op.drop_index("ix_scan_sessions_agent_id", "scan_sessions")
    op.drop_index("ix_plate_reads_text_detection", "plate_reads")
    op.drop_index("ix_plate_reads_plate_state", "plate_reads")
    op.drop_index("ix_plate_reads_detection_id", "plate_reads")
    op.drop_index("ix_detections_session_created", "detections")
    op.drop_index("ix_detections_agent_created", "detections")
    op.drop_index("ix_detections_session_id", "detections")
    op.drop_index("ix_detections_agent_id", "detections")
