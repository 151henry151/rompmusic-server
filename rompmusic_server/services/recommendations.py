# Copyright (C) 2024 RompMusic Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
#
# Recommendations engine: hybrid Last.fm + collaborative filtering + content-based.
# Inspired by YouTube Music / Spotify: multiple signals, weighted blending.

import logging
import re
from collections import defaultdict

import httpx
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from rompmusic_server.config import settings
from rompmusic_server.models import Album, Artist, PlayHistory, Track
from rompmusic_server.services.metadata_quality import is_home_quality_track

logger = logging.getLogger(__name__)


def _normalize(s: str) -> str:
    """Normalize for fuzzy matching: lowercase, collapse whitespace, strip punctuation."""
    if not s:
        return ""
    s = s.lower().strip()
    s = re.sub(r"[^\w\s]", "", s)
    s = re.sub(r"\s+", " ", s)
    return s


def _normalize_for_match(s: str) -> str:
    """Aggressive normalization for matching: remove common suffixes, etc."""
    s = _normalize(s)
    # Remove "remaster", "live", etc. for better matching
    for suffix in ["remaster", "remastered", "live", "acoustic", "edit", "radio edit"]:
        s = re.sub(rf"\b{suffix}\b", "", s, flags=re.I)
    return re.sub(r"\s+", " ", s).strip()


async def _fetch_lastfm_similar(
    artist: str, track: str, limit: int = 30, api_key: str | None = None
) -> list[tuple[str, str, float]]:
    """Fetch similar tracks from Last.fm. Returns [(artist, track, match_score), ...]."""
    key = api_key or settings.lastfm_api_key
    if not key:
        return []
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(
                "http://ws.audioscrobbler.com/2.0/",
                params={
                    "method": "track.getSimilar",
                    "artist": artist,
                    "track": track,
                    "api_key": key,
                    "format": "json",
                    "limit": limit,
                    "autocorrect": 1,
                },
            )
            r.raise_for_status()
            data = r.json()
    except Exception as e:
        logger.warning("Last.fm similar fetch failed: %s", e)
        return []

    similar = data.get("similartracks", {}).get("track", [])
    if isinstance(similar, dict):
        similar = [similar]
    out = []
    for i, item in enumerate(similar[:limit]):
        a = item.get("artist", {}).get("name", "")
        t = item.get("name", "")
        if a and t:
            # Last.fm returns match as 0-1; top results are most similar
            match_val = float(item.get("match", 1.0))
            out.append((a, t, match_val))
    return out


def _str_similar(a: str, b: str) -> bool:
    """True if two normalized strings are considered the same for matching."""
    if not a or not b:
        return False
    if a == b:
        return True
    if a in b or b in a:
        return True
    if len(a) >= 4 and len(b) >= 4 and a[:4] == b[:4]:
        return True
    return False


async def _match_lastfm_to_library(
    db: AsyncSession,
    similar: list[tuple[str, str, float]],
    exclude_track_id: int,
    limit: int,
) -> list[tuple[int, float]]:
    """
    Match Last.fm results to our library. Returns [(track_id, score), ...].
    First: exact (artist + track) matches with full score.
    Then: artist-only matches (we have that artist but not the exact track) with reduced score
    so similar-artist variety appears even when the exact track is not in the library.
    """
    if not similar:
        return []

    targets = []
    for artist, track, score in similar:
        targets.append((_normalize_for_match(artist), _normalize_for_match(track), score))

    q = (
        select(Track.id, Artist.name, Track.title)
        .join(Album, Track.album_id == Album.id)
        .join(Artist, Track.artist_id == Artist.id)
        .where(Track.id != exclude_track_id)
    )
    result = await db.execute(q)
    rows = result.all()

    matched: list[tuple[int, float]] = []
    seen_ids: set[int] = set()

    # 1) Exact (artist + track) matches with full Last.fm score
    for track_id, our_artist, our_title in rows:
        if track_id in seen_ids or len(matched) >= limit:
            break
        our_a_norm = _normalize_for_match(our_artist or "")
        our_t_norm = _normalize_for_match(our_title or "")
        for lf_artist_norm, lf_track_norm, lf_score in targets:
            if _str_similar(our_a_norm, lf_artist_norm) and _str_similar(our_t_norm, lf_track_norm):
                matched.append((track_id, lf_score))
                seen_ids.add(track_id)
                break

    # 2) Artist-only matches: Last.fm said this artist is similar; add any of their tracks we have
    artist_only_score_scale = 0.6
    for track_id, our_artist, our_title in rows:
        if track_id in seen_ids or len(matched) >= limit:
            break
        our_a_norm = _normalize_for_match(our_artist or "")
        for lf_artist_norm, _lf_track_norm, lf_score in targets:
            if _str_similar(our_a_norm, lf_artist_norm):
                score = lf_score * artist_only_score_scale
                matched.append((track_id, score))
                seen_ids.add(track_id)
                break

    return matched[:limit]


