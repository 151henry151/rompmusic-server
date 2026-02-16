# Copyright (C) 2024 RompMusic Contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Artwork API - serves album artwork from embedded metadata."""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from rompmusic_server.config import settings
from rompmusic_server.database import get_db
from rompmusic_server.models import Track
from rompmusic_server.services.artwork import extract_artwork_from_file

router = APIRouter(prefix="/artwork", tags=["artwork"])


@router.get("/album/{album_id}")
async def get_album_artwork(
    album_id: int,
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Get album artwork by ID. Extracts from first track's embedded metadata."""
    result = await db.execute(
        select(Track).where(Track.album_id == album_id).order_by(Track.disc_number, Track.track_number).limit(1)
    )
    track = result.scalar_one_or_none()
    if not track:
        raise HTTPException(status_code=404, detail="Album or tracks not found")
    full_path = Path(settings.music_path) / track.file_path
    artwork = extract_artwork_from_file(full_path)
    if not artwork:
        raise HTTPException(status_code=404, detail="No artwork found")
    data, mime = artwork
    return Response(content=data, media_type=mime)
