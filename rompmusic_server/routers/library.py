# Copyright (C) 2024 RompMusic Contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Library API routes - artists, albums, tracks."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from rompmusic_server.auth import get_current_user_id, get_optional_user_id, get_user_id_or_anonymous
from rompmusic_server.database import get_db
from rompmusic_server.models import Album, Artist, PlayHistory, Track
from rompmusic_server.api.schemas import AlbumResponse, ArtistResponse, TrackResponse
from rompmusic_server.services.metadata_quality import is_home_quality_track

router = APIRouter(prefix="/library", tags=["library"])


def _artist_order(q, sort_by: str, order: str):
    """Apply sort to artist query."""
    from sqlalchemy import asc
    col = Artist.name if sort_by == "name" else Artist.created_at
    return q.order_by(desc(col) if order == "desc" else asc(col))


def _artist_primary_album_id():
    from sqlalchemy import asc
    return (
        select(Album.id)
        .where(Album.artist_id == Artist.id)
        .order_by(Album.year.desc().nullslast(), asc(Album.id))
        .limit(1)
        .scalar_subquery()
    )


def _artist_primary_album_title():
    from sqlalchemy import asc
    return (
        select(Album.title)
        .where(Album.artist_id == Artist.id)
        .order_by(Album.year.desc().nullslast(), asc(Album.id))
        .limit(1)
        .scalar_subquery()
    )


@router.get("/artists", response_model=list[ArtistResponse])
async def list_artists(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    search: str | None = Query(None),
    home: bool = Query(False, description="Home page: only artists with albums that have artwork"),
    sort_by: str = Query("name", description="Sort: name, date_added"),
    order: str = Query("asc", description="Order: asc, desc"),
    db: AsyncSession = Depends(get_db),
) -> list[ArtistResponse]:
    """List artists with optional search and sort."""
    from sqlalchemy import exists, or_

    has_artwork_subq = exists().where(Album.artist_id == Artist.id).where(Album.has_artwork == True)
    q = select(
        Artist,
        has_artwork_subq.label("has_artwork"),
        _artist_primary_album_id().label("primary_album_id"),
        _artist_primary_album_title().label("primary_album_title"),
    )
    if search:
        q = q.where(Artist.name.ilike(f"%{search}%"))
    if home:
        q = q.join(Album, Album.artist_id == Artist.id).where(Album.has_artwork == True)
        q = q.distinct()
    q = _artist_order(q, sort_by, order).offset(skip).limit(limit)
    result = await db.execute(q)
    rows = result.all()
    return [
        ArtistResponse(
            id=a.id,
            name=a.name,
            artwork_path=a.artwork_path,
            has_artwork=bool(has_art) if has_art is not None else None,
            primary_album_id=pid,
            primary_album_title=ptitle,
            created_at=a.created_at,
        )
        for a, has_art, pid, ptitle in rows
    ]


@router.get("/artists/{artist_id}", response_model=ArtistResponse)
async def get_artist(
    artist_id: int,
    db: AsyncSession = Depends(get_db),
) -> ArtistResponse:
    """Get artist by ID."""
    from sqlalchemy import exists, or_

    has_artwork_subq = exists().where(Album.artist_id == Artist.id).where(Album.has_artwork == True)
    result = await db.execute(
        select(
            Artist,
            has_artwork_subq.label("has_artwork"),
            _artist_primary_album_id().label("primary_album_id"),
            _artist_primary_album_title().label("primary_album_title"),
        ).where(Artist.id == artist_id)
    )
    row = result.one_or_none()
    if not row:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Artist not found")
    artist, has_art, pid, ptitle = row
    return ArtistResponse(
        id=artist.id,
        name=artist.name,
        artwork_path=artist.artwork_path,
        has_artwork=bool(has_art) if has_art is not None else None,
        primary_album_id=pid,
        primary_album_title=ptitle,
        created_at=artist.created_at,
    )


def _album_order(q, sort_by: str, order: str):
    """Apply sort to album query. q must have Album and Artist joined.
    For alphabetical sorts (title, artist), items starting with 0-9 or special
    characters are placed at the end; A-Z always come first.
    """
    from sqlalchemy import asc, case, func
    if sort_by == "year":
        col = Album.year
        return q.order_by(desc(col).nullslast() if order == "desc" else asc(col).nullslast())
    if sort_by == "date_added":
        col = Album.created_at
        return q.order_by(desc(col).nullslast() if order == "desc" else asc(col).nullslast())
    # Alphabetical sort: letters first, then numbers/symbols at the end
    if sort_by == "artist":
        col = Artist.name
    else:  # title
        col = Album.title
    first_char = func.lower(func.substr(col, 1, 1))
    letter_first = case((first_char.between("a", "z"), 0), else_=1)
    dir_col = desc(col).nullslast() if order == "desc" else asc(col).nullslast()
    return q.order_by(letter_first, dir_col)


