"""Alembic migration environment.

Fixes:
- Uses the sync database URL from app config (the previous version relied on
  alembic.ini sqlalchemy.url which was often missing or stale).
- Adds include_object hook to prevent destructive migrations from accidentally
  dropping tables or columns not managed by the models.
- Properly imports all models so autogenerate can diff correctly.
"""
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.config import get_settings
from app.database import Base
from app.models import *  # noqa: F401,F403 — import all models for metadata

config = context.config
settings = get_settings()

# Override sqlalchemy.url from app config so we don't depend on alembic.ini
config.set_main_option("sqlalchemy.url", settings.sync_database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def include_object(object, name, type_, reflected, compare_to):
    """Safety guard: prevent autogenerate from emitting DROP TABLE/DROP COLUMN.

    If a table or column exists in the DB but not in the models, Alembic's
    autogenerate would produce a destructive migration.  This hook blocks that.
    Developers must write explicit drop migrations when intentionally removing
    schema objects.
    """
    if type_ == "table" and reflected and compare_to is None:
        # Table exists in DB but not in models — skip (don't drop)
        return False
    if type_ == "column" and reflected and compare_to is None:
        # Column exists in DB but not in models — skip (don't drop)
        return False
    return True


def run_migrations_offline():
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_object=include_object,
            compare_type=True,  # Detect column type changes
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
