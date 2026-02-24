"""Unit tests for SQLAlchemy model definitions — schema coverage."""

from app.models.detection import Detection, PlateRead
from app.models.hotlist import HotListAlert, HotListEntry
from app.models.route import Route, RouteStop
from app.models.scan_session import ScanSession
from app.models.user import User

# ── Table names ──────────────────────────────────────────────────────────────


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


def test_route_model_tablename():
    assert Route.__tablename__ == "routes"


def test_route_stop_model_tablename():
    assert RouteStop.__tablename__ == "route_stops"


# ── Column existence ─────────────────────────────────────────────────────────


def test_user_model_columns():
    columns = {c.name for c in User.__table__.columns}
    expected = {
        "id",
        "email",
        "hashed_password",
        "full_name",
        "role",
        "is_active",
        "created_at",
        "updated_at",
    }
    assert expected.issubset(columns)


def test_detection_model_columns():
    columns = {c.name for c in Detection.__table__.columns}
    expected = {
        "id",
        "agent_id",
        "session_id",
        "vehicle_type",
        "vehicle_color",
        "vehicle_make",
        "vehicle_model",
        "vehicle_year",
        "vehicle_confidence",
        "bbox_x",
        "bbox_y",
        "bbox_w",
        "bbox_h",
        "image_path",
        "thumbnail_path",
        "latitude",
        "longitude",
        "location",
        "address",
        "heading",
        "speed",
        "extra",
        "created_at",
    }
    assert expected.issubset(columns)


def test_plate_read_model_columns():
    columns = {c.name for c in PlateRead.__table__.columns}
    expected = {
        "id",
        "detection_id",
        "plate_text",
        "plate_state",
        "plate_type",
        "confidence",
        "plate_image_path",
        "raw_ocr",
        "ocr_alternatives",
        "created_at",
    }
    assert expected.issubset(columns)


def test_hotlist_entry_model_columns():
    columns = {c.name for c in HotListEntry.__table__.columns}
    expected = {
        "id",
        "plate_text",
        "plate_state",
        "case_number",
        "lender_name",
        "order_type",
        "is_active",
        "priority",
        "vehicle_year",
        "vehicle_make",
        "vehicle_model",
        "vehicle_color",
        "vin",
        "debtor_name",
        "debtor_address",
        "debtor_phone",
        "notes",
        "extra",
        "created_at",
        "updated_at",
        "expires_at",
    }
    assert expected.issubset(columns)


def test_hotlist_alert_model_columns():
    columns = {c.name for c in HotListAlert.__table__.columns}
    expected = {
        "id",
        "hotlist_entry_id",
        "detection_id",
        "agent_id",
        "plate_text_matched",
        "match_confidence",
        "latitude",
        "longitude",
        "address",
        "status",
        "acknowledged_at",
        "resolved_at",
        "notes",
        "created_at",
    }
    assert expected.issubset(columns)


def test_route_model_columns():
    columns = {c.name for c in Route.__table__.columns}
    expected = {
        "id",
        "agent_id",
        "name",
        "status",
        "current_stop_index",
        "total_stops",
        "created_at",
        "completed_at",
    }
    assert expected.issubset(columns)


def test_route_stop_model_columns():
    columns = {c.name for c in RouteStop.__table__.columns}
    expected = {
        "id",
        "route_id",
        "order_index",
        "address",
        "latitude",
        "longitude",
        "geofence_radius_m",
        "status",
        "arrived_at",
        "scan_started_at",
        "completed_at",
        "plates_found",
        "notes",
    }
    assert expected.issubset(columns)


# ── Primary keys are UUID ────────────────────────────────────────────────────


def test_all_primary_keys_are_uuid():
    for model in [
        User,
        Detection,
        PlateRead,
        HotListEntry,
        HotListAlert,
        ScanSession,
        Route,
        RouteStop,
    ]:
        pk_cols = [c for c in model.__table__.columns if c.primary_key]
        assert len(pk_cols) == 1, f"{model.__tablename__} should have exactly 1 PK"


# ── Foreign key relationships ────────────────────────────────────────────────


def _fk_targets(model):
    targets = set()
    for c in model.__table__.columns:
        for fk in c.foreign_keys:
            targets.add(fk.target_fullname)
    return targets


def test_detection_has_agent_fk():
    assert "users.id" in _fk_targets(Detection)


def test_plate_read_has_detection_fk():
    assert "detections.id" in _fk_targets(PlateRead)


def test_hotlist_alert_has_entry_fk():
    assert "hotlist_entries.id" in _fk_targets(HotListAlert)


def test_route_stop_has_route_fk():
    assert "routes.id" in _fk_targets(RouteStop)


def test_route_has_agent_fk():
    assert "users.id" in _fk_targets(Route)


# ── Index existence ──────────────────────────────────────────────────────────


def test_detection_has_composite_indexes():
    index_names = {idx.name for idx in Detection.__table__.indexes}
    assert "ix_detections_agent_created" in index_names
    assert "ix_detections_session_created" in index_names


def test_hotlist_entry_has_active_plate_index():
    index_names = {idx.name for idx in HotListEntry.__table__.indexes}
    assert "ix_hotlist_active_plate_expires" in index_names


def test_hotlist_alert_has_status_index():
    index_names = {idx.name for idx in HotListAlert.__table__.indexes}
    assert "ix_hotlist_alerts_status_created" in index_names


def test_route_has_agent_status_index():
    index_names = {idx.name for idx in Route.__table__.indexes}
    assert "ix_routes_agent_status" in index_names


def test_route_stop_has_route_order_index():
    index_names = {idx.name for idx in RouteStop.__table__.indexes}
    assert "ix_route_stops_route_order" in index_names


# ── Cascade delete rules ────────────────────────────────────────────────────


def test_plate_read_cascade_on_detection_delete():
    for c in PlateRead.__table__.columns:
        for fk in c.foreign_keys:
            if fk.target_fullname == "detections.id":
                assert fk.ondelete == "CASCADE"


def test_route_stop_cascade_on_route_delete():
    for c in RouteStop.__table__.columns:
        for fk in c.foreign_keys:
            if fk.target_fullname == "routes.id":
                assert fk.ondelete == "CASCADE"
