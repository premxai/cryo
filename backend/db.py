"""Async PostgreSQL connection pool via SQLAlchemy 2.0 + asyncpg."""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from backend.config import settings

engine = create_async_engine(
    settings.database_url,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,  # validates connections before use — catches stale connections
    pool_recycle=3600,  # recycle connections every hour
    echo=False,  # never True in production (leaks query internals to logs)
)

AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""

    pass


async def get_db() -> AsyncSession:
    """FastAPI dependency that yields a database session."""
    async with AsyncSessionLocal() as session:
        yield session


async def init_db_pool() -> None:
    """Called at app startup to verify the DB is reachable.

    In development, a missing DB is non-fatal — the app still boots and search works.
    In production, a missing DB at startup is a hard error.
    """
    import structlog
    from sqlalchemy import text

    log = structlog.get_logger()
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        log.info("cryo.db.connected", url=settings.database_url.split("@")[-1])
    except Exception as exc:
        if settings.is_production:
            raise
        log.warning(
            "cryo.db.unavailable",
            error=str(exc),
            hint="Start PostgreSQL: docker-compose up -d postgres",
        )


async def close_db_pool() -> None:
    """Called at app shutdown to cleanly close the pool."""
    await engine.dispose()
