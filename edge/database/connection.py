"""
SEEN IT FIRST - Edge AI Vehicle LPR System
SQLite async connection manager using aiosqlite.

Provides DatabaseConnection with WAL mode, foreign keys, busy timeout,
schema initialization, and full async context manager support.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Optional, Sequence

import aiosqlite

logger = logging.getLogger("sif.database.connection")

# Default database path relative to project working directory
DEFAULT_DB_PATH = os.path.join("data", "seen_it_first.db")

# Location of the schema file (same directory as this module)
_SCHEMA_PATH = Path(__file__).parent / "schema.sql"


class DatabaseConnection:
    """Async SQLite connection manager for the SEEN IT FIRST edge database.

    Usage::

        async with DatabaseConnection(db_path="data/seen_it_first.db") as db:
            rows = await db.fetchall("SELECT * FROM vehicles LIMIT 10")
    """

    def __init__(self, db_path: Optional[str] = None) -> None:
        self._db_path: str = db_path or DEFAULT_DB_PATH
        self._conn: Optional[aiosqlite.Connection] = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def connect(self, db_path: Optional[str] = None) -> None:
        """Open the database connection and apply runtime pragmas.

        Parameters
        ----------
        db_path:
            Override the path set at construction time.  When *None* the
            original path is kept.
        """
        if db_path is not None:
            self._db_path = db_path

        # Ensure the parent directory exists
        db_dir = os.path.dirname(os.path.abspath(self._db_path))
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
            logger.debug("Ensured database directory exists: %s", db_dir)

        logger.info("Opening SQLite connection: %s", self._db_path)
        self._conn = await aiosqlite.connect(self._db_path)

        # Return rows as sqlite3.Row so columns are accessible by name
        self._conn.row_factory = aiosqlite.Row

        # Enable WAL mode for concurrent readers
        await self._conn.execute("PRAGMA journal_mode = WAL")
        # Enable foreign-key enforcement
        await self._conn.execute("PRAGMA foreign_keys = ON")
        # Busy timeout: wait up to 5 s when the database is locked
        await self._conn.execute("PRAGMA busy_timeout = 5000")

        logger.info(
            "SQLite connection ready (WAL, FK enabled, busy_timeout=5000ms): %s",
            self._db_path,
        )

    async def close(self) -> None:
        """Close the database connection gracefully."""
        if self._conn is not None:
            logger.info("Closing SQLite connection: %s", self._db_path)
            try:
                await self._conn.close()
            except Exception:
                logger.exception("Error closing SQLite connection")
            finally:
                self._conn = None

    # ------------------------------------------------------------------
    # Async context manager
    # ------------------------------------------------------------------

    async def __aenter__(self) -> "DatabaseConnection":
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:  # noqa: ANN001
        await self.close()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ensure_connected(self) -> aiosqlite.Connection:
        """Raise if the connection has not been opened yet."""
        if self._conn is None:
            raise RuntimeError(
                "DatabaseConnection is not open. "
                "Call connect() or use 'async with DatabaseConnection(...)' first."
            )
        return self._conn

    # ------------------------------------------------------------------
    # Query API
    # ------------------------------------------------------------------

    async def execute(
        self, sql: str, params: Optional[Sequence[Any]] = None
    ) -> aiosqlite.Cursor:
        """Execute a single SQL statement and commit.

        Returns the cursor for last-row-id / rowcount inspection.
        """
        conn = self._ensure_connected()
        try:
            cursor = await conn.execute(sql, params or ())
            await conn.commit()
            return cursor
        except Exception:
            logger.exception("execute failed | sql=%s params=%s", sql, params)
            raise

    async def executemany(
        self, sql: str, params_list: Sequence[Sequence[Any]]
    ) -> aiosqlite.Cursor:
        """Execute a statement against every parameter set and commit."""
        conn = self._ensure_connected()
        try:
            cursor = await conn.executemany(sql, params_list)
            await conn.commit()
            return cursor
        except Exception:
            logger.exception("executemany failed | sql=%s rows=%d", sql, len(params_list))
            raise

    async def fetchone(
        self, sql: str, params: Optional[Sequence[Any]] = None
    ) -> Optional[aiosqlite.Row]:
        """Execute *sql* and return the first row, or ``None``."""
        conn = self._ensure_connected()
        try:
            cursor = await conn.execute(sql, params or ())
            return await cursor.fetchone()
        except Exception:
            logger.exception("fetchone failed | sql=%s params=%s", sql, params)
            raise

    async def fetchall(
        self, sql: str, params: Optional[Sequence[Any]] = None
    ) -> list[aiosqlite.Row]:
        """Execute *sql* and return every matching row."""
        conn = self._ensure_connected()
        try:
            cursor = await conn.execute(sql, params or ())
            return await cursor.fetchall()
        except Exception:
            logger.exception("fetchall failed | sql=%s params=%s", sql, params)
            raise

    # ------------------------------------------------------------------
    # Schema bootstrap
    # ------------------------------------------------------------------

    async def init_schema(self) -> None:
        """Read *schema.sql* from the package directory and execute it.

        Safe to call multiple times thanks to ``CREATE TABLE IF NOT EXISTS``.
        """
        conn = self._ensure_connected()
        schema_file = _SCHEMA_PATH
        if not schema_file.is_file():
            logger.error("Schema file not found: %s", schema_file)
            raise FileNotFoundError(f"Schema file not found: {schema_file}")

        logger.info("Initialising database schema from %s", schema_file)
        sql = schema_file.read_text(encoding="utf-8")

        try:
            await conn.executescript(sql)
            logger.info("Database schema initialised successfully")
        except Exception:
            logger.exception("Failed to initialise database schema")
            raise

    # ------------------------------------------------------------------
    # Convenience / introspection
    # ------------------------------------------------------------------

    @property
    def db_path(self) -> str:
        """Return the database file path."""
        return self._db_path

    @property
    def is_connected(self) -> bool:
        """Return ``True`` when the underlying connection is open."""
        return self._conn is not None
