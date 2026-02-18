# Copyright (C) 2024 RompMusic Contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Last.fm API integration for artist images and metadata."""

import logging
import re

import httpx

from rompmusic_server.config import settings

logger = logging.getLogger(__name__)


def _primary_artist_name(artist_name: str) -> str:
    """Extract primary artist name for Last.fm lookup (strip Feat., & His Orchestra, etc.)."""
    s = artist_name.strip()
    # Strip feat./ft.
    s = re.sub(r"\s+(?:feat\.?|ft\.?|featuring)\s+.*$", "", s, flags=re.I)
    # Strip ", X" (featured artist)
    if "," in s:
        s = s.split(",")[0].strip()
    # Strip " & His/Her Orchestra"
    s = re.sub(r"\s+&\s+(?:his|her)\s+.+$", "", s, flags=re.I)
    s = re.sub(r"\s+and\s+(?:his|her)\s+.+$", "", s, flags=re.I)
    # Strip " X Orchestra", " X Band", " X All-Stars"
    s = re.sub(r"\s+(?:orchestra|band|all[- ]?stars?)\s*$", "", s, flags=re.I)
    # Strip "The X Sextet/Quintet/etc"
    s = re.sub(r"\s+(?:sextet|septet|quintet|quartet|nonet|trio)\s*$", "", s, flags=re.I)
    # Strip parenthetical
    s = re.sub(r"\s*\([^)]*\)\s*$", "", s).strip()
    # Strip "The " prefix
    if s.lower().startswith("the "):
        s = s[4:].strip()
    return s or artist_name


async def get_artist_image_url(artist_name: str, api_key: str | None = None) -> str | None:
    """
    Fetch artist image URL from Last.fm artist.getInfo.
    Returns the medium-sized image URL (e.g. 160px) or None if not found.
    """
    key = api_key or settings.lastfm_api_key
    if not key or not artist_name:
        return None
    primary = _primary_artist_name(artist_name)
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(
                "http://ws.audioscrobbler.com/2.0/",
                params={
                    "method": "artist.getInfo",
                    "artist": primary,
                    "api_key": key,
                    "format": "json",
                    "autocorrect": 1,
                },
            )
            r.raise_for_status()
            data = r.json()
    except Exception as e:
        logger.debug("Last.fm artist.getInfo failed for %r: %s", primary, e)
        return None

    artist = data.get("artist")
    if not isinstance(artist, dict):
        return None
    images = artist.get("image", [])
    if isinstance(images, dict):
        images = [images]
    # Prefer largest available for better quality on artist cards
    for size in ("mega", "extralarge", "large", "medium"):
        for img in images:
            if isinstance(img, dict) and img.get("#text") and img.get("size") == size:
                url = (img.get("#text") or "").strip()
                if url and url.startswith("http"):
                    return url
    # Fallback: any image with URL
    for img in images:
        if isinstance(img, dict):
            url = (img.get("#text") or "").strip()
            if url and url.startswith("http"):
                return url
    return None
