# Copyright (C) 2024 RompMusic Contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Playlist endpoint tests."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

from rompmusic_server.auth import create_access_token, hash_password
from rompmusic_server.database import async_session_maker, engine
from rompmusic_server.main import app
from rompmusic_server.models import Album, Artist, Playlist, PlaylistTrack, Track, User


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture(scope="session")
def event_loop():
    """Use one loop for all async tests so global async engine connections stay valid."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def playlist_seed_data() -> AsyncGenerator[dict[str, int], None]:
    await engine.dispose()
    suffix = uuid.uuid4().hex[:10]
    async with async_session_maker() as db:
        user1 = User(
            username=f"playlist_user1_{suffix}",
            email=f"playlist_user1_{suffix}@example.com",
            password_hash=hash_password("password123"),
            is_active=True,
        )
        user2 = User(
            username=f"playlist_user2_{suffix}",
            email=f"playlist_user2_{suffix}@example.com",
            password_hash=hash_password("password123"),
            is_active=True,
        )
        artist = Artist(name=f"Playlist Test Artist {suffix}")
        album = Album(title=f"Playlist Test Album {suffix}", artist=artist, year=2026)
        tracks = [
            Track(
                title=f"Playlist Track {suffix} #1",
                album=album,
                artist=artist,
                track_number=1,
                disc_number=1,
                duration=180.0,
                file_path=f"/tmp/playlist-{suffix}-1.mp3",
            ),
            Track(
                title=f"Playlist Track {suffix} #2",
                album=album,
                artist=artist,
                track_number=2,
                disc_number=1,
                duration=200.0,
                file_path=f"/tmp/playlist-{suffix}-2.mp3",
            ),
            Track(
                title=f"Playlist Track {suffix} #3",
                album=album,
                artist=artist,
                track_number=3,
                disc_number=1,
                duration=220.0,
                file_path=f"/tmp/playlist-{suffix}-3.mp3",
            ),
        ]
        db.add_all([user1, user2, artist, album, *tracks])
        await db.commit()
        await db.refresh(user1)
        await db.refresh(user2)
        for track in tracks:
            await db.refresh(track)

        data = {
            "user1_id": user1.id,
            "user2_id": user2.id,
            "track1_id": tracks[0].id,
            "track2_id": tracks[1].id,
            "track3_id": tracks[2].id,
            "album_id": album.id,
            "artist_id": artist.id,
        }

    try:
        yield data
    finally:
        await engine.dispose()
        async with async_session_maker() as db:
            playlist_ids = (
                await db.execute(
                    select(Playlist.id).where(
                        Playlist.user_id.in_([data["user1_id"], data["user2_id"]])
                    )
                )
            ).scalars().all()
            if playlist_ids:
                await db.execute(
                    delete(PlaylistTrack).where(
                        PlaylistTrack.playlist_id.in_(playlist_ids)
                    )
                )
            await db.execute(delete(Playlist).where(Playlist.user_id.in_([data["user1_id"], data["user2_id"]])))
            await db.execute(
                delete(Track).where(
                    Track.id.in_([data["track1_id"], data["track2_id"], data["track3_id"]])
                )
            )
            await db.execute(delete(Album).where(Album.id == data["album_id"]))
            await db.execute(delete(Artist).where(Artist.id == data["artist_id"]))
            await db.execute(delete(User).where(User.id.in_([data["user1_id"], data["user2_id"]])))
            await db.commit()
        await engine.dispose()


def _auth_header(user_id: int) -> dict[str, str]:
    token = create_access_token({"sub": str(user_id)})
    return {"Authorization": f"Bearer {token}"}


async def _create_playlist(client: AsyncClient, user_id: int, name: str, description: str | None = None) -> dict:
    response = await client.post(
        "/api/v1/playlists",
        headers=_auth_header(user_id),
        json={"name": name, "description": description},
    )
    assert response.status_code == 200
    return response.json()


async def _add_track(client: AsyncClient, user_id: int, playlist_id: int, track_id: int, position: int | None = None) -> dict:
    payload: dict[str, int] = {"track_id": track_id}
    if position is not None:
        payload["position"] = position
    response = await client.post(
        f"/api/v1/playlists/{playlist_id}/tracks",
        headers=_auth_header(user_id),
        json=payload,
    )
    assert response.status_code == 200
    return response.json()


async def test_create_playlist(client: AsyncClient, playlist_seed_data: dict[str, int]):
    response = await client.post(
        "/api/v1/playlists",
        headers=_auth_header(playlist_seed_data["user1_id"]),
        json={"name": "Road Trip", "description": "Long drive songs"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Road Trip"
    assert body["description"] == "Long drive songs"
    assert body["owner_id"] == playlist_seed_data["user1_id"]
    assert body["track_count"] == 0
    assert body["tracks"] == []


async def test_list_playlists_only_returns_current_user_playlists(
    client: AsyncClient, playlist_seed_data: dict[str, int]
):
    await _create_playlist(client, playlist_seed_data["user1_id"], "User One List")
    await _create_playlist(client, playlist_seed_data["user2_id"], "User Two List")

    response = await client.get(
        "/api/v1/playlists",
        headers=_auth_header(playlist_seed_data["user1_id"]),
    )

    assert response.status_code == 200
    rows = response.json()
    assert len(rows) == 1
    assert rows[0]["name"] == "User One List"
    assert rows[0]["owner_id"] == playlist_seed_data["user1_id"]


async def test_get_playlist(client: AsyncClient, playlist_seed_data: dict[str, int]):
    created = await _create_playlist(client, playlist_seed_data["user1_id"], "My Mix")

    response = await client.get(
        f"/api/v1/playlists/{created['id']}",
        headers=_auth_header(playlist_seed_data["user1_id"]),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == created["id"]
    assert body["name"] == "My Mix"
    assert body["tracks"] == []


async def test_update_playlist(client: AsyncClient, playlist_seed_data: dict[str, int]):
    created = await _create_playlist(client, playlist_seed_data["user1_id"], "Old Name", "Old Description")

    response = await client.put(
        f"/api/v1/playlists/{created['id']}",
        headers=_auth_header(playlist_seed_data["user1_id"]),
        json={"name": "New Name", "description": "New Description"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "New Name"
    assert body["description"] == "New Description"


async def test_add_tracks_with_append_and_position_insertion(
    client: AsyncClient, playlist_seed_data: dict[str, int]
):
    created = await _create_playlist(client, playlist_seed_data["user1_id"], "Workout")
    playlist_id = created["id"]

    after_append = await _add_track(
        client,
        playlist_seed_data["user1_id"],
        playlist_id,
        playlist_seed_data["track2_id"],
    )
    assert [t["id"] for t in after_append["tracks"]] == [playlist_seed_data["track2_id"]]

    after_insert_front = await _add_track(
        client,
        playlist_seed_data["user1_id"],
        playlist_id,
        playlist_seed_data["track1_id"],
        position=0,
    )
    assert [t["id"] for t in after_insert_front["tracks"]] == [
        playlist_seed_data["track1_id"],
        playlist_seed_data["track2_id"],
    ]
    assert [t["position"] for t in after_insert_front["tracks"]] == [0, 1]

    after_insert_middle = await _add_track(
        client,
        playlist_seed_data["user1_id"],
        playlist_id,
        playlist_seed_data["track3_id"],
        position=1,
    )
    assert [t["id"] for t in after_insert_middle["tracks"]] == [
        playlist_seed_data["track1_id"],
        playlist_seed_data["track3_id"],
        playlist_seed_data["track2_id"],
    ]
    assert [t["position"] for t in after_insert_middle["tracks"]] == [0, 1, 2]
    assert after_insert_middle["track_count"] == 3


async def test_remove_track_renormalizes_positions(
    client: AsyncClient, playlist_seed_data: dict[str, int]
):
    created = await _create_playlist(client, playlist_seed_data["user1_id"], "Renorm")
    playlist_id = created["id"]
    await _add_track(client, playlist_seed_data["user1_id"], playlist_id, playlist_seed_data["track1_id"])
    await _add_track(client, playlist_seed_data["user1_id"], playlist_id, playlist_seed_data["track2_id"])
    await _add_track(client, playlist_seed_data["user1_id"], playlist_id, playlist_seed_data["track3_id"])

    response = await client.delete(
        f"/api/v1/playlists/{playlist_id}/tracks/{playlist_seed_data['track2_id']}",
        headers=_auth_header(playlist_seed_data["user1_id"]),
    )

    assert response.status_code == 200
    body = response.json()
    assert [t["id"] for t in body["tracks"]] == [
        playlist_seed_data["track1_id"],
        playlist_seed_data["track3_id"],
    ]
    assert [t["position"] for t in body["tracks"]] == [0, 1]


async def test_reorder_tracks(client: AsyncClient, playlist_seed_data: dict[str, int]):
    created = await _create_playlist(client, playlist_seed_data["user1_id"], "Reorder")
    playlist_id = created["id"]
    await _add_track(client, playlist_seed_data["user1_id"], playlist_id, playlist_seed_data["track1_id"])
    await _add_track(client, playlist_seed_data["user1_id"], playlist_id, playlist_seed_data["track2_id"])
    await _add_track(client, playlist_seed_data["user1_id"], playlist_id, playlist_seed_data["track3_id"])

    response = await client.put(
        f"/api/v1/playlists/{playlist_id}/tracks/reorder",
        headers=_auth_header(playlist_seed_data["user1_id"]),
        json={"track_ids": [playlist_seed_data["track3_id"], playlist_seed_data["track1_id"], playlist_seed_data["track2_id"]]},
    )

    assert response.status_code == 200
    body = response.json()
    assert [t["id"] for t in body["tracks"]] == [
        playlist_seed_data["track3_id"],
        playlist_seed_data["track1_id"],
        playlist_seed_data["track2_id"],
    ]
    assert [t["position"] for t in body["tracks"]] == [0, 1, 2]


async def test_playlist_access_forbidden_for_other_user(
    client: AsyncClient, playlist_seed_data: dict[str, int]
):
    created = await _create_playlist(client, playlist_seed_data["user1_id"], "Private")

    response = await client.get(
        f"/api/v1/playlists/{created['id']}",
        headers=_auth_header(playlist_seed_data["user2_id"]),
    )

    assert response.status_code == 403


async def test_playlist_not_found_returns_404(
    client: AsyncClient, playlist_seed_data: dict[str, int]
):
    response = await client.get(
        "/api/v1/playlists/987654321",
        headers=_auth_header(playlist_seed_data["user1_id"]),
    )
    assert response.status_code == 404
