"""
Data repository: insert and query detections, alerts, and system events.
"""

import logging
import time
import math
from typing import Optional

from edge.storage.database import Database
from edge.inference.scheduler import PipelineResult
from edge.hotlist.matcher import HotlistAlert

logger = logging.getLogger(__name__)


class DetectionRepository:
    """
    Handles all database read/write operations for detections and alerts.
    """

    def __init__(self, db: Database):
        self.db = db

    def save_detection(
        self,
        result: PipelineResult,
        plate_text: str = "",
        plate_confidence: float = 0.0,
        vehicle_class: str = "",
        vehicle_color: str = "",
        year_bucket: str = "",
        bbox: tuple[int, int, int, int] = (0, 0, 0, 0),
        snapshot_path: str = "",
        detection_address: str = "",
    ) -> int:
        """Insert a detection record. Returns the row ID."""
        cursor = self.db.execute(
            """
            INSERT INTO detections
                (timestamp, camera_id, track_id, plate_text, plate_confidence,
                 vehicle_class, vehicle_color, year_bucket,
                 bbox_x1, bbox_y1, bbox_x2, bbox_y2,
                 snapshot_path, night_mode, detection_address)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                result.timestamp,
                result.camera_id,
                None,
                plate_text,
                plate_confidence,
                vehicle_class,
                vehicle_color,
                year_bucket,
                bbox[0], bbox[1], bbox[2], bbox[3],
                snapshot_path,
                1 if result.night_mode else 0,
                detection_address,
            ),
        )
        self.db.commit()
        return cursor.lastrowid

    def save_evidence_detection(
        self,
        timestamp:        float,
        camera_id:        str,
        track_id:         int | None,
        plate_text:       str,
        plate_confidence: float,
        vehicle_class:    str,
        bbox:             tuple[int, int, int, int] = (0, 0, 0, 0),
        vehicle_path:     str = "",
        plate_path:       str = "",
        composite_path:   str = "",
        night_mode:       bool = False,
        make:             str = "",
        model:            str = "",
        color:            str = "",
        year_range:       str = "",
        confidence:       float = 0.0,
        latitude:         float = 0.0,
        longitude:        float = 0.0,
        fingerprint:      str = "",
        detection_address: str = "",
    ) -> int:
        """
        Insert a confirmed-detection record that includes evidence image paths,
        full vehicle intelligence fields, and a vehicle fingerprint.

        Takes flat scalar args (no PipelineResult dependency) so it can be
        called directly from the evidence storage layer.  Returns the row ID.
        """
        cursor = self.db.execute(
            """
            INSERT INTO detections
                (timestamp, camera_id, track_id, plate_text, plate_confidence,
                 vehicle_class, vehicle_color, year_bucket,
                 make, model, year_range, confidence, latitude, longitude,
                 detection_address, fingerprint,
                 bbox_x1, bbox_y1, bbox_x2, bbox_y2,
                 snapshot_path, vehicle_path, plate_path, composite_path,
                 night_mode)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                timestamp,
                camera_id,
                track_id,
                plate_text,
                plate_confidence,
                vehicle_class,
                color,        # vehicle_color
                year_range,   # year_bucket (legacy col)
                make,
                model,
                year_range,
                confidence,
                latitude,
                longitude,
                detection_address,
                fingerprint,
                bbox[0], bbox[1], bbox[2], bbox[3],
                composite_path,   # snapshot_path = composite for dashboard compat
                vehicle_path,
                plate_path,
                composite_path,
                1 if night_mode else 0,
            ),
        )
        self.db.commit()
        return cursor.lastrowid

    def save_alert(self, alert: HotlistAlert) -> int:
        """Insert a hotlist alert record. Returns the row ID."""
        cursor = self.db.execute(
            """
            INSERT INTO hotlist_alerts
                (timestamp, plate_text, reason, priority,
                 confidence, camera_id, track_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                alert.timestamp,
                alert.plate,
                alert.reason,
                alert.priority,
                alert.confidence,
                alert.camera_id,
                alert.track_id,
            ),
        )
        self.db.commit()
        return cursor.lastrowid

    def save_thermal_event(
        self, gpu_temp: float, throttle_level: int, action: str
    ) -> int:
        cursor = self.db.execute(
            """
            INSERT INTO thermal_events (timestamp, gpu_temp_c, throttle_level, action)
            VALUES (?, ?, ?, ?)
            """,
            (time.time(), gpu_temp, throttle_level, action),
        )
        self.db.commit()
        return cursor.lastrowid

    def save_system_stats(
        self,
        gpu_temp: float,
        gpu_util: float,
        mem_used_mb: float,
        mem_total_mb: float,
        det_fps: float,
        cameras_active: int,
        tracks_active: int,
    ):
        self.db.execute(
            """
            INSERT INTO system_stats
                (timestamp, gpu_temp_c, gpu_util_pct, mem_used_mb,
                 mem_total_mb, det_fps, cameras_active, tracks_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                time.time(), gpu_temp, gpu_util, mem_used_mb,
                mem_total_mb, det_fps, cameras_active, tracks_active,
            ),
        )
        self.db.commit()

    def get_recent_detections(self, limit: int = 100) -> list[dict]:
        cursor = self.db.execute(
            "SELECT * FROM detections ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_recent_alerts(self, limit: int = 50) -> list[dict]:
        cursor = self.db.execute(
            "SELECT * FROM hotlist_alerts ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        )
        return [dict(row) for row in cursor.fetchall()]

    def search_plate(self, plate_text: str) -> list[dict]:
        cursor = self.db.execute(
            "SELECT * FROM detections WHERE plate_text = ? ORDER BY timestamp DESC",
            (plate_text.upper().strip(),),
        )
        return [dict(row) for row in cursor.fetchall()]


    def search_detections(
        self,
        plate_text: str = "",
        vehicle_class: str = "",
        make: str = "",
        model: str = "",
        detection_address: str = "",
        limit: int = 200,
    ) -> list[dict]:
        clauses = []
        params: list[object] = []

        if plate_text.strip():
            clauses.append("UPPER(COALESCE(plate_text,'')) LIKE ?")
            params.append(f"%{plate_text.upper().strip()}%")
        if vehicle_class.strip():
            clauses.append("LOWER(COALESCE(vehicle_class,'')) LIKE ?")
            params.append(f"%{vehicle_class.lower().strip()}%")
        if make.strip():
            clauses.append("LOWER(COALESCE(make,'')) LIKE ?")
            params.append(f"%{make.lower().strip()}%")
        if model.strip():
            clauses.append("LOWER(COALESCE(model,'')) LIKE ?")
            params.append(f"%{model.lower().strip()}%")
        if detection_address.strip():
            clauses.append("LOWER(COALESCE(detection_address,'')) LIKE ?")
            params.append(f"%{detection_address.lower().strip()}%")

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        q = f"SELECT * FROM detections {where} ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        cursor = self.db.execute(q, tuple(params))
        return [dict(row) for row in cursor.fetchall()]

    @staticmethod
    def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        r = 6371000.0
        p1, p2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dl = math.radians(lon2 - lon1)
        a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
        return 2 * r * math.asin(math.sqrt(a))

    def search_detections_near(
        self,
        lat: float,
        lon: float,
        radius_m: float = 120.0,
        plate_text: str = "",
        vehicle_class: str = "",
        make: str = "",
        model: str = "",
        limit: int = 300,
    ) -> list[dict]:
        rows = self.search_detections(
            plate_text=plate_text,
            vehicle_class=vehicle_class,
            make=make,
            model=model,
            limit=limit,
        )
        out = []
        for row in rows:
            rlat = row.get("latitude")
            rlon = row.get("longitude")
            if rlat is None or rlon is None:
                continue
            try:
                dist = self._haversine_m(float(lat), float(lon), float(rlat), float(rlon))
            except Exception:
                continue
            if dist <= radius_m:
                row["distance_m"] = round(dist, 2)
                out.append(row)
        out.sort(key=lambda x: x.get("distance_m", 1e9))
        return out

    def get_detection_by_id(self, detection_id: int) -> dict | None:
        cursor = self.db.execute("SELECT * FROM detections WHERE id = ?", (detection_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_detection_count(self) -> int:
        cursor = self.db.execute("SELECT COUNT(*) FROM detections")
        return cursor.fetchone()[0]

    def get_alert_count(self) -> int:
        cursor = self.db.execute("SELECT COUNT(*) FROM hotlist_alerts")
        return cursor.fetchone()[0]

    def prune_old_detections(self, max_rows: int = 1000000):
        """Delete oldest detections if count exceeds max."""
        count = self.get_detection_count()
        if count > max_rows:
            delete_count = count - max_rows
            self.db.execute(
                """
                DELETE FROM detections WHERE id IN (
                    SELECT id FROM detections ORDER BY timestamp ASC LIMIT ?
                )
                """,
                (delete_count,),
            )
            self.db.commit()
            logger.info("Pruned %d old detections", delete_count)
