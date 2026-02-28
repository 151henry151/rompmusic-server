# Copyright (C) 2024 RompMusic Contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Play-history endpoint tests."""

from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient

from rompmusic_server.auth import get_user_id_or_anonymous
from rompmusic_server.database import get_db
from rompmusic_server.main import app


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class _FakeSession:
    def __init__(self, rows):
        self._rows = rows
        self.queries = []

    async def execute(self, query):
        self.queries.append(query)
        return _FakeResult(self._rows)


@pytest.fixture
async def history_client():
    rows = [
        (
            SimpleNamespace(
                id=1,
                title="No Artwork Track",
                album_id=10,
                artist_id=20,
                track_number=1,
                disc_number=1,
                duration=123.0,
                bitrate=None,
                format="mp3",
            ),
            "Album A",
            "Artist A",
        ),
        (
            SimpleNamespace(
                id=2,
                title="Second Track",
                album_id=11,
                artist_id=21,
                track_number=2,
                disc_number=1,
                duration=222.0,
                bitrate=320,
                format="flac",
            ),
            "Album B",
            "Artist B",
        ),
    ]
    fake_db = _FakeSession(rows)

    async def _override_db():
        yield fake_db

    async def _override_user_or_anon():
        return (123, None)

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_user_id_or_anonymous] = _override_user_or_anon

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, fake_db

    app.dependency_overrides.clear()


async def test_recently_played_accepts_large_limit(history_client):
    """Regression: History screen requests limit=100 and must not 422."""
    client, _ = history_client
    response = await client.get("/api/v1/library/tracks/recently-played?limit=100")
    assert response.status_code == 200
    assert len(response.json()) == 2


async def test_recently_played_without_limit_uses_full_history_query(history_client):
    """Omitting limit should build an unbounded query (no truncation in API layer)."""
    client, fake_db = history_client
    response = await client.get("/api/v1/library/tracks/recently-played")
    assert response.status_code == 200
    data = response.json()
    assert [row["id"] for row in data] == [1, 2]
    assert fake_db.queries[-1]._limit_clause is None
