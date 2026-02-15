# Copyright (C) 2024 RompMusic Contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Artwork API - serves album/artist artwork."""

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from rompmusic_server.config import settings

router = APIRouter(prefix="/artwork", tags=["artwork"])

# Placeholder - artwork can be extracted from files or stored in cache
# For now we return 404; scanner can populate artwork_path later


@router.get("/album/{album_id}")
async def get_album_artwork(album_id: int):
    """Get album artwork by ID. Returns placeholder or cached image."""
    raise HTTPException(status_code=404, detail="Artwork not yet implemented")


@router.get("/artist/{artist_id}")
async def get_artist_artwork(artist_id: int):
    """Get artist artwork by ID."""
    raise HTTPException(status_code=404, detail="Artwork not yet implemented")
