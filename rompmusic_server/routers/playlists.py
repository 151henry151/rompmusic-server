# Copyright (C) 2024 RompMusic Contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Playlist API routes."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from rompmusic_server.auth import get_current_user_id
from rompmusic_server.database import get_db
from rompmusic_server.models import Album, Artist, Playlist, PlaylistTrack, Track
from rompmusic_server.api.schemas import (
    PlaylistCreate,
    PlaylistTrackAdd,
    PlaylistUpdate,
    PlaylistResponse,
    TrackResponse,
)

router = APIRouter(prefix="/playlists", tags=["playlists"])


@router.get("", response_model=list[PlaylistResponse])
async def list_playlists(
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> list[PlaylistResponse]:
    """List current user's playlists."""
    result = await db.execute(
        select(Playlist).where(Playlist.user_id == user_id).order_by(Playlist.name)
    )
    playlists = result.scalars().all()
    out = []
    from sqlalchemy import func
    for p in playlists:
        cnt_result = await db.scalar(
            select(func.count()).select_from(PlaylistTrack).where(PlaylistTrack.playlist_id == p.id)
        )
        cnt = cnt_result or 0
        out.append(
            PlaylistResponse(
                id=p.id,
                name=p.name,
                description=p.description,
                is_public=p.is_public,
                created_at=p.created_at,
                track_count=cnt,
            )
        )
    return out


@router.post("", response_model=PlaylistResponse)
async def create_playlist(
    data: PlaylistCreate,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> PlaylistResponse:
    """Create a new playlist."""
    playlist = Playlist(
        user_id=user_id,
        name=data.name,
        description=data.description,
        is_public=data.is_public,
    )
    db.add(playlist)
    await db.commit()
    await db.refresh(playlist)
    return PlaylistResponse(
        id=playlist.id,
        name=playlist.name,
        description=playlist.description,
        is_public=playlist.is_public,
        created_at=playlist.created_at,
        track_count=0,
    )


@router.get("/{playlist_id}", response_model=PlaylistResponse)
async def get_playlist(
    playlist_id: int,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> PlaylistResponse:
    """Get playlist by ID."""
    result = await db.execute(
        select(Playlist).where(
            Playlist.id == playlist_id,
            Playlist.user_id == user_id,
        )
    )
    playlist = result.scalar_one_or_none()
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")
    return PlaylistResponse(
        id=playlist.id,
        name=playlist.name,
        description=playlist.description,
        is_public=playlist.is_public,
        created_at=playlist.created_at,
        track_count=len(playlist.tracks),
    )


@router.get("/{playlist_id}/tracks", response_model=list[TrackResponse])
async def get_playlist_tracks(
    playlist_id: int,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> list[TrackResponse]:
    """Get tracks in a playlist."""
    result = await db.execute(
        select(Playlist).where(
            Playlist.id == playlist_id,
            Playlist.user_id == user_id,
        )
    )
    playlist = result.scalar_one_or_none()
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")

    # Load playlist tracks with track, album, artist
    pt_result = await db.execute(
        select(PlaylistTrack, Track, Album.title, Artist.name)
        .join(Track, PlaylistTrack.track_id == Track.id)
        .join(Album, Track.album_id == Album.id)
        .join(Artist, Track.artist_id == Artist.id)
        .where(PlaylistTrack.playlist_id == playlist_id)
        .order_by(PlaylistTrack.position)
    )
    rows = pt_result.all()
    return [
        TrackResponse(
            id=t.id,
            title=t.title,
            album_id=t.album_id,
            artist_id=t.artist_id,
            album_title=at,
            artist_name=an,
            track_number=t.track_number,
            disc_number=t.disc_number,
            duration=t.duration,
            bitrate=t.bitrate,
            format=t.format,
        )
        for _, t, at, an in rows
    ]


@router.post("/{playlist_id}/tracks")
async def add_track_to_playlist(
    playlist_id: int,
    data: PlaylistTrackAdd,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Add a track to a playlist."""
    result = await db.execute(
        select(Playlist).where(
            Playlist.id == playlist_id,
            Playlist.user_id == user_id,
        )
    )
    playlist = result.scalar_one_or_none()
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")

    track_result = await db.execute(select(Track).where(Track.id == data.track_id))
    if not track_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Track not found")

    max_pos = max((pt.position for pt in playlist.tracks), default=0)
    position = data.position if data.position is not None else max_pos + 1

    pt = PlaylistTrack(
        playlist_id=playlist_id,
        track_id=data.track_id,
        position=position,
    )
    db.add(pt)
    await db.commit()
    return {"status": "ok"}


@router.delete("/{playlist_id}/tracks/{track_id}")
async def remove_track_from_playlist(
    playlist_id: int,
    track_id: int,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Remove a track from a playlist."""
    result = await db.execute(
        select(Playlist).where(
            Playlist.id == playlist_id,
            Playlist.user_id == user_id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Playlist not found")

    from sqlalchemy import delete
    await db.execute(
        delete(PlaylistTrack).where(
            PlaylistTrack.playlist_id == playlist_id,
            PlaylistTrack.track_id == track_id,
        )
    )
    await db.commit()
    return {"status": "ok"}
