# Copyright (C) 2024 RompMusic Contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Search API - search across artists, albums, tracks."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from rompmusic_server.auth import get_optional_user_id
from rompmusic_server.database import get_db
from rompmusic_server.models import Album, Artist, Track
from rompmusic_server.api.schemas import AlbumResponse, ArtistResponse, TrackResponse

router = APIRouter(prefix="/search", tags=["search"])


@router.get("")
async def search(
    q: str = Query(..., min_length=1),
    limit: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Search artists, albums, and tracks.
    Returns combined results with type indicator.
    """
    pattern = f"%{q}%"

    artists_result = await db.execute(
        select(Artist).where(Artist.name.ilike(pattern)).limit(limit)
    )
    artists = [ArtistResponse.model_validate(a) for a in artists_result.scalars().all()]

    albums_result = await db.execute(
        select(Album, Artist.name)
        .join(Artist, Album.artist_id == Artist.id)
        .where(Album.title.ilike(pattern))
        .limit(limit)
    )
    albums = [
        AlbumResponse(
            id=a.id,
            title=a.title,
            artist_id=a.artist_id,
            artist_name=an,
            year=a.year,
            artwork_path=a.artwork_path,
            has_artwork=a.has_artwork,
        )
        for a, an in albums_result.all()
    ]

    tracks_result = await db.execute(
        select(Track, Album.title, Artist.name)
        .join(Album, Track.album_id == Album.id)
        .join(Artist, Track.artist_id == Artist.id)
        .where(
            or_(
                Track.title.ilike(pattern),
                Album.title.ilike(pattern),
                Artist.name.ilike(pattern),
            )
        )
        .limit(limit)
    )
    tracks = [
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
        for t, at, an in tracks_result.all()
    ]

    return {
        "artists": artists,
        "albums": albums,
        "tracks": tracks,
    }
