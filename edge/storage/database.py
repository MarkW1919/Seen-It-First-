"""
SQLite database connection and schema initialization.

Thread-safe via WAL mode and connection-per-thread pattern.
"""

import logging
import sqlite3
import threading
from pathlib import Path

logger = logging.getLogger(__name__)

SCHEMA_PATH = Path(__file__).parent / "schema.sql"


class Database:
    """
    SQLite database manager with WAL mode for concurrent reads.

    Uses a per-thread connection pattern for thread safety.
    """

    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self._local = threading.local()
        self._initialized = False

    def initialize(self) -> bool:
        """Create database file, apply schema, enable WAL."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            conn = self._get_connection()
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA cache_size=-8000")  # 8 MB cache
            conn.execute("PRAGMA temp_store=MEMORY")

            if SCHEMA_PATH.exists():
                with open(SCHEMA_PATH, "r") as f:
                    conn.executescript(f.read())
                logger.info("Database schema applied: %s", self.db_path)
            else:
                logger.warning("Schema file not found: %s", SCHEMA_PATH)

            self._run_migrations(conn)

            self._initialized = True
            logger.info("Database initialized: %s", self.db_path)
            return True

        except sqlite3.Error:
            logger.exception("Database initialization failed")
            return False

    def _run_migrations(self, conn: sqlite3.Connection):
        """
        Apply additive schema migrations to existing databases.

        Each ALTER TABLE is wrapped in a try/except so the migration is
        idempotent — running against a freshly created database (where the
        columns already exist from schema.sql) is a safe no-op.
        """
        new_columns = [
            ("detections", "vehicle_path",   "TEXT"),
            ("detections", "plate_path",     "TEXT"),
            ("detections", "composite_path", "TEXT"),
            ("detections", "make",           "TEXT"),
            ("detections", "model",          "TEXT"),
            ("detections", "year_range",     "TEXT"),
            ("detections", "confidence",     "REAL"),
            ("detections", "latitude",       "REAL"),
            ("detections", "longitude",      "REAL"),
            ("detections", "fingerprint",    "TEXT"),
        ]
        for table, column, col_type in new_columns:
            try:
                conn.execute(
                    f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"
                )
                logger.info("Migration: added column %s.%s", table, column)
            except sqlite3.OperationalError:
                pass  # column already exists — skip

    def _get_connection(self) -> sqlite3.Connection:
        """Get or create a thread-local connection."""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(
                str(self.db_path),
                check_same_thread=False,
            )
            self._local.conn.row_factory = sqlite3.Row
        return self._local.conn

    @property
    def connection(self) -> sqlite3.Connection:
        return self._get_connection()

    def execute(self, query: str, params: tuple = ()) -> sqlite3.Cursor:
        """Execute a query and return the cursor."""
        conn = self._get_connection()
        return conn.execute(query, params)

    def executemany(self, query: str, params_list: list[tuple]) -> sqlite3.Cursor:
        conn = self._get_connection()
        return conn.executemany(query, params_list)

    def commit(self):
        conn = self._get_connection()
        conn.commit()

    def vacuum(self):
        """Run VACUUM to reclaim space."""
        logger.info("Running VACUUM on database")
        conn = self._get_connection()
        conn.execute("VACUUM")

    def close(self):
        """Close the thread-local connection."""
        if hasattr(self._local, "conn") and self._local.conn is not None:
            self._local.conn.close()
            self._local.conn = None

    @property
    def is_initialized(self) -> bool:
        return self._initialized
