# Copyright (C) 2024 RompMusic Contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Streaming endpoint tests. Track not found returns 404."""

import pytest
from httpx import ASGITransport, AsyncClient

from rompmusic_server.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def test_stream_track_not_found(client: AsyncClient):
    """Requesting a non-existent track id returns 404."""
    r = await client.get("/api/v1/stream/999999999")
    assert r.status_code == 404
    assert "detail" in r.json()
