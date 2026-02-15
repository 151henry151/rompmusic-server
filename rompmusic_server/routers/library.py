# Copyright (C) 2024 RompMusic Contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Library API routes - artists, albums, tracks."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from rompmusic_server.auth import get_current_user_id, get_optional_user_id
from rompmusic_server.database import get_db
from rompmusic_server.models import Album, Artist, PlayHistory, Track
from rompmusic_server.api.schemas import AlbumResponse, ArtistResponse, TrackResponse

router = APIRouter(prefix="/library", tags=["library"])


@router.get("/artists", response_model=list[ArtistResponse])
async def list_artists(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    search: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> list[ArtistResponse]:
    """List artists with optional search."""
    q = select(Artist)
    if search:
        q = q.where(Artist.name.ilike(f"%{search}%"))
    q = q.order_by(Artist.name).offset(skip).limit(limit)
    result = await db.execute(q)
    artists = result.scalars().all()
    return [ArtistResponse.model_validate(a) for a in artists]


@router.get("/artists/{artist_id}", response_model=ArtistResponse)
async def get_artist(
    artist_id: int,
    db: AsyncSession = Depends(get_db),
) -> ArtistResponse:
    """Get artist by ID."""
    result = await db.execute(select(Artist).where(Artist.id == artist_id))
    artist = result.scalar_one_or_none()
    if not artist:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Artist not found")
    return ArtistResponse.model_validate(artist)


@router.get("/albums", response_model=list[AlbumResponse])
async def list_albums(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    artist_id: int | None = Query(None),
    search: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> list[AlbumResponse]:
    """List albums with optional filters."""
    q = select(Album, Artist.name).join(Artist, Album.artist_id == Artist.id)
    if artist_id:
        q = q.where(Album.artist_id == artist_id)
    if search:
        q = q.where(Album.title.ilike(f"%{search}%"))
    q = q.order_by(Album.year.desc().nullslast(), Album.title).offset(skip).limit(limit)
    result = await db.execute(q)
    rows = result.all()
    from sqlalchemy import func
    out = []
    for a, an in rows:
        tc = await db.scalar(select(func.count()).select_from(Track).where(Track.album_id == a.id))
        out.append(
            AlbumResponse(
                id=a.id,
                title=a.title,
                artist_id=a.artist_id,
                artist_name=an,
                year=a.year,
                artwork_path=a.artwork_path,
                track_count=tc or 0,
            )
        )
    return out


@router.get("/albums/{album_id}", response_model=AlbumResponse)
async def get_album(
    album_id: int,
    db: AsyncSession = Depends(get_db),
) -> AlbumResponse:
    """Get album by ID with artist name."""
    result = await db.execute(
        select(Album, Artist.name).join(Artist, Album.artist_id == Artist.id).where(Album.id == album_id)
    )
    row = result.one_or_none()
    if not row:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Album not found")
    album, artist_name = row
    track_count = await db.scalar(
        select(func.count()).select_from(Track).where(Track.album_id == album_id)
    ) or 0
    return AlbumResponse(
        id=album.id,
        title=album.title,
        artist_id=album.artist_id,
        artist_name=artist_name,
        year=album.year,
        artwork_path=album.artwork_path,
        track_count=track_count,
    )


@router.get("/tracks", response_model=list[TrackResponse])
async def list_tracks(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    album_id: int | None = Query(None),
    artist_id: int | None = Query(None),
    search: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> list[TrackResponse]:
    """List tracks with optional filters."""
    q = (
        select(Track, Album.title, Artist.name)
        .join(Album, Track.album_id == Album.id)
        .join(Artist, Track.artist_id == Artist.id)
    )
    if album_id:
        q = q.where(Track.album_id == album_id)
    if artist_id:
        q = q.where(Track.artist_id == artist_id)
    if search:
        q = q.where(Track.title.ilike(f"%{search}%"))
    q = q.order_by(Track.album_id, Track.disc_number, Track.track_number).offset(skip).limit(limit)
    result = await db.execute(q)
    rows = result.all()
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
        for t, at, an in rows
    ]


@router.get("/tracks/recently-added", response_model=list[TrackResponse])
async def list_recently_added_tracks(
    limit: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
) -> list[TrackResponse]:
    """List most recently added tracks (by created_at)."""
    q = (
        select(Track, Album.title, Artist.name)
        .join(Album, Track.album_id == Album.id)
        .join(Artist, Track.artist_id == Artist.id)
        .order_by(Track.created_at.desc())
        .limit(limit)
    )
    result = await db.execute(q)
    rows = result.all()
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
        for t, at, an in rows
    ]


@router.get("/tracks/recently-played", response_model=list[TrackResponse])
async def list_recently_played_tracks(
    limit: int = Query(20, ge=1, le=50),
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> list[TrackResponse]:
    """List user's recently played tracks."""
    subq = (
        select(PlayHistory.track_id, func.max(PlayHistory.played_at).label("last_played"))
        .where(PlayHistory.user_id == user_id)
        .group_by(PlayHistory.track_id)
    ).subquery()
    q = (
        select(Track, Album.title, Artist.name)
        .join(Album, Track.album_id == Album.id)
        .join(Artist, Track.artist_id == Artist.id)
        .join(subq, Track.id == subq.c.track_id)
        .order_by(desc(subq.c.last_played))
        .limit(limit)
    )
    result = await db.execute(q)
    rows = result.all()
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
        for t, at, an in rows
    ]


@router.get("/tracks/frequently-played", response_model=list[TrackResponse])
async def list_frequently_played_tracks(
    limit: int = Query(20, ge=1, le=50),
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> list[TrackResponse]:
    """List user's most frequently played tracks."""
    subq = (
        select(PlayHistory.track_id, func.count(PlayHistory.id).label("play_count"))
        .where(PlayHistory.user_id == user_id)
        .group_by(PlayHistory.track_id)
    ).subquery()
    q = (
        select(Track, Album.title, Artist.name)
        .join(Album, Track.album_id == Album.id)
        .join(Artist, Track.artist_id == Artist.id)
        .join(subq, Track.id == subq.c.track_id)
        .order_by(desc(subq.c.play_count))
        .limit(limit)
    )
    result = await db.execute(q)
    rows = result.all()
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
        for t, at, an in rows
    ]


@router.get("/tracks/most-played", response_model=list[TrackResponse])
async def list_most_played_tracks(
    limit: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
) -> list[TrackResponse]:
    """List most played tracks server-wide."""
    subq = (
        select(PlayHistory.track_id, func.count(PlayHistory.id).label("play_count"))
        .group_by(PlayHistory.track_id)
    ).subquery()
    q = (
        select(Track, Album.title, Artist.name)
        .join(Album, Track.album_id == Album.id)
        .join(Artist, Track.artist_id == Artist.id)
        .join(subq, Track.id == subq.c.track_id)
        .order_by(desc(subq.c.play_count))
        .limit(limit)
    )
    result = await db.execute(q)
    rows = result.all()
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
        for t, at, an in rows
    ]


