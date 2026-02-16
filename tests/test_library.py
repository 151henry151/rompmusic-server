# Copyright (C) 2024 RompMusic Contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Library endpoint tests. List endpoints return 200 (optional auth)."""

import pytest
from httpx import ASGITransport, AsyncClient

from rompmusic_server.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def test_list_artists(client: AsyncClient):
    """GET /library/artists returns 200 and a list (may be empty)."""
    r = await client.get("/api/v1/library/artists?limit=5")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    # If there are artists, check shape
    if data:
        assert "id" in data[0]
        assert "name" in data[0]
