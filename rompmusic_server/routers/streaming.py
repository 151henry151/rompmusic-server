# Copyright (C) 2024 RompMusic Contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Streaming API - serves audio with HTTP range request support."""

import asyncio
import mimetypes
import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import select

from rompmusic_server.auth import get_optional_user_id_for_stream
from rompmusic_server.config import settings
from rompmusic_server.database import get_db
from rompmusic_server.models import PlayHistory, Track
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/stream", tags=["streaming"])

EXT_MIME = {
    "mp3": "audio/mpeg",
    "flac": "audio/flac",
    "m4a": "audio/mp4",
    "ogg": "audio/ogg",
    "oga": "audio/ogg",
    "opus": "audio/opus",
}


def get_mime(path: Path) -> str:
    """Get MIME type for audio file."""
    ext = path.suffix.lower().lstrip(".")
    return EXT_MIME.get(ext) or mimetypes.guess_type(str(path))[0] or "application/octet-stream"


async def _transcode_to_ogg(full_path: Path):
    """Stream transcoded OGG Vorbis. Yields bytes. No range support."""
    ffmpeg = shutil.which(settings.ffmpeg_path) or settings.ffmpeg_path
    proc = await asyncio.create_subprocess_exec(
        ffmpeg,
        "-i", str(full_path),
        "-f", "ogg",
        "-acodec", "libvorbis",
        "-q:a", "5",  # VBR quality ~160kbps
        "-",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    chunk_size = 64 * 1024
    while True:
        chunk = await proc.stdout.read(chunk_size)
        if not chunk:
            break
        yield chunk
    await proc.wait()


@router.get("/{track_id}")
async def stream_track(
    track_id: int,
    request: Request,
    format: str | None = "original",
    user_id: int | None = Depends(get_optional_user_id_for_stream),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """
    Stream a track with HTTP Range request support for seeking.
    Clients send Range: bytes=0- for partial content.
    Auth optional: if token provided, records play history.
    """
    result = await db.execute(select(Track).where(Track.id == track_id))
    track = result.scalar_one_or_none()
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")

    # Record play history when authenticated (fire-and-forget)
    if user_id is not None:
        db.add(PlayHistory(user_id=user_id, track_id=track_id))
    try:
        await db.flush()
    except Exception:
        pass

    base = Path(settings.music_path).resolve()
    full_path = (base / track.file_path).resolve()
    if not full_path.is_relative_to(base) or not full_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    # Transcode to OGG when requested (no range support)
    if (format or "").lower() == "ogg":
        return StreamingResponse(
            _transcode_to_ogg(full_path),
            media_type="audio/ogg",
            headers={"Content-Disposition": f'inline; filename="{full_path.stem}.ogg"'},
        )

    file_size = full_path.stat().st_size
    mime = get_mime(full_path)

    range_header = request.headers.get("range")
    if not range_header:
        return FileResponse(
            full_path,
            media_type=mime,
            filename=full_path.name,
        )

    # Parse Range: bytes=start-end
    try:
        range_str = range_header.replace("bytes=", "").strip()
        if "-" in range_str:
            start_str, end_str = range_str.split("-", 1)
            start = int(start_str) if start_str else 0
            end = int(end_str) if end_str else file_size - 1
        else:
            start = 0
            end = file_size - 1
    except (ValueError, IndexError):
        raise HTTPException(status_code=400, detail="Invalid Range header")

    if start >= file_size:
        raise HTTPException(status_code=416, detail="Range not satisfiable")

    end = min(end, file_size - 1)
    content_length = end - start + 1

    def iter_file():
        with open(full_path, "rb") as f:
            f.seek(start)
            remaining = content_length
            chunk_size = 256 * 1024
            while remaining > 0:
                to_read = min(chunk_size, remaining)
                data = f.read(to_read)
                if not data:
                    break
                remaining -= len(data)
                yield data

    return Response(
        content=iter_file(),
        status_code=206,
        media_type=mime,
        headers={
            "Accept-Ranges": "bytes",
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Content-Length": str(content_length),
        },
    )