@router.get("/albums", response_model=list[AlbumResponse])
async def list_albums(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    artist_id: int | None = Query(None),
    search: str | None = Query(None),
    sort_by: str = Query("year", description="Sort: year, date_added, artist, title"),
    order: str = Query("desc", description="Order: asc, desc"),
    random: bool = Query(False, description="Return random albums"),
    artwork_first: bool = Query(True, description="Put albums with artwork first (no-art at bottom)"),
    db: AsyncSession = Depends(get_db),
) -> list[AlbumResponse]:
    """List albums with optional filters and sort.
    When search is set, matches album title, artist name, or any track title on the album.
    When artwork_first is true, albums with artwork are listed before those without.
    """
    from sqlalchemy import asc, exists, func, or_
    q = select(Album, Artist.name).join(Artist, Album.artist_id == Artist.id)
    if artist_id:
        q = q.where(Album.artist_id == artist_id)
    if search:
        pattern = f"%{search}%"
        album_has_matching_track = exists().where(Track.album_id == Album.id).where(Track.title.ilike(pattern))
        q = q.where(
            or_(
                Album.title.ilike(pattern),
                Artist.name.ilike(pattern),
                album_has_matching_track,
            )
        )
    if random:
        q = q.order_by(func.random()).offset(skip).limit(limit)
    else:
        if artwork_first:
            q = q.order_by(desc(Album.has_artwork).nullslast())
        q = _album_order(q, sort_by, order).offset(skip).limit(limit)
    result = await db.execute(q)
    rows = result.all()
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
                has_artwork=a.has_artwork,
                artwork_hash=a.artwork_hash,
                track_count=tc or 0,
                created_at=a.created_at,
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
        has_artwork=album.has_artwork,
        artwork_hash=album.artwork_hash,
        track_count=track_count,
        created_at=album.created_at,
    )


def _track_order(q, sort_by: str, order: str, album_id: int | None = None):
    """Apply sort to track query. q must have Track, Album, Artist.
    When album_id is set, use disc_number then track_number so multi-disc albums play in order."""
    from sqlalchemy import asc
    if album_id is not None:
        return q.order_by(
            asc(Track.disc_number).nullslast(),
            asc(Track.track_number).nullslast(),
        )
    if sort_by == "year":
        col = Album.year
    elif sort_by == "date_added":
        col = Track.created_at
    elif sort_by == "artist":
        col = Artist.name
    elif sort_by == "album":
        col = Album.title
    else:  # title
        col = Track.title
    return q.order_by(desc(col).nullslast() if order == "desc" else asc(col).nullslast())


@router.get("/tracks", response_model=list[TrackResponse])
async def list_tracks(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=1000),
    album_id: int | None = Query(None),
    artist_id: int | None = Query(None),
    search: str | None = Query(None),
    sort_by: str = Query("title", description="Sort: year, date_added, artist, album, title"),
    order: str = Query("asc", description="Order: asc, desc"),
    db: AsyncSession = Depends(get_db),
) -> list[TrackResponse]:
    """List tracks with optional filters and sort."""
    q = (
        select(Track, Album.title, Artist.name, Album.year)
        .join(Album, Track.album_id == Album.id)
        .join(Artist, Track.artist_id == Artist.id)
    )
    if album_id:
        q = q.where(Track.album_id == album_id)
    if artist_id:
        q = q.where(Track.artist_id == artist_id)
    if search:
        q = q.where(Track.title.ilike(f"%{search}%"))
    q = _track_order(q, sort_by, order, album_id=album_id).offset(skip).limit(limit)
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
            year=yr,
            created_at=t.created_at,
        )
        for t, at, an, yr in rows
    ]


def _filter_home_quality(
    rows: list[tuple], limit: int
) -> list[TrackResponse]:
    """Filter to home-quality tracks (has artwork, real titles) and build responses."""
    from rompmusic_server.api.schemas import TrackResponse

    out = []
    for item in rows:
        if len(item) == 4:
            t, at, an, has_art = item
        else:
            t, at, an = item
            has_art = None
        if not is_home_quality_track(t.title, has_art):
            continue
        out.append(
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
        )
        if len(out) >= limit:
            break
    return out


