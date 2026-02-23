import logging
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
    pool_recycle=1800,  # Recycle connections after 30 min to avoid stale connections
    pool_timeout=10,    # Fail fast if pool is exhausted (prevents thread starvation)
)

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Provide a transactional database session.

    Routers MUST call `await db.commit()` explicitly when writes succeed.
    The session auto-rollbacks on unhandled exceptions and closes on exit.
    This avoids the double-commit issue where both the router and this
    dependency attempt to commit the same transaction.
    """
    async with async_session() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Run metadata create_all as a safety net for development.

    In production, schema changes should be managed exclusively via Alembic
    migrations. create_all is a no-op for tables that already exist but ensures
    new models added during development are created without needing a migration.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
