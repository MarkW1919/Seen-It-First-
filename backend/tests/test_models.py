"""Unit tests for SQLAlchemy model definitions."""
from app.models.user import User
from app.models.detection import Detection, PlateRead
from app.models.hotlist import HotListEntry, HotListAlert
from app.models.scan_session import ScanSession


def test_user_model_tablename():
    assert User.__tablename__ == "users"


def test_detection_model_tablename():
    assert Detection.__tablename__ == "detections"


def test_plate_read_model_tablename():
    assert PlateRead.__tablename__ == "plate_reads"


def test_hotlist_entry_model_tablename():
    assert HotListEntry.__tablename__ == "hotlist_entries"


def test_hotlist_alert_model_tablename():
    assert HotListAlert.__tablename__ == "hotlist_alerts"


def test_scan_session_model_tablename():
    assert ScanSession.__tablename__ == "scan_sessions"


def test_user_model_columns():
    columns = {c.name for c in User.__table__.columns}
    expected = {"id", "email", "hashed_password", "full_name", "role", "is_active", "created_at", "updated_at"}
    assert expected.issubset(columns)


def test_detection_model_columns():
    columns = {c.name for c in Detection.__table__.columns}
    expected = {
        "id", "agent_id", "session_id",
        "vehicle_type", "vehicle_color", "vehicle_make", "vehicle_model", "vehicle_year",
        "vehicle_confidence", "bbox_x", "bbox_y", "bbox_w", "bbox_h",
        "image_path", "thumbnail_path",
        "latitude", "longitude", "location", "address",
        "created_at",
    }
    assert expected.issubset(columns)


def test_hotlist_entry_model_columns():
    columns = {c.name for c in HotListEntry.__table__.columns}
    expected = {
        "id", "plate_text", "plate_state", "case_number",
        "lender_name", "order_type", "is_active", "priority",
    }
    assert expected.issubset(columns)
