-- =============================================================================
-- SEEN IT FIRST - Edge AI Vehicle LPR System
-- SQLite Database Schema v1
-- =============================================================================
-- Target: SQLite 3.35+ via aiosqlite
-- Primary keys: TEXT (UUID4 generated in Python)
-- Timestamps: TEXT (ISO 8601 format)
-- Booleans: INTEGER (0 = false, 1 = true)
-- US license plates only
-- =============================================================================

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- -----------------------------------------------------------------------------
-- vehicles: every detected vehicle frame capture
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS vehicles (
    id                    TEXT PRIMARY KEY,
    camera_id             TEXT NOT NULL,
    housing_id            TEXT NOT NULL,
    vehicle_type          TEXT NOT NULL,
    color                 TEXT,
    make                  TEXT,
    model                 TEXT,
    year_bucket           TEXT,
    detection_confidence  REAL NOT NULL,
    bbox_x                INTEGER,
    bbox_y                INTEGER,
    bbox_w                INTEGER,
    bbox_h                INTEGER,
    image_path            TEXT,
    thumbnail_path        TEXT,
    created_at            TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%f', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_vehicles_camera   ON vehicles(camera_id);
CREATE INDEX IF NOT EXISTS idx_vehicles_created  ON vehicles(created_at);
CREATE INDEX IF NOT EXISTS idx_vehicles_type     ON vehicles(vehicle_type);

-- -----------------------------------------------------------------------------
-- plates: OCR results linked to a vehicle detection
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS plates (
    id                TEXT PRIMARY KEY,
    vehicle_id        TEXT NOT NULL REFERENCES vehicles(id),
    plate_text        TEXT NOT NULL,
    plate_state       TEXT,
    ocr_confidence    REAL NOT NULL,
    plate_image_path  TEXT,
    raw_ocr           TEXT,
    created_at        TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%f', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_plates_text     ON plates(plate_text);
CREATE INDEX IF NOT EXISTS idx_plates_vehicle  ON plates(vehicle_id);
CREATE INDEX IF NOT EXISTS idx_plates_state    ON plates(plate_state);

-- -----------------------------------------------------------------------------
-- detections: fused vehicle+plate event record
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS detections (
    id                TEXT PRIMARY KEY,
    vehicle_id        TEXT NOT NULL REFERENCES vehicles(id),
    plate_id          TEXT REFERENCES plates(id),
    fused_confidence  REAL NOT NULL,
    hotlist_match     INTEGER NOT NULL DEFAULT 0,
    alert_sent        INTEGER NOT NULL DEFAULT 0,
    video_clip_path   TEXT,
    created_at        TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%f', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_detections_created  ON detections(created_at);
CREATE INDEX IF NOT EXISTS idx_detections_vehicle  ON detections(vehicle_id);
CREATE INDEX IF NOT EXISTS idx_detections_hotlist  ON detections(hotlist_match) WHERE hotlist_match = 1;

-- -----------------------------------------------------------------------------
-- addresses: geo-fenced locations for camera housings
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS addresses (
    id              TEXT PRIMARY KEY,
    label           TEXT NOT NULL,
    address         TEXT,
    latitude        REAL,
    longitude       REAL,
    radius_meters   REAL DEFAULT 100.0,
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%f', 'now'))
);

-- -----------------------------------------------------------------------------
-- hotlist: plates of interest (repo, stolen, BOLO, etc.)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS hotlist (
    id              TEXT PRIMARY KEY,
    plate_text      TEXT NOT NULL,
    plate_state     TEXT,
    case_number     TEXT,
    lender_name     TEXT,
    order_type      TEXT,
    vehicle_year    TEXT,
    vehicle_make    TEXT,
    vehicle_model   TEXT,
    vehicle_color   TEXT,
    vin             TEXT,
    debtor_name     TEXT,
    debtor_address  TEXT,
    is_active       INTEGER NOT NULL DEFAULT 1,
    priority        INTEGER NOT NULL DEFAULT 3,
    notes           TEXT,
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%f', 'now')),
    updated_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%f', 'now')),
    expires_at      TEXT
);

CREATE INDEX IF NOT EXISTS idx_hotlist_plate   ON hotlist(plate_text) WHERE is_active = 1;
CREATE INDEX IF NOT EXISTS idx_hotlist_active  ON hotlist(is_active);
CREATE INDEX IF NOT EXISTS idx_hotlist_expiry  ON hotlist(expires_at) WHERE expires_at IS NOT NULL;

-- -----------------------------------------------------------------------------
-- system_logs: structured application log sink
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS system_logs (
    id          TEXT PRIMARY KEY,
    level       TEXT NOT NULL,
    source      TEXT NOT NULL,
    message     TEXT NOT NULL,
    details     TEXT,
    created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%f', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_logs_level    ON system_logs(level);
CREATE INDEX IF NOT EXISTS idx_logs_created  ON system_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_logs_source   ON system_logs(source);

-- -----------------------------------------------------------------------------
-- schema_version: migration tracking
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER NOT NULL
);
