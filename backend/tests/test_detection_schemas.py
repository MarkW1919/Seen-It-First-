"""Unit tests for Pydantic detection and plate-read schemas — validation, defaults."""
import uuid
from datetime import datetime

from app.schemas.detection import (
    PlateReadCreate,
    PlateReadResponse,
    DetectionCreate,
    DetectionResponse,
    DetectionList,
)


# ── PlateReadCreate ──────────────────────────────────────────────────────────


def test_plate_read_create_minimal():
    pr = PlateReadCreate(plate_text="ABC1234", confidence=0.95)
    assert pr.plate_text == "ABC1234"
    assert pr.confidence == 0.95
    assert pr.plate_state is None
    assert pr.plate_type is None
    assert pr.ocr_alternatives == {}


def test_plate_read_create_all_fields():
    pr = PlateReadCreate(
        plate_text="XYZ9876",
        plate_state="CA",
        plate_type="passenger",
        confidence=0.88,
        plate_image_path="/data/plates/img.jpg",
        plate_bbox_x=10,
        plate_bbox_y=20,
        plate_bbox_w=100,
        plate_bbox_h=50,
        raw_ocr="XYZ 9876",
        ocr_alternatives={"alt1": "XY29876"},
    )
    assert pr.plate_state == "CA"
    assert pr.plate_bbox_w == 100
    assert pr.ocr_alternatives["alt1"] == "XY29876"


# ── DetectionCreate ──────────────────────────────────────────────────────────


def test_detection_create_defaults():
    dc = DetectionCreate()
    assert dc.session_id is None
    assert dc.vehicle_type is None
    assert dc.latitude is None
    assert dc.longitude is None
    assert dc.extra == {}
    assert dc.plate_reads == []


def test_detection_create_with_plates():
    dc = DetectionCreate(
        vehicle_type="sedan",
        vehicle_confidence=0.9,
        latitude=33.45,
        longitude=-112.07,
        plate_reads=[
            PlateReadCreate(plate_text="ABC1234", confidence=0.95),
            PlateReadCreate(plate_text="DEF5678", confidence=0.80),
        ],
    )
    assert len(dc.plate_reads) == 2
    assert dc.plate_reads[0].plate_text == "ABC1234"


def test_detection_create_with_session_id():
    sid = uuid.uuid4()
    dc = DetectionCreate(session_id=sid)
    assert dc.session_id == sid


def test_detection_create_bbox_fields():
    dc = DetectionCreate(bbox_x=100, bbox_y=200, bbox_w=300, bbox_h=150)
    assert dc.bbox_x == 100
    assert dc.bbox_w == 300


def test_detection_create_heading_and_speed():
    dc = DetectionCreate(heading=180.5, speed=35.0)
    assert dc.heading == 180.5
    assert dc.speed == 35.0


def test_detection_create_extra_dict():
    dc = DetectionCreate(extra={"source": "cam1", "night_mode": True})
    assert dc.extra["source"] == "cam1"


# ── DetectionResponse ────────────────────────────────────────────────────────


def test_detection_response_from_dict():
    now = datetime.utcnow()
    dr = DetectionResponse(
        id=uuid.uuid4(),
        agent_id=uuid.uuid4(),
        session_id=None,
        vehicle_type="truck",
        vehicle_color="blue",
        vehicle_make="Ford",
        vehicle_model="F-150",
        vehicle_year=2020,
        vehicle_confidence=0.85,
        image_path="/data/img.jpg",
        thumbnail_path="/data/thumb.jpg",
        latitude=33.45,
        longitude=-112.07,
        address="123 Main St",
        heading=90.0,
        speed=25.0,
        extra={},
        created_at=now,
        plate_reads=[],
    )
    assert dr.vehicle_make == "Ford"
    assert dr.plate_reads == []


def test_detection_response_with_plate_reads():
    now = datetime.utcnow()
    pr = PlateReadResponse(
        id=uuid.uuid4(),
        plate_text="ABC1234",
        plate_state="AZ",
        plate_type=None,
        confidence=0.95,
        plate_image_path=None,
        raw_ocr="ABC1234",
        created_at=now,
    )
    dr = DetectionResponse(
        id=uuid.uuid4(),
        agent_id=None,
        session_id=None,
        vehicle_type=None,
        vehicle_color=None,
        vehicle_make=None,
        vehicle_model=None,
        vehicle_year=None,
        vehicle_confidence=None,
        image_path=None,
        thumbnail_path=None,
        latitude=None,
        longitude=None,
        address=None,
        heading=None,
        speed=None,
        extra={},
        created_at=now,
        plate_reads=[pr],
    )
    assert len(dr.plate_reads) == 1
    assert dr.plate_reads[0].plate_text == "ABC1234"


# ── DetectionList ────────────────────────────────────────────────────────────


def test_detection_list_structure():
    dl = DetectionList(items=[], total=0, page=1, page_size=50)
    assert dl.items == []
    assert dl.total == 0
    assert dl.page == 1
    assert dl.page_size == 50


def test_detection_list_with_items():
    now = datetime.utcnow()
    item = DetectionResponse(
        id=uuid.uuid4(),
        agent_id=None,
        session_id=None,
        vehicle_type="suv",
        vehicle_color=None,
        vehicle_make=None,
        vehicle_model=None,
        vehicle_year=None,
        vehicle_confidence=0.7,
        image_path=None,
        thumbnail_path=None,
        latitude=None,
        longitude=None,
        address=None,
        heading=None,
        speed=None,
        extra={},
        created_at=now,
    )
    dl = DetectionList(items=[item], total=1, page=1, page_size=50)
    assert dl.total == 1
    assert dl.items[0].vehicle_type == "suv"
