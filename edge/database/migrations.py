"""
SEEN IT FIRST - Edge AI Vehicle LPR System
Schema migration runner.

Versioned migration strategy:
  * Version 0 / empty  -> execute schema.sql to bootstrap all tables (-> v1)
  * Version 2, 3, ...  -> future incremental SQL migrations added here

Each migration is an async callable keyed by target version number.  The runner
walks from the current version to ``LATEST_VERSION``, applying each step in
order inside a transaction.
"""

from __future__ import annotations

import logging
from typing import Callable, Awaitable

from edge.database.connection import DatabaseConnection
from edge.database.models import _new_id, _now_iso

logger = logging.getLogger("sif.database.migrations")

# The highest schema version shipped with this release.
LATEST_VERSION: int = 1


# ------------------------------------------------------------------
# Individual migration steps
# ------------------------------------------------------------------

async def _migrate_to_v1(db: DatabaseConnection) -> None:
    """Bootstrap: execute the full schema.sql and set version = 1."""
    logger.info("Migration -> v1: applying initial schema from schema.sql")
    await db.init_schema()

    # Seed the version row
    await db.execute(
        "INSERT INTO schema_version (version) VALUES (?)",
        [1],
    )
    logger.info("Migration -> v1: complete")


# Register every migration step.  Key = *target* version.
_MIGRATIONS: dict[int, Callable[[DatabaseConnection], Awaitable[None]]] = {
    1: _migrate_to_v1,
    # Future migrations go here:
    # 2: _migrate_to_v2,
    # 3: _migrate_to_v3,
}


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------

async def _get_current_version(db: DatabaseConnection) -> int:
    """Return the current schema version, or ``0`` if the table does not exist
    or contains no rows."""
    try:
        row = await db.fetchone(
            "SELECT version FROM schema_version ORDER BY version DESC LIMIT 1"
        )
        if row is None:
            return 0
        return int(row["version"])
    except Exception:
        # Table might not exist at all on a brand-new database.
        logger.debug("schema_version table not found -- assuming version 0")
        return 0


async def run_migrations(db: DatabaseConnection) -> None:
    """Bring the database schema up to :data:`LATEST_VERSION`.

    Safe to call on every startup -- it is a no-op when the schema is already
    current.

    Parameters
    ----------
    db:
        An **already-connected** :class:`DatabaseConnection`.
    """
    current = await _get_current_version(db)
    logger.info(
        "Schema version check: current=%d latest=%d", current, LATEST_VERSION
    )

    if current >= LATEST_VERSION:
        logger.info("Database schema is up to date (v%d)", current)
        return

    for target in range(current + 1, LATEST_VERSION + 1):
        migration_fn = _MIGRATIONS.get(target)
        if migration_fn is None:
            logger.error(
                "No migration function registered for version %d -- aborting",
                target,
            )
            raise RuntimeError(
                f"Missing migration step for schema version {target}"
            )

        logger.info("Applying migration: v%d -> v%d", target - 1, target)
        try:
            await migration_fn(db)
        except Exception:
            logger.exception(
                "Migration to v%d FAILED -- database may be in an inconsistent state",
                target,
            )
            raise

    final = await _get_current_version(db)
    logger.info("All migrations applied. Schema is now at v%d", final)
