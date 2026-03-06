-- Seen-It-First-Edge SQLite Schema
-- Phase 1: Local detection storage

CREATE TABLE IF NOT EXISTS detections (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp       REAL    NOT NULL,
    camera_id       TEXT    NOT NULL,
    track_id        INTEGER,
    plate_text      TEXT,
    plate_confidence REAL,
    vehicle_class   TEXT,
    vehicle_color   TEXT,
    year_bucket     TEXT,
    -- Extended classification fields
    make            TEXT,
    model           TEXT,
    year_range      TEXT,
    confidence      REAL,
    -- GPS (operator position at detection time)
    latitude        REAL,
    longitude       REAL,
    -- Bounding box
    bbox_x1         INTEGER,
    bbox_y1         INTEGER,
    bbox_x2         INTEGER,
    bbox_y2         INTEGER,
    -- Vehicle fingerprint (type-make-model-year-color-hash)
    fingerprint     TEXT,
    -- Evidence image paths
    snapshot_path   TEXT,
    vehicle_path    TEXT,
    plate_path      TEXT,
    composite_path  TEXT,
    night_mode      INTEGER DEFAULT 0,
    created_at      TEXT    DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_detections_timestamp ON detections(timestamp);
CREATE INDEX IF NOT EXISTS idx_detections_plate ON detections(plate_text);
CREATE INDEX IF NOT EXISTS idx_detections_camera ON detections(camera_id);

CREATE TABLE IF NOT EXISTS hotlist_alerts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp       REAL    NOT NULL,
    plate_text      TEXT    NOT NULL,
    reason          TEXT,
    priority        TEXT,
    confidence      REAL,
    camera_id       TEXT    NOT NULL,
    track_id        INTEGER,
    acknowledged    INTEGER DEFAULT 0,
    created_at      TEXT    DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_alerts_timestamp ON hotlist_alerts(timestamp);
CREATE INDEX IF NOT EXISTS idx_alerts_plate ON hotlist_alerts(plate_text);

CREATE TABLE IF NOT EXISTS thermal_events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp       REAL    NOT NULL,
    gpu_temp_c      REAL    NOT NULL,
    throttle_level  INTEGER NOT NULL,
    action          TEXT,
    created_at      TEXT    DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS system_stats (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp       REAL    NOT NULL,
    gpu_temp_c      REAL,
    gpu_util_pct    REAL,
    mem_used_mb     REAL,
    mem_total_mb    REAL,
    det_fps         REAL,
    cameras_active  INTEGER,
    tracks_active   INTEGER,
    created_at      TEXT    DEFAULT (datetime('now'))
);
