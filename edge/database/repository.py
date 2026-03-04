"""
SEEN IT FIRST - Edge AI Vehicle LPR System
Async data-access layer (repository pattern) over raw aiosqlite.

Every public method is an ``async`` coroutine.  The repository never opens its
own connections -- it receives a :class:`DatabaseConnection` instance at
construction time and delegates all IO through it.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from edge.database.connection import DatabaseConnection
from edge.database.models import (
    Detection,
    HotlistEntry,
    Plate,
    SystemLog,
    Vehicle,
    _new_id,
    _now_iso,
)

logger = logging.getLogger("sif.database.repository")


class DetectionRepository:
    """Async CRUD facade for the SEEN IT FIRST edge database."""

    def __init__(self, db: DatabaseConnection) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # Vehicle
    # ------------------------------------------------------------------

    async def insert_vehicle(self, vehicle: Vehicle) -> str:
        """Persist a Vehicle row and return its ``id``."""
        d = vehicle.to_dict()
        cols = ", ".join(d.keys())
        placeholders = ", ".join("?" for _ in d)
        sql = f"INSERT INTO vehicles ({cols}) VALUES ({placeholders})"
        try:
            await self._db.execute(sql, list(d.values()))
            logger.info("Inserted vehicle %s (camera=%s)", vehicle.id, vehicle.camera_id)
        except Exception:
            logger.exception("Failed to insert vehicle %s", vehicle.id)
            raise
        return vehicle.id

    # ------------------------------------------------------------------
    # Plate
    # ------------------------------------------------------------------

    async def insert_plate(self, plate: Plate) -> str:
        """Persist a Plate row and return its ``id``."""
        d = plate.to_dict()
        cols = ", ".join(d.keys())
        placeholders = ", ".join("?" for _ in d)
        sql = f"INSERT INTO plates ({cols}) VALUES ({placeholders})"
        try:
            await self._db.execute(sql, list(d.values()))
            logger.info("Inserted plate %s (text=%s)", plate.id, plate.plate_text)
        except Exception:
            logger.exception("Failed to insert plate %s", plate.id)
            raise
        return plate.id

    # ------------------------------------------------------------------
    # Detection
    # ------------------------------------------------------------------

    async def insert_detection(self, detection: Detection) -> str:
        """Persist a Detection row and return its ``id``."""
        d = detection.to_dict()
        cols = ", ".join(d.keys())
        placeholders = ", ".join("?" for _ in d)
        sql = f"INSERT INTO detections ({cols}) VALUES ({placeholders})"
        try:
            await self._db.execute(sql, list(d.values()))
            logger.info(
                "Inserted detection %s (hotlist_match=%s)",
                detection.id,
                detection.hotlist_match,
            )
        except Exception:
            logger.exception("Failed to insert detection %s", detection.id)
            raise
        return detection.id

    # ------------------------------------------------------------------
    # Plate search
    # ------------------------------------------------------------------

    async def search_plates(
        self, text: str, exact: bool = True
    ) -> list[Plate]:
        """Search plates by ``plate_text``.

        Parameters
        ----------
        text:
            The plate text to match.
        exact:
            When *True* an exact (case-insensitive) match is used.
            When *False* a ``LIKE`` partial match with surrounding ``%``
            wildcards is applied.
        """
        normalised = text.strip().upper()
        if exact:
            sql = "SELECT * FROM plates WHERE UPPER(plate_text) = ?"
            params: list[Any] = [normalised]
        else:
            sql = "SELECT * FROM plates WHERE UPPER(plate_text) LIKE ?"
            params = [f"%{normalised}%"]

        try:
            rows = await self._db.fetchall(sql, params)
            results = [Plate.from_row(r) for r in rows]
            logger.debug(
                "search_plates text=%s exact=%s -> %d results",
                text,
                exact,
                len(results),
            )
            return results
        except Exception:
            logger.exception("search_plates failed text=%s exact=%s", text, exact)
            raise

    # ------------------------------------------------------------------
    # Detection queries (joined)
    # ------------------------------------------------------------------

    async def get_detections(
        self,
        limit: int = 50,
        offset: int = 0,
        camera_id: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        hotlist_only: bool = False,
    ) -> list[dict]:
        """Return joined detection + vehicle + plate rows.

        Results are ordered by ``detections.created_at DESC``.
        """
        sql = """
            SELECT
                d.id            AS detection_id,
                d.fused_confidence,
                d.hotlist_match,
                d.alert_sent,
                d.video_clip_path,
                d.created_at    AS detection_created_at,
                v.id            AS vehicle_id,
                v.camera_id,
                v.housing_id,
                v.vehicle_type,
                v.color,
                v.make,
                v.model,
                v.year_bucket,
                v.detection_confidence,
                v.bbox_x,
                v.bbox_y,
                v.bbox_w,
                v.bbox_h,
                v.image_path,
                v.thumbnail_path,
                p.id            AS plate_id,
                p.plate_text,
                p.plate_state,
                p.ocr_confidence,
                p.plate_image_path,
                p.raw_ocr
            FROM detections d
            JOIN vehicles v ON v.id = d.vehicle_id
            LEFT JOIN plates p ON p.id = d.plate_id
            WHERE 1 = 1
        """
        params: list[Any] = []

        if camera_id is not None:
            sql += " AND v.camera_id = ?"
            params.append(camera_id)
        if start_date is not None:
            sql += " AND d.created_at >= ?"
            params.append(start_date)
        if end_date is not None:
            sql += " AND d.created_at <= ?"
            params.append(end_date)
        if hotlist_only:
            sql += " AND d.hotlist_match = 1"

        sql += " ORDER BY d.created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        try:
            rows = await self._db.fetchall(sql, params)
            results = [dict(r) for r in rows]
            logger.debug("get_detections -> %d rows (limit=%d offset=%d)", len(results), limit, offset)
            return results
        except Exception:
            logger.exception("get_detections failed")
            raise

    async def get_detection_by_id(self, detection_id: str) -> Optional[dict]:
        """Return a single joined detection record, or ``None``."""
        sql = """
            SELECT
                d.id            AS detection_id,
                d.fused_confidence,
                d.hotlist_match,
                d.alert_sent,
                d.video_clip_path,
                d.created_at    AS detection_created_at,
                v.id            AS vehicle_id,
                v.camera_id,
                v.housing_id,
                v.vehicle_type,
                v.color,
                v.make,
                v.model,
                v.year_bucket,
                v.detection_confidence,
                v.bbox_x,
                v.bbox_y,
                v.bbox_w,
                v.bbox_h,
                v.image_path,
                v.thumbnail_path,
                p.id            AS plate_id,
                p.plate_text,
                p.plate_state,
                p.ocr_confidence,
                p.plate_image_path,
                p.raw_ocr
            FROM detections d
            JOIN vehicles v ON v.id = d.vehicle_id
            LEFT JOIN plates p ON p.id = d.plate_id
            WHERE d.id = ?
        """
        try:
            row = await self._db.fetchone(sql, [detection_id])
            if row is None:
                logger.debug("get_detection_by_id %s -> not found", detection_id)
                return None
            result = dict(row)
            logger.debug("get_detection_by_id %s -> found", detection_id)
            return result
        except Exception:
            logger.exception("get_detection_by_id failed id=%s", detection_id)
            raise

    # ------------------------------------------------------------------
    # Hotlist
    # ------------------------------------------------------------------

    async def get_hotlist_entries(
        self, active_only: bool = True
    ) -> list[HotlistEntry]:
        """Return hotlist entries, optionally limited to active ones."""
        if active_only:
            sql = "SELECT * FROM hotlist WHERE is_active = 1 ORDER BY priority ASC, created_at DESC"
        else:
            sql = "SELECT * FROM hotlist ORDER BY priority ASC, created_at DESC"

        try:
            rows = await self._db.fetchall(sql)
            results = [HotlistEntry.from_row(r) for r in rows]
            logger.debug(
                "get_hotlist_entries active_only=%s -> %d entries",
                active_only,
                len(results),
            )
            return results
        except Exception:
            logger.exception("get_hotlist_entries failed active_only=%s", active_only)
            raise

    async def add_hotlist_entry(self, entry: HotlistEntry) -> str:
        """Insert a hotlist entry and return its ``id``."""
        d = entry.to_dict()
        cols = ", ".join(d.keys())
        placeholders = ", ".join("?" for _ in d)
        sql = f"INSERT INTO hotlist ({cols}) VALUES ({placeholders})"
        try:
            await self._db.execute(sql, list(d.values()))
            logger.info(
                "Added hotlist entry %s (plate=%s priority=%d)",
                entry.id,
                entry.plate_text,
                entry.priority,
            )
        except Exception:
            logger.exception("Failed to add hotlist entry %s", entry.id)
            raise
        return entry.id

    async def update_hotlist_entry(
        self, entry_id: str, updates: dict[str, Any]
    ) -> bool:
        """Apply *updates* to a hotlist entry.  Returns ``True`` on success."""
        if not updates:
            logger.warning("update_hotlist_entry called with empty updates for %s", entry_id)
            return False

        # Always bump updated_at
        updates["updated_at"] = _now_iso()

        set_clause = ", ".join(f"{k} = ?" for k in updates)
        params = list(updates.values()) + [entry_id]
        sql = f"UPDATE hotlist SET {set_clause} WHERE id = ?"

        try:
            cursor = await self._db.execute(sql, params)
            changed = cursor.rowcount > 0
            if changed:
                logger.info("Updated hotlist entry %s fields=%s", entry_id, list(updates.keys()))
            else:
                logger.warning("update_hotlist_entry %s: no row matched", entry_id)
            return changed
        except Exception:
            logger.exception("update_hotlist_entry failed id=%s", entry_id)
            raise

    async def deactivate_hotlist_entry(self, entry_id: str) -> bool:
        """Mark a hotlist entry as inactive.  Returns ``True`` on success."""
        return await self.update_hotlist_entry(
            entry_id, {"is_active": 0}
        )

    async def get_active_hotlist_plates(self) -> set[str]:
        """Return the set of normalised plate strings for all active hotlist entries.

        Plates are uppercased and stripped so callers can perform O(1) membership
        tests against incoming OCR output.
        """
        sql = "SELECT plate_text FROM hotlist WHERE is_active = 1"
        try:
            rows = await self._db.fetchall(sql)
            plates = {str(r["plate_text"]).strip().upper() for r in rows}
            logger.debug("get_active_hotlist_plates -> %d plates loaded", len(plates))
            return plates
        except Exception:
            logger.exception("get_active_hotlist_plates failed")
            raise

    # ------------------------------------------------------------------
    # System logs
    # ------------------------------------------------------------------

    async def insert_system_log(
        self,
        level: str,
        source: str,
        message: str,
        details: Optional[str] = None,
    ) -> str:
        """Write a structured log entry and return its ``id``."""
        log = SystemLog(
            level=level.upper(),
            source=source,
            message=message,
            details=details,
        )
        d = log.to_dict()
        cols = ", ".join(d.keys())
        placeholders = ", ".join("?" for _ in d)
        sql = f"INSERT INTO system_logs ({cols}) VALUES ({placeholders})"
        try:
            await self._db.execute(sql, list(d.values()))
            logger.debug(
                "Inserted system_log %s [%s] %s: %s",
                log.id,
                log.level,
                log.source,
                log.message,
            )
        except Exception:
            logger.exception("Failed to insert system_log")
            raise
        return log.id

    async def get_system_logs(
        self, limit: int = 100, level: Optional[str] = None
    ) -> list[SystemLog]:
        """Retrieve recent system log entries."""
        params: list[Any] = []
        if level is not None:
            sql = "SELECT * FROM system_logs WHERE level = ? ORDER BY created_at DESC LIMIT ?"
            params = [level.upper(), limit]
        else:
            sql = "SELECT * FROM system_logs ORDER BY created_at DESC LIMIT ?"
            params = [limit]

        try:
            rows = await self._db.fetchall(sql, params)
            results = [SystemLog.from_row(r) for r in rows]
            logger.debug(
                "get_system_logs level=%s -> %d entries",
                level,
                len(results),
            )
            return results
        except Exception:
            logger.exception("get_system_logs failed level=%s", level)
            raise
