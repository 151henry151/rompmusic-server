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


async def _fetch_lastfm_similar(artist: str, track: str, limit: int = 30) -> list[tuple[str, str, float]]:
    """Fetch similar tracks from Last.fm. Returns [(artist, track, match_score), ...]."""
    if not settings.lastfm_api_key:
        return []
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(
                "http://ws.audioscrobbler.com/2.0/",
                params={
                    "method": "track.getSimilar",
                    "artist": artist,
                    "track": track,
                    "api_key": settings.lastfm_api_key,
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


async def _match_lastfm_to_library(
    db: AsyncSession,
    similar: list[tuple[str, str, float]],
    exclude_track_id: int,
    limit: int,
) -> list[tuple[int, float]]:
    """Match Last.fm results to our library. Returns [(track_id, score), ...]."""
    if not similar:
        return []

    # Build list of (artist_norm, track_norm, lastfm_score) for matching
    targets = []
    for artist, track, score in similar:
        targets.append((_normalize_for_match(artist), _normalize_for_match(track), score))

    # Fetch our tracks with artist name and title
    q = (
        select(Track.id, Artist.name, Track.title)
        .join(Album, Track.album_id == Album.id)
        .join(Artist, Track.artist_id == Artist.id)
        .where(Track.id != exclude_track_id)
    )
    result = await db.execute(q)
    rows = result.all()

    def _str_similar(a: str, b: str) -> bool:
        if not a or not b:
            return False
        if a == b:
            return True
        if a in b or b in a:
            return True
        # First 6 chars match
        if len(a) >= 4 and len(b) >= 4 and a[:4] == b[:4]:
            return True
        return False

    matched: list[tuple[int, float]] = []
    seen_ids: set[int] = set()
    for track_id, our_artist, our_title in rows:
        if track_id in seen_ids:
            continue
        our_a_norm = _normalize_for_match(our_artist or "")
        our_t_norm = _normalize_for_match(our_title or "")
        for lf_artist_norm, lf_track_norm, lf_score in targets:
            a_ok = _str_similar(our_a_norm, lf_artist_norm)
            t_ok = _str_similar(our_t_norm, lf_track_norm)
            if a_ok and t_ok:
                matched.append((track_id, lf_score))
                seen_ids.add(track_id)
                break
        if len(matched) >= limit:
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


async def get_similar_tracks(
    db: AsyncSession,
    track_id: int,
    user_id: int | None,
    limit: int = 20,
) -> list[tuple[Track, str | None, str | None]]:
    """
    Hybrid similar tracks: Last.fm + our collaborative filtering + content-based.
    Blends scores and deduplicates, favoring external data when available.
    """
    # Get seed track
    result = await db.execute(
        select(Track, Artist.name)
        .join(Album, Track.album_id == Album.id)
        .join(Artist, Track.artist_id == Artist.id)
        .where(Track.id == track_id)
    )
    row = result.one_or_none()
    if not row:
        return []  # type: ignore
    track, artist_name = row

    combined: dict[int, float] = {}

    # 1. Last.fm (weight 2.0 - strong signal when we get matches)
    lastfm_similar = await _fetch_lastfm_similar(artist_name or "", track.title or "", limit=limit * 2)
    lastfm_matched = await _match_lastfm_to_library(db, lastfm_similar, track_id, limit)
    for tid, score in lastfm_matched:
        combined[tid] = combined.get(tid, 0) + score * 2.0

    # 2. Collaborative filtering (weight 1.5 - our own data, very relevant)
    cf_results = await _collaborative_filtering(db, track_id, user_id, limit)
    for tid, score in cf_results:
        combined[tid] = combined.get(tid, 0) + score * 1.5

    # 3. Content-based fallback (weight 0.8 - same artist)
    cb_results = await _content_based_fallback(db, track.artist_id, track_id, limit)
    for tid, score in cb_results:
        combined[tid] = combined.get(tid, 0) + score * 0.8

    # Sort by blended score, take top limit
    sorted_ids = sorted(combined.items(), key=lambda x: -x[1])[:limit]
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
    return [(by_id[tid][0], by_id[tid][1], by_id[tid][2]) for tid in track_ids if tid in by_id]


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