async def _collaborative_filtering(
    db: AsyncSession,
    track_id: int,
    user_id: int | None,
    limit: int,
) -> list[tuple[int, float]]:
    """
    "Users who played X also played Y" - implicit collaborative filtering.
    Co-occurrence: count how often track Y was played in same session/context as X.
    """
    # Sessions: consecutive plays by same user within 30 min = same "session"
    # Simplified: users who played track_id also played these tracks (by play order proximity)
    subq = (
        select(
            PlayHistory.user_id,
            PlayHistory.track_id,
            PlayHistory.played_at,
            func.lag(PlayHistory.track_id).over(
                partition_by=PlayHistory.user_id,
                order_by=PlayHistory.played_at,
            ).label("prev_track"),
            func.lead(PlayHistory.track_id).over(
                partition_by=PlayHistory.user_id,
                order_by=PlayHistory.played_at,
            ).label("next_track"),
        )
        .where(PlayHistory.track_id == track_id)
    ).subquery()

    # Get prev_track and next_track when track_id was played
    q = select(subq.c.prev_track, subq.c.next_track).where(
        (subq.c.prev_track.isnot(None)) | (subq.c.next_track.isnot(None))
    )
    result = await db.execute(q)
    rows = result.all()

    co_counts: dict[int, float] = defaultdict(float)
    for prev, nxt in rows:
        for tid in (prev, nxt):
            if tid and tid != track_id:
                co_counts[tid] += 1.0

    sorted_co = sorted(co_counts.items(), key=lambda x: -x[1])[:limit]
    return [(tid, score) for tid, score in sorted_co]


async def _content_based_fallback(
    db: AsyncSession,
    artist_id: int,
    exclude_track_id: int,
    limit: int,
) -> list[tuple[int, float]]:
    """Same artist, different tracks. Score decays by album distance."""
    q = (
        select(Track.id)
        .where(Track.artist_id == artist_id, Track.id != exclude_track_id)
        .order_by(Track.album_id, Track.disc_number, Track.track_number)
        .limit(limit * 2)
    )
    result = await db.execute(q)
    ids = [r[0] for r in result.all()]
    # Score: first tracks get higher score
    return [(tid, 1.0 - (i * 0.05)) for i, tid in enumerate(ids[:limit])]


# Year window for "similar era" when no Last.fm (e.g. ±5 years)
METADATA_YEAR_WINDOW = 5


