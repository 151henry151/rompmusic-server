# Copyright (C) 2024 RompMusic Contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Database connection and session management."""

from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from rompmusic_server.config import settings
from rompmusic_server.models.base import Base

engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for FastAPI that yields a database session."""
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Create all tables. Call at startup."""
    from sqlalchemy import text

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Migration: add has_artwork to albums if missing (for home quality filtering)
        try:
            await conn.execute(text("""
                ALTER TABLE albums ADD COLUMN IF NOT EXISTS has_artwork BOOLEAN DEFAULT NULL
            """))
        except Exception:
            pass
        # Migration: add artwork_hash for grouping identical album art in library
        try:
            await conn.execute(text("""
                ALTER TABLE albums ADD COLUMN IF NOT EXISTS artwork_hash VARCHAR(64)
            """))
        except Exception:
            pass
        # Migration: play_history support anonymous (public server)
        try:
            await conn.execute(text("""
                ALTER TABLE play_history ADD COLUMN IF NOT EXISTS anonymous_id VARCHAR(64)
            """))
            await conn.execute(text("""
                ALTER TABLE play_history ALTER COLUMN user_id DROP NOT NULL
            """))
        except Exception:
            pass
        try:
            await conn.execute(text("""
                ALTER TABLE play_history DROP CONSTRAINT IF EXISTS play_history_user_or_anonymous
            """))
            await conn.execute(text("""
                ALTER TABLE play_history ADD CONSTRAINT play_history_user_or_anonymous
                CHECK ((user_id IS NOT NULL) OR (anonymous_id IS NOT NULL))
            """))
        except Exception:
            pass