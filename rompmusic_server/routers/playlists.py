# Copyright (C) 2024 RompMusic Contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Playlist API routes."""

from collections import Counter, defaultdict
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from rompmusic_server.api.schemas import (
    AddTrackRequest,
    PlaylistCreate,
    PlaylistOut,
    PlaylistSummary,
    PlaylistTrackOut,
    PlaylistUpdate,
    ReorderRequest,
)
from rompmusic_server.auth import get_current_user_id
from rompmusic_server.database import get_db
from rompmusic_server.models import Album, Artist, Playlist, PlaylistTrack, Track

router = APIRouter(prefix="/playlists", tags=["playlists"])


async def _get_playlist_or_error(db: AsyncSession, playlist_id: int, user_id: int) -> Playlist:
    playlist = await db.scalar(select(Playlist).where(Playlist.id == playlist_id))
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")
    if playlist.user_id != user_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    return playlist


async def _list_playlist_tracks(db: AsyncSession, playlist_id: int) -> list[PlaylistTrackOut]:
    rows = (
        await db.execute(
            select(
                PlaylistTrack.position,
                Track.id,
                Track.title,
                Track.album_id,
                Track.artist_id,
                Artist.name,
                Album.title,
                Track.duration,
            )
            .join(Track, PlaylistTrack.track_id == Track.id)
            .join(Artist, Track.artist_id == Artist.id)
            .join(Album, Track.album_id == Album.id)
            .where(PlaylistTrack.playlist_id == playlist_id)
            .order_by(PlaylistTrack.position.asc(), PlaylistTrack.id.asc())
        )
    ).all()
    return [
        PlaylistTrackOut(
            id=track_id,
            title=track_title,
            album_id=album_id,
            artist_id=artist_id,
            artist=artist_name,
            album=album_title,
            duration=duration,
            position=position,
        )
        for (
            position,
            track_id,
            track_title,
            album_id,
            artist_id,
            artist_name,
            album_title,
            duration,
        ) in rows
    ]


async def _build_playlist_out(db: AsyncSession, playlist: Playlist) -> PlaylistOut:
    tracks = await _list_playlist_tracks(db, playlist.id)
    return PlaylistOut(
        id=playlist.id,
        name=playlist.name,
        description=playlist.description,
        owner_id=playlist.user_id,
        created_at=playlist.created_at,
        updated_at=playlist.updated_at,
        track_count=len(tracks),
        tracks=tracks,
    )


async def _normalize_positions(db: AsyncSession, playlist_id: int) -> None:
    rows = (
        await db.execute(
            select(PlaylistTrack)
            .where(PlaylistTrack.playlist_id == playlist_id)
            .order_by(PlaylistTrack.position.asc(), PlaylistTrack.id.asc())
        )
    ).scalars().all()
    for index, row in enumerate(rows):
        row.position = index