async def _metadata_based_similar(
    db: AsyncSession,
    exclude_track_id: int,
    artist_id: int,
    album_id: int,
    album_year: int | None,
    limit: int,
) -> list[tuple[int, float]]:
    """
    Recommendations from metadata when Last.fm is not available.
    Uses: same artist (other albums), similar release year, compilations featuring this artist.
    Favours variety: different artists, different albums; caller caps per-artist (e.g. max 2).
    Genre is not in the DB yet; could be added from file tags (e.g. TCON genre tag) later.
    """
    combined: dict[int, float] = {}

    # 1) Same artist, other albums: up to half of limit, spread across albums (max 2 per album)
    q_other_albums = (
        select(Track.id, Track.album_id)
        .where(
            Track.artist_id == artist_id,
            Track.album_id != album_id,
            Track.id != exclude_track_id,
        )
        .order_by(Track.album_id, Track.disc_number, Track.track_number)
    )
    result = await db.execute(q_other_albums)
    rows = result.all()
    per_album: dict[int, list[int]] = defaultdict(list)
    for tid, aid in rows:
        per_album[aid].append(tid)
    taken = 0
    max_per_album = 2
    target_same_artist = min(limit // 2, 15)
    for aid in sorted(per_album.keys()):
        if taken >= target_same_artist:
            break
        for tid in per_album[aid][:max_per_album]:
            combined[tid] = 1.0
            taken += 1
            if taken >= target_same_artist:
                break

    # 2) Similar year: albums within ±METADATA_YEAR_WINDOW years (exclude seed album and seed artist for variety)
    if album_year is not None:
        year_lo = max(1900, album_year - METADATA_YEAR_WINDOW)
        year_hi = album_year + METADATA_YEAR_WINDOW
        q_year = (
            select(Track.id, Track.artist_id, Album.year)
            .join(Album, Track.album_id == Album.id)
            .where(
                Track.id != exclude_track_id,
                Track.album_id != album_id,
                Album.year >= year_lo,
                Album.year <= year_hi,
            )
        )
        result = await db.execute(q_year)
        year_rows = result.all()
        # Score by year proximity; we'll diversify by artist when building the final list
        for tid, tid_artist_id, yr in year_rows:
            if yr is None:
                continue
            dist = abs(yr - album_year)
            score = 0.85 * (1.0 - min(dist / (METADATA_YEAR_WINDOW + 1), 1.0))
            combined[tid] = max(combined.get(tid, 0), score)

    # 3) Compilations that feature this artist: other tracks from those albums (any artist)
    subq_album_artists = (
        select(Track.album_id, func.count(func.distinct(Track.artist_id)).label("n_artists"))
        .group_by(Track.album_id)
    ).subquery()
    subq_has_seed = (
        select(Track.album_id)
        .where(Track.artist_id == artist_id)
        .distinct()
    ).subquery()
    q_comp = (
        select(Track.id)
        .join(subq_album_artists, Track.album_id == subq_album_artists.c.album_id)
        .join(subq_has_seed, Track.album_id == subq_has_seed.c.album_id)
        .where(
            subq_album_artists.c.n_artists > 1,
            Track.id != exclude_track_id,
        )
    )
    result = await db.execute(q_comp)
    for (tid,) in result.all():
        combined[tid] = max(combined.get(tid, 0), 0.75)

    # Sort by score and return; caller will diversify by artist
    sorted_ids = sorted(combined.items(), key=lambda x: -x[1])[:limit * 3]
    return sorted_ids


async def get_similar_tracks(
    db: AsyncSession,
    track_id: int,
    user_id: int | None,
    limit: int = 20,
    lastfm_api_key: str | None = None,
) -> list[tuple[Track, str | None, str | None]]:
    """
    Hybrid similar tracks: Last.fm + our collaborative filtering + content-based.
    Blends scores and deduplicates, favoring external data when available.
    """
    if lastfm_api_key is None:
        from rompmusic_server.services.server_settings import get_api_keys
        api_keys = await get_api_keys(db)
        lastfm_api_key = api_keys.get("lastfm") or settings.lastfm_api_key
    # Get seed track and album year (for metadata-based fallback when no Last.fm)
    result = await db.execute(
        select(Track, Artist.name, Album.year)
        .join(Album, Track.album_id == Album.id)
        .join(Artist, Track.artist_id == Artist.id)
        .where(Track.id == track_id)
    )
    row = result.one_or_none()
    if not row:
        return []  # type: ignore
    track, artist_name, album_year = row

    combined: dict[int, float] = {}

    # 1. Last.fm (weight 2.0 - strong signal when we get matches)
    lastfm_similar = await _fetch_lastfm_similar(
        artist_name or "", track.title or "", limit=limit * 2, api_key=lastfm_api_key
    )
    lastfm_matched = await _match_lastfm_to_library(db, lastfm_similar, track_id, limit)
    have_lastfm = len(lastfm_matched) > 0
    for tid, score in lastfm_matched:
        combined[tid] = combined.get(tid, 0) + score * 2.0

    # 2. Collaborative filtering - only use when we have Last.fm; otherwise co-play data adds unrelated artists
    if have_lastfm:
        cf_results = await _collaborative_filtering(db, track_id, user_id, limit)
        for tid, score in cf_results:
            combined[tid] = combined.get(tid, 0) + score * 1.5

    # 3. When no Last.fm: metadata-based (same artist other albums, similar year, compilations). Else content-based for variety.
    if not have_lastfm:
        meta_results = await _metadata_based_similar(
            db, track_id, track.artist_id, track.album_id, album_year, limit
        )
        for tid, score in meta_results:
            combined[tid] = combined.get(tid, 0) + score
    else:
        cb_results = await _content_based_fallback(db, track.artist_id, track_id, limit)
        for tid, score in cb_results:
            combined[tid] = combined.get(tid, 0) + score * 0.4

    # Sort by blended score, take more than limit so we can diversify
    sorted_ids = sorted(combined.items(), key=lambda x: -x[1])[:limit * 3]
    if not sorted_ids:
        # Pure fallback: same artist
        cb = await _content_based_fallback(db, track.artist_id, track_id, limit)
        sorted_ids = cb

    track_ids = [tid for tid, _ in sorted_ids]
    if not track_ids:
        return []

    # Fetch full track data with album/artist names
    q = (
        select(Track, Album.title, Artist.name)
        .join(Album, Track.album_id == Album.id)
        .join(Artist, Track.artist_id == Artist.id)
        .where(Track.id.in_(track_ids))
    )
    result = await db.execute(q)
    rows = result.all()
    by_id = {t.id: (t, at, an) for t, at, an in rows}

    # Diversify: cap tracks per artist so we don't return only same-artist (max 2 per artist)
    order_by_score = [tid for tid in track_ids if tid in by_id]
    seen_per_artist: dict[int, int] = defaultdict(int)
    diversified: list[int] = []
    for tid in order_by_score:
        t, _, _ = by_id[tid]
        if seen_per_artist[t.artist_id] >= 2:
            continue
        seen_per_artist[t.artist_id] += 1
        diversified.append(tid)
        if len(diversified) >= limit:
            break
    # If we have too few (e.g. library is small), fill with remaining by score
    for tid in order_by_score:
        if len(diversified) >= limit:
            break
        if tid not in diversified:
            diversified.append(tid)

    return [(by_id[tid][0], by_id[tid][1], by_id[tid][2]) for tid in diversified if tid in by_id]


async def get_recommended_tracks(
    db: AsyncSession,
    user_id: int,
    limit: int = 20,
) -> list[tuple[Track, str | None, str | None]]:
    """
    "Recommended for you" - based on user's play history.
    Uses collaborative filtering from our data + similar-to-recently-played via Last.fm.
    """
    # Get user's recently played track IDs
    subq = (
        select(PlayHistory.track_id, func.max(PlayHistory.played_at).label("last_played"))
        .where(PlayHistory.user_id == user_id)
        .group_by(PlayHistory.track_id)
    ).subquery()
    q = (
        select(Track.id)
        .join(subq, Track.id == subq.c.track_id)
        .order_by(desc(subq.c.last_played))
        .limit(5)
    )
    result = await db.execute(q)
    recent_ids = [r[0] for r in result.all()]

    combined: dict[int, float] = {}
    seen_recent: set[int] = set(recent_ids)

    # For each recently played, get similar and add to pool (weighted by recency)
    for i, seed_id in enumerate(recent_ids):
        weight = 1.0 - (i * 0.15)  # First = 1.0, then 0.85, 0.7, ...
        similar = await get_similar_tracks(db, seed_id, user_id, limit=limit // 2 + 5)
        for t, _, _ in similar:
            if t.id not in seen_recent:
                combined[t.id] = combined.get(t.id, 0) + weight

    if not combined:
        # No history: return recently added (filtered for home quality)
        q = (
            select(Track, Album.title, Artist.name, Album.has_artwork)
            .join(Album, Track.album_id == Album.id)
            .join(Artist, Track.artist_id == Artist.id)
            .order_by(desc(Track.created_at))
            .limit(limit * 5)
        )
        result = await db.execute(q)
        rows = result.all()
        out = []
        for t, at, an, has_art in rows:
            if is_home_quality_track(t.title, has_art):
                out.append((t, at, an))
                if len(out) >= limit:
                    break
        return out

    sorted_ids = sorted(combined.items(), key=lambda x: -x[1])[:limit * 3]
    track_ids = [tid for tid, _ in sorted_ids]

    q = (
        select(Track, Album.title, Artist.name, Album.has_artwork)
        .join(Album, Track.album_id == Album.id)
        .join(Artist, Track.artist_id == Artist.id)
        .where(Track.id.in_(track_ids))
    )
    result = await db.execute(q)
    by_id = {t.id: (t, at, an, has_art) for t, at, an, has_art in result.all()}
    out = []
    for tid in track_ids:
        if tid not in by_id:
            continue
        t, at, an, has_art = by_id[tid]
        if is_home_quality_track(t.title, has_art):
            out.append((t, at, an))
            if len(out) >= limit:
                break
    return out
