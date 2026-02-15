# Copyright (C) 2024 RompMusic Contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Music library scanner using Mutagen for metadata extraction."""

import asyncio
from pathlib import Path
from typing import Any

from mutagen import File as MutagenFile
from mutagen.flac import FLAC
from mutagen.mp3 import MP3
from mutagen.mp4 import MP4
from mutagen.oggvorbis import OggVorbis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from rompmusic_server.config import settings
from rompmusic_server.models import Artist, Album, Track

SUPPORTED_EXTENSIONS = {".mp3", ".flac", ".m4a", ".ogg", ".oga", ".opus"}


def extract_metadata(file_path: Path) -> dict[str, Any] | None:
    """Extract metadata from a music file using Mutagen."""
    try:
        audio = MutagenFile(str(file_path))
        if audio is None:
            return None

        info = {
            "title": None,
            "artist": None,
            "album": None,
            "album_artist": None,
            "year": None,
            "track_number": 1,
            "disc_number": 1,
            "duration": float(getattr(audio.info, "length", 0) or 0),
            "bitrate": getattr(audio.info, "bitrate", None),
        }

        if hasattr(audio, "tags") and audio.tags:
            tags = audio.tags
            info["title"] = _get_tag(tags, ["\xa9nam", "TIT2", "title", "TITLE"])
            info["artist"] = _get_tag(tags, ["\xa9ART", "TPE1", "artist", "ARTIST"])
            info["album"] = _get_tag(tags, ["\xa9alb", "TALB", "album", "ALBUM"])
            info["album_artist"] = _get_tag(
                tags, ["aART", "TPE2", "albumartist", "ALBUMARTIST", "ARTIST"]
            )
            year_str = _get_tag(tags, ["\xa9day", "TDRC", "date", "DATE"])
            if year_str:
                try:
                    info["year"] = int(str(year_str)[:4])
                except (ValueError, TypeError):
                    pass
            tn = _get_tag(tags, ["trkn", "TRCK", "tracknumber", "TRACKNUMBER"])
            if tn:
                try:
                    info["track_number"] = int(str(tn).split("/")[0])
                except (ValueError, TypeError):
                    pass
            dn = _get_tag(tags, ["disk", "TPOS", "discnumber", "DISCNUMBER"])
            if dn:
                try:
                    info["disc_number"] = int(str(dn).split("/")[0])
                except (ValueError, TypeError):
                    pass

        if not info["artist"] and info["album_artist"]:
            info["artist"] = info["album_artist"]
        if not info["artist"]:
            info["artist"] = "Unknown Artist"
        if not info["album"]:
            info["album"] = "Unknown Album"
        if not info["title"]:
            info["title"] = file_path.stem

        return info
    except Exception:
        return None


def _get_tag(tags: Any, keys: list[str]) -> str | None:
    """Get first available tag value from a list of possible keys."""
    for key in keys:
        try:
            val = tags.get(key)
            if val is not None:
                if isinstance(val, (list, tuple)):
                    val = val[0] if val else None
                if isinstance(val, bytes):
                    val = val.decode("utf-8", errors="replace")
                if val:
                    return str(val).strip()
        except (KeyError, IndexError, TypeError):
            continue
    return None


async def scan_library(session: AsyncSession) -> dict[str, int]:
    """Scan the music directory and update the database. Returns counts."""
    music_path = Path(settings.music_path)
    if not music_path.exists():
        return {"artists": 0, "albums": 0, "tracks": 0}

    artists_map: dict[str, int] = {}
    albums_map: dict[tuple[str, str], int] = {}
    seen_tracks: set[str] = set()
    new_artists = 0
    new_albums = 0
    new_tracks = 0

    def walk_files() -> list[Path]:
        files = []
        for ext in SUPPORTED_EXTENSIONS:
            files.extend(music_path.rglob(f"*{ext}"))
        return files

    loop = asyncio.get_event_loop()
    files = await loop.run_in_executor(None, walk_files)

    for file_path in files:
        rel_path = str(file_path.relative_to(music_path))
        if rel_path in seen_tracks:
            continue

        meta = await loop.run_in_executor(None, extract_metadata, file_path)
        if not meta:
            continue

        artist_name = meta["artist"] or "Unknown Artist"
        album_title = meta["album"] or "Unknown Album"

        if artist_name not in artists_map:
            result = await session.execute(select(Artist).where(Artist.name == artist_name))
            artist = result.scalar_one_or_none()
            if not artist:
                artist = Artist(name=artist_name)
                session.add(artist)
                await session.flush()
                new_artists += 1
            artists_map[artist_name] = artist.id

        artist_id = artists_map[artist_name]
        key = (artist_name, album_title)
        if key not in albums_map:
            result = await session.execute(
                select(Album).where(
                    Album.artist_id == artist_id,
                    Album.title == album_title,
                )
            )
            album = result.scalar_one_or_none()
            if not album:
                album = Album(
                    title=album_title,
                    artist_id=artist_id,
                    year=meta.get("year"),
                )
                session.add(album)
                await session.flush()
                new_albums += 1
            albums_map[key] = album.id

        album_id = albums_map[key]
        result = await session.execute(
            select(Track).where(Track.file_path == rel_path)
        )
        if result.scalar_one_or_none() is None:
            track = Track(
                title=meta["title"] or file_path.stem,
                album_id=album_id,
                artist_id=artist_id,
                track_number=meta.get("track_number", 1),
                disc_number=meta.get("disc_number", 1),
                duration=meta["duration"],
                file_path=rel_path,
                bitrate=meta.get("bitrate"),
                format=file_path.suffix[1:].lower(),
            )
            session.add(track)
            new_tracks += 1

        seen_tracks.add(rel_path)

    await session.commit()
    return {
        "artists": len(artists_map),
        "albums": len(albums_map),
        "tracks": len(seen_tracks),
    }