@router.get("/tracks/recently-added", response_model=list[TrackResponse])
async def list_recently_added_tracks(
    limit: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
) -> list[TrackResponse]:
    """List most recently added tracks (by created_at). Home page: only quality metadata."""
    q = (
        select(Track, Album.title, Artist.name, Album.has_artwork)
        .join(Album, Track.album_id == Album.id)
        .join(Artist, Track.artist_id == Artist.id)
        .order_by(Track.created_at.desc())
        .limit(limit * 5)
    )
    result = await db.execute(q)
    rows = result.all()
    return _filter_home_quality(rows, limit)


def _play_history_filter_user_or_anon(user_id: int | None, anonymous_id: str | None):
    """Filter PlayHistory by user_id or anonymous_id (one must be set)."""
    if user_id is not None:
        return PlayHistory.user_id == user_id
    if anonymous_id is not None:
        return PlayHistory.anonymous_id == anonymous_id
    return None


@router.get("/tracks/recently-played", response_model=list[TrackResponse])
async def list_recently_played_tracks(
    limit: int = Query(20, ge=1, le=50),
    user_or_anon: tuple[int | None, str | None] = Depends(get_user_id_or_anonymous),
    db: AsyncSession = Depends(get_db),
) -> list[TrackResponse]:
    """List user's or anonymous session's recently played tracks. Public server: cookie-based anonymous."""
    user_id, anonymous_id = user_or_anon
    filt = _play_history_filter_user_or_anon(user_id, anonymous_id)
    if filt is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    subq = (
        select(PlayHistory.track_id, func.max(PlayHistory.played_at).label("last_played"))
        .where(filt)
        .group_by(PlayHistory.track_id)
    ).subquery()
    q = (
        select(Track, Album.title, Artist.name, Album.has_artwork)
        .join(Album, Track.album_id == Album.id)
        .join(Artist, Track.artist_id == Artist.id)
        .join(subq, Track.id == subq.c.track_id)
        .order_by(desc(subq.c.last_played))
        .limit(limit * 5)
    )
    result = await db.execute(q)
    rows = result.all()
    return _filter_home_quality(rows, limit)


@router.get("/tracks/frequently-played", response_model=list[TrackResponse])
async def list_frequently_played_tracks(
    limit: int = Query(20, ge=1, le=50),
    user_or_anon: tuple[int | None, str | None] = Depends(get_user_id_or_anonymous),
    db: AsyncSession = Depends(get_db),
) -> list[TrackResponse]:
    """List user's or anonymous session's frequently played tracks. Public server: cookie-based anonymous."""
    user_id, anonymous_id = user_or_anon
    filt = _play_history_filter_user_or_anon(user_id, anonymous_id)
    if filt is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    subq = (
        select(PlayHistory.track_id, func.count(PlayHistory.id).label("play_count"))
        .where(filt)
        .group_by(PlayHistory.track_id)
    ).subquery()
    q = (
        select(Track, Album.title, Artist.name, Album.has_artwork)
        .join(Album, Track.album_id == Album.id)
        .join(Artist, Track.artist_id == Artist.id)
        .join(subq, Track.id == subq.c.track_id)
        .order_by(desc(subq.c.play_count))
        .limit(limit * 5)
    )
    result = await db.execute(q)
    rows = result.all()
    return _filter_home_quality(rows, limit)


@router.get("/tracks/most-played", response_model=list[TrackResponse])
async def list_most_played_tracks(
    limit: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
) -> list[TrackResponse]:
    """List most played tracks server-wide. Home page: only quality metadata."""
    subq = (
        select(PlayHistory.track_id, func.count(PlayHistory.id).label("play_count"))
        .group_by(PlayHistory.track_id)
    ).subquery()
    q = (
        select(Track, Album.title, Artist.name, Album.has_artwork)
        .join(Album, Track.album_id == Album.id)
        .join(Artist, Track.artist_id == Artist.id)
        .join(subq, Track.id == subq.c.track_id)
        .order_by(desc(subq.c.play_count))
        .limit(limit * 5)
    )
    result = await db.execute(q)
    rows = result.all()
    return _filter_home_quality(rows, limit)


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