def _normalize_description(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


@router.get("", response_model=list[PlaylistSummary])
async def list_playlists(
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> list[PlaylistSummary]:
    playlists = (
        await db.execute(
            select(Playlist)
            .where(Playlist.user_id == user_id)
            .order_by(Playlist.updated_at.desc(), Playlist.id.desc())
        )
    ).scalars().all()
    if not playlists:
        return []
    playlist_ids = [playlist.id for playlist in playlists]
    counts = (
        await db.execute(
            select(PlaylistTrack.playlist_id, func.count(PlaylistTrack.id))
            .where(PlaylistTrack.playlist_id.in_(playlist_ids))
            .group_by(PlaylistTrack.playlist_id)
        )
    ).all()
    count_by_playlist = {playlist_id: int(count) for playlist_id, count in counts}
    return [
        PlaylistSummary(
            id=playlist.id,
            name=playlist.name,
            description=playlist.description,
            owner_id=playlist.user_id,
            created_at=playlist.created_at,
            updated_at=playlist.updated_at,
            track_count=count_by_playlist.get(playlist.id, 0),
        )
        for playlist in playlists
    ]


@router.post("", response_model=PlaylistOut)
async def create_playlist(
    data: PlaylistCreate,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> PlaylistOut:
    name = data.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Playlist name is required")
    playlist = Playlist(
        user_id=user_id,
        name=name,
        description=_normalize_description(data.description),
        is_public=False,
    )
    db.add(playlist)
    await db.flush()
    await db.refresh(playlist)
    return await _build_playlist_out(db, playlist)


@router.get("/{playlist_id}", response_model=PlaylistOut)
async def get_playlist(
    playlist_id: int,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> PlaylistOut:
    playlist = await _get_playlist_or_error(db, playlist_id, user_id)
    return await _build_playlist_out(db, playlist)


@router.put("/{playlist_id}", response_model=PlaylistOut)
async def update_playlist(
    playlist_id: int,
    data: PlaylistUpdate,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> PlaylistOut:
    playlist = await _get_playlist_or_error(db, playlist_id, user_id)
    if data.name is not None:
        name = data.name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="Playlist name is required")
        playlist.name = name
    if data.description is not None:
        playlist.description = _normalize_description(data.description)
    playlist.updated_at = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(playlist)
    return await _build_playlist_out(db, playlist)


@router.delete("/{playlist_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_playlist(
    playlist_id: int,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> Response:
    playlist = await _get_playlist_or_error(db, playlist_id, user_id)
    await db.delete(playlist)
    await db.flush()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{playlist_id}/tracks", response_model=PlaylistOut)
async def add_track_to_playlist(
    playlist_id: int,
    data: AddTrackRequest,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> PlaylistOut:
    playlist = await _get_playlist_or_error(db, playlist_id, user_id)
    track_exists = await db.scalar(select(Track.id).where(Track.id == data.track_id))
    if not track_exists:
        raise HTTPException(status_code=404, detail="Track not found")

    current_tracks = (
        await db.execute(
            select(PlaylistTrack.id)
            .where(PlaylistTrack.playlist_id == playlist_id)
            .order_by(PlaylistTrack.position.asc(), PlaylistTrack.id.asc())
        )
    ).scalars().all()
    target_position = len(current_tracks) if data.position is None else data.position
    if target_position < 0 or target_position > len(current_tracks):
        raise HTTPException(status_code=400, detail="Invalid position")

    await db.execute(
        update(PlaylistTrack)
        .where(
            PlaylistTrack.playlist_id == playlist_id,
            PlaylistTrack.position >= target_position,
        )
        .values(position=PlaylistTrack.position + 1)
    )
    db.add(
        PlaylistTrack(
            playlist_id=playlist_id,
            track_id=data.track_id,
            position=target_position,
        )
    )
    await db.flush()
    await _normalize_positions(db, playlist_id)
    playlist.updated_at = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(playlist)
    return await _build_playlist_out(db, playlist)


@router.delete("/{playlist_id}/tracks/{track_id}", response_model=PlaylistOut)
async def remove_track_from_playlist(
    playlist_id: int,
    track_id: int,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> PlaylistOut:
    playlist = await _get_playlist_or_error(db, playlist_id, user_id)
    playlist_track = await db.scalar(
        select(PlaylistTrack)
        .where(
            PlaylistTrack.playlist_id == playlist_id,
            PlaylistTrack.track_id == track_id,
        )
        .order_by(PlaylistTrack.position.asc(), PlaylistTrack.id.asc())
    )
    if not playlist_track:
        raise HTTPException(status_code=404, detail="Track not found in playlist")
    await db.delete(playlist_track)
    await db.flush()
    await _normalize_positions(db, playlist_id)
    playlist.updated_at = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(playlist)
    return await _build_playlist_out(db, playlist)


@router.put("/{playlist_id}/tracks/reorder", response_model=PlaylistOut)
async def reorder_playlist_tracks(
    playlist_id: int,
    data: ReorderRequest,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> PlaylistOut:
    playlist = await _get_playlist_or_error(db, playlist_id, user_id)
    current_playlist_tracks = (
        await db.execute(
            select(PlaylistTrack)
            .where(PlaylistTrack.playlist_id == playlist_id)
            .order_by(PlaylistTrack.position.asc(), PlaylistTrack.id.asc())
        )
    ).scalars().all()
    current_track_ids = [playlist_track.track_id for playlist_track in current_playlist_tracks]
    if len(data.track_ids) != len(current_track_ids):
        raise HTTPException(status_code=400, detail="Provided track IDs must match playlist contents")
    if Counter(data.track_ids) != Counter(current_track_ids):
        raise HTTPException(status_code=400, detail="Provided track IDs must match playlist contents")

    # Move every row out of the 0..N-1 range first to avoid unique-position collisions.
    offset = len(current_playlist_tracks)
    for index, playlist_track in enumerate(current_playlist_tracks):
        playlist_track.position = offset + index
    await db.flush()

    track_id_to_rows: dict[int, list[PlaylistTrack]] = defaultdict(list)
    for playlist_track in current_playlist_tracks:
        track_id_to_rows[playlist_track.track_id].append(playlist_track)

    for new_position, track_id in enumerate(data.track_ids):
        playlist_track = track_id_to_rows[track_id].pop(0)
        playlist_track.position = new_position

    playlist.updated_at = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(playlist)
    return await _build_playlist_out(db, playlist)
