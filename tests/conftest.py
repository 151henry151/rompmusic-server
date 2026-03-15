# Copyright (C) 2024 RompMusic Contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Pytest fixtures. Tests require DATABASE_URL (e.g. postgresql+asyncpg) to be set."""

import pytest

from rompmusic_server.database import engine


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
async def reset_async_db_pool():
    """Dispose asyncpg pool between tests to avoid cross-event-loop connections."""
    await engine.dispose()
    yield
    await engine.dispose()