@router.get("/tracks/similar", response_model=list[TrackResponse])
async def list_similar_tracks(
    track_id: int = Query(..., ge=1),
    limit: int = Query(20, ge=1, le=50),
    user_id: int | None = Depends(get_optional_user_id),
    db: AsyncSession = Depends(get_db),
) -> list[TrackResponse]:
    """Get tracks similar to the given track. Uses Last.fm + collaborative filtering + content-based."""
    from fastapi import HTTPException
    from rompmusic_server.services.recommendations import get_similar_tracks

    # Verify track exists
    check = await db.execute(select(Track).where(Track.id == track_id))
    if not check.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Track not found")

    rows = await get_similar_tracks(db, track_id, user_id, limit)
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
        for t, at, an in rows
    ]


@router.get("/tracks/recommended", response_model=list[TrackResponse])
async def list_recommended_tracks(
    limit: int = Query(20, ge=1, le=50),
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> list[TrackResponse]:
    """Get recommended tracks based on user's play history. Uses similar-to-recent + collaborative filtering."""
    from rompmusic_server.services.recommendations import get_recommended_tracks

    rows = await get_recommended_tracks(db, user_id, limit)
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
        for t, at, an in rows
    ]


@router.get("/tracks/{track_id}", response_model=TrackResponse)
async def get_track(
    track_id: int,
    db: AsyncSession = Depends(get_db),
) -> TrackResponse:
    """Get track by ID."""
    result = await db.execute(
        select(Track, Album.title, Artist.name)
        .join(Album, Track.album_id == Album.id)
        .join(Artist, Track.artist_id == Artist.id)
        .where(Track.id == track_id)
    )
    row = result.one_or_none()
    if not row:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Track not found")
    t, at, an = row
    return TrackResponse(
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
