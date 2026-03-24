# Copyright (C) 2024 RompMusic Contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Library endpoint tests. List endpoints return 200 (optional auth)."""

import pytest
from httpx import ASGITransport, AsyncClient

from rompmusic_server.config import settings
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


async def test_library_stats_forbidden_without_token_when_token_configured(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
):
    """GET /library/stats returns 403 when a metrics token is required and header is missing."""
    monkeypatch.setattr(settings, "metrics_library_stats_token", "secret-metrics-token")
    r = await client.get("/api/v1/library/stats")
    assert r.status_code == 403


async def test_library_stats_ok_with_matching_token(client: AsyncClient, monkeypatch: pytest.MonkeyPatch):
    """GET /library/stats returns albums and tracks when X-Rompmusic-Metrics-Token matches."""
    monkeypatch.setattr(settings, "metrics_library_stats_token", "secret-metrics-token")
    r = await client.get(
        "/api/v1/library/stats",
        headers={"X-Rompmusic-Metrics-Token": "secret-metrics-token"},
    )
    assert r.status_code == 200
    data = r.json()
    assert "albums" in data and "tracks" in data
    assert isinstance(data["albums"], int) and isinstance(data["tracks"], int)
