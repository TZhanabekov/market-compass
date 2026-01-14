"""PostgreSQL store with async SQLAlchemy.

Handles:
- Database session management
- Repository pattern for data access
- Connection pooling
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.settings import get_settings


class Base(DeclarativeBase):
    """Base class for SQLAlchemy models."""

    pass


# Engine and session factory (initialized on startup)
_engine = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


async def init_db() -> None:
    """Initialize database connection pool."""
    global _engine, _session_factory

    settings = get_settings()
    _engine = create_async_engine(
        settings.async_database_url,
        echo=settings.debug,
        connect_args=settings.asyncpg_connect_args,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
    )
    _session_factory = async_sessionmaker(
        _engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


async def close_db() -> None:
    """Close database connection pool."""
    global _engine, _session_factory
    if _engine:
        await _engine.dispose()
        _engine = None
        _session_factory = None


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Get database session context manager.

    Usage:
        async with get_session() as session:
            result = await session.execute(query)
    """
    if _session_factory is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")

    async with _session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def create_tables() -> None:
    """Create all tables (for development/testing only)."""
    if _engine is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")

    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def drop_tables() -> None:
    """Drop all tables (for testing only)."""
    if _engine is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")

    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
