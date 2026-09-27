"""
TruthLens – Database Engine, Session Factory, and Initialization.
Configured for PostgreSQL (via asyncpg) with graceful local fallback for development.
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


def _resolve_db_url(url: str) -> str:
    """Normalize database URL for asyncpg / aiosqlite."""
    if url.startswith("postgres://"):
        return "postgresql+asyncpg://" + url[len("postgres://"):]
    elif url.startswith("postgresql://") and "+asyncpg" not in url:
        return "postgresql+asyncpg://" + url[len("postgresql://"):]
    return url


# Resolve configured URL (PostgreSQL by default from settings.database_url)
_target_url = _resolve_db_url(settings.database_url)

_active_engine: AsyncEngine = create_async_engine(
    _target_url,
    echo=False,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

_active_session_maker = async_sessionmaker(
    bind=_active_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

engine = _active_engine


@asynccontextmanager
async def AsyncSessionLocal() -> AsyncGenerator[AsyncSession, None]:
    """Async context manager that yields a session from the active sessionmaker."""
    async with _active_session_maker() as session:
        yield session


async def init_db() -> None:
    """
    Initialize database schema (create tables if they don't exist).
    If PostgreSQL is unreachable, falls back to local SQLite to ensure
    seamless local development without crashing the app.
    """
    global _active_engine, _active_session_maker

    try:
        async with _active_engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Successfully connected to primary PostgreSQL database: %s", settings.database_url)
    except Exception as exc:
        logger.warning(
            "Primary database (%s) connection failed: %s. "
            "Falling back to local SQLite database (truthlens.db) for development.",
            settings.database_url,
            exc,
        )
        fallback_url = "sqlite+aiosqlite:///./truthlens.db"
        _active_engine = create_async_engine(fallback_url, echo=False)
        _active_session_maker = async_sessionmaker(
            bind=_active_engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        async with _active_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Initialized fallback local SQLite database: %s", fallback_url)


_initialized = False


async def ensure_db() -> None:
    """Ensure database has been initialized once."""
    global _initialized
    if not _initialized:
        await init_db()
        _initialized = True


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency – yields an async DB session."""
    await ensure_db()
    async with _active_session_maker() as session:
        yield session
