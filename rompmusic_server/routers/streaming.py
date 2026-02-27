# Copyright (C) 2024 RompMusic Contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Streaming API - serves audio with HTTP range request support."""

import mimetypes
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import select

from rompmusic_server.auth import get_current_user_id
from rompmusic_server.config import settings
from rompmusic_server.database import get_db
from rompmusic_server.models import Track
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


@router.get("/{track_id}")
async def stream_track(
    track_id: int,
    request: Request,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """
    Stream a track with HTTP Range request support for seeking.
    Clients send Range: bytes=0- for partial content.
    """
    result = await db.execute(select(Track).where(Track.id == track_id))
    track = result.scalar_one_or_none()
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")

    full_path = Path(settings.music_path) / track.file_path
    if not full_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

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
