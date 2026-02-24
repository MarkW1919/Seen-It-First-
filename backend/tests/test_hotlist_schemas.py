"""Unit tests for Pydantic hotlist schemas — creation, update, response, import."""

import uuid
from datetime import UTC, datetime

from app.schemas.hotlist import (
    HotListAlertResponse,
    HotListAlertUpdate,
    HotListEntryCreate,
    HotListEntryResponse,
    HotListEntryUpdate,
    HotListImport,
)

# ── HotListEntryCreate ──────────────────────────────────────────────────────


def test_entry_create_minimal():
    e = HotListEntryCreate(plate_text="ABC1234")
    assert e.plate_text == "ABC1234"
    assert e.order_type == "repossession"
    assert e.priority == "normal"
    assert e.extra == {}
    assert e.expires_at is None


def test_entry_create_all_fields():
    e = HotListEntryCreate(
        plate_text="XYZ9876",
        plate_state="TX",
        case_number="CASE-001",
        lender_name="Big Bank",
        lender_contact="555-1234",
        order_type="voluntary",
        vehicle_year=2019,
        vehicle_make="Honda",
        vehicle_model="Accord",
        vehicle_color="Silver",
        vin="1HGCV1F3XKA000001",
        debtor_name="John Doe",
        debtor_address="456 Oak St",
        debtor_phone="555-5678",
        priority="high",
        notes="Last seen downtown",
        expires_at=datetime(2026, 12, 31, tzinfo=UTC),
        extra={"source": "csv_import"},
    )
    assert e.vehicle_make == "Honda"
    assert e.priority == "high"
    assert e.extra["source"] == "csv_import"


# ── HotListEntryUpdate ──────────────────────────────────────────────────────


def test_entry_update_partial():
    u = HotListEntryUpdate(is_active=False)
    dumped = u.model_dump(exclude_unset=True)
    assert dumped == {"is_active": False}


def test_entry_update_multiple_fields():
    u = HotListEntryUpdate(plate_text="NEW1234", priority="urgent", notes="Updated")
    dumped = u.model_dump(exclude_unset=True)
    assert "plate_text" in dumped
    assert "priority" in dumped
    assert "notes" in dumped
    assert "vehicle_make" not in dumped


# ── HotListEntryResponse ────────────────────────────────────────────────────


def test_entry_response_fields():
    now = datetime.now(UTC)
    r = HotListEntryResponse(
        id=uuid.uuid4(),
        plate_text="ABC1234",
        plate_state="AZ",
        case_number="C-100",
        lender_name="Lender",
        order_type="repossession",
        vehicle_year=2020,
        vehicle_make="Toyota",
        vehicle_model="Camry",
        vehicle_color="White",
        vin=None,
        debtor_name="Jane",
        debtor_address="789 Pine",
        is_active=True,
        priority="normal",
        notes=None,
        created_at=now,
        updated_at=now,
        expires_at=None,
    )
    assert r.is_active is True
    assert r.order_type == "repossession"


# ── HotListAlertResponse ────────────────────────────────────────────────────


def test_alert_response_fields():
    now = datetime.now(UTC)
    ar = HotListAlertResponse(
        id=uuid.uuid4(),
        hotlist_entry_id=uuid.uuid4(),
        detection_id=uuid.uuid4(),
        plate_text_matched="ABC1234",
        match_confidence=0.97,
        latitude=33.45,
        longitude=-112.07,
        address="123 Main",
        status="new",
        acknowledged_at=None,
        resolved_at=None,
        notes=None,
        created_at=now,
    )
    assert ar.status == "new"
    assert ar.match_confidence == 0.97


def test_alert_response_with_entry():
    now = datetime.now(UTC)
    entry = HotListEntryResponse(
        id=uuid.uuid4(),
        plate_text="ABC1234",
        plate_state=None,
        case_number=None,
        lender_name=None,
        order_type="repossession",
        vehicle_year=None,
        vehicle_make=None,
        vehicle_model=None,
        vehicle_color=None,
        vin=None,
        debtor_name=None,
        debtor_address=None,
        is_active=True,
        priority="normal",
        notes=None,
        created_at=now,
        updated_at=now,
        expires_at=None,
    )
    ar = HotListAlertResponse(
        id=uuid.uuid4(),
        hotlist_entry_id=entry.id,
        detection_id=None,
        plate_text_matched="ABC1234",
        match_confidence=0.95,
        latitude=None,
        longitude=None,
        address=None,
        status="acknowledged",
        acknowledged_at=now,
        resolved_at=None,
        notes="Confirmed",
        created_at=now,
        hotlist_entry=entry,
    )
    assert ar.hotlist_entry is not None
    assert ar.hotlist_entry.plate_text == "ABC1234"


# ── HotListAlertUpdate ──────────────────────────────────────────────────────


def test_alert_update_status_only():
    u = HotListAlertUpdate(status="resolved")
    assert u.status == "resolved"
    assert u.notes is None


def test_alert_update_notes_only():
    u = HotListAlertUpdate(notes="False positive, different vehicle")
    assert u.notes == "False positive, different vehicle"
    assert u.status is None


# ── HotListImport (bulk) ────────────────────────────────────────────────────


def test_bulk_import_schema():
    imp = HotListImport(
        entries=[
            HotListEntryCreate(plate_text="AAA111"),
            HotListEntryCreate(plate_text="BBB222", priority="high"),
        ]
    )
    assert len(imp.entries) == 2
    assert imp.entries[1].priority == "high"


def test_bulk_import_empty_list():
    imp = HotListImport(entries=[])
    assert imp.entries == []
