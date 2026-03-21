# Copyright (C) 2024 RompMusic Contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests for Last.fm API integration (similar tracks, artist images) with API key.

Run: pytest tests/test_lastfm.py -v
Optional live smoke test (real API): LASTFM_API_KEY=yourkey pytest tests/test_lastfm.py -v
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from rompmusic_server.services.lastfm import get_artist_image_url
from rompmusic_server.services.recommendations import _fetch_lastfm_similar


@pytest.mark.asyncio
async def test_fetch_lastfm_similar_returns_empty_when_no_api_key():
    """Without an API key, _fetch_lastfm_similar returns an empty list."""
    with patch("rompmusic_server.services.recommendations.settings") as mock_settings:
        mock_settings.lastfm_api_key = None
        result = await _fetch_lastfm_similar("Artist", "Track", api_key=None)
    assert result == []


@pytest.mark.asyncio
async def test_fetch_lastfm_similar_returns_empty_when_empty_key():
    """With an empty string API key, _fetch_lastfm_similar returns an empty list."""
    result = await _fetch_lastfm_similar("Artist", "Track", api_key="")
    assert result == []


@pytest.mark.asyncio
async def test_fetch_lastfm_similar_parses_valid_response():
    """With a valid API key and mocked Last.fm response, similar tracks are parsed."""
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "similartracks": {
            "track": [
                {"artist": {"name": "Other Artist"}, "name": "Similar Track One", "match": 0.95},
                {"artist": {"name": "Another Band"}, "name": "Similar Track Two", "match": 0.8},
            ]
        }
    }

    mock_get = AsyncMock(return_value=mock_response)
    mock_client = MagicMock()
    mock_client.get = mock_get
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("rompmusic_server.services.recommendations.httpx.AsyncClient", return_value=mock_client):
        result = await _fetch_lastfm_similar("Seed Artist", "Seed Track", limit=10, api_key="test-key")

    assert len(result) == 2
    assert result[0] == ("Other Artist", "Similar Track One", 0.95)
    assert result[1] == ("Another Band", "Similar Track Two", 0.8)
    mock_get.assert_called_once()
    call_kwargs = mock_get.call_args[1]
    assert call_kwargs["params"]["method"] == "track.getSimilar"
    assert call_kwargs["params"]["artist"] == "Seed Artist"
    assert call_kwargs["params"]["track"] == "Seed Track"
    assert call_kwargs["params"]["api_key"] == "test-key"
    assert call_kwargs["params"]["format"] == "json"


@pytest.mark.asyncio
async def test_fetch_lastfm_similar_handles_single_track_dict():
    """Last.fm sometimes returns a single track as dict; we normalize to list."""
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "similartracks": {
            "track": {"artist": {"name": "Solo"}, "name": "One Hit", "match": 1.0}
        }
    }

    mock_client = MagicMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("rompmusic_server.services.recommendations.httpx.AsyncClient", return_value=mock_client):
        result = await _fetch_lastfm_similar("A", "B", api_key="key")

    assert len(result) == 1
    assert result[0] == ("Solo", "One Hit", 1.0)


@pytest.mark.asyncio
async def test_fetch_lastfm_similar_returns_empty_on_http_error():
    """On HTTP or request error, _fetch_lastfm_similar returns empty list."""
    mock_get = AsyncMock(side_effect=Exception("Network error"))

    mock_client = MagicMock()
    mock_client.get = mock_get
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("rompmusic_server.services.recommendations.httpx.AsyncClient", return_value=mock_client):
        result = await _fetch_lastfm_similar("Artist", "Track", api_key="key")

    assert result == []


# --- Artist image (get_artist_image_url) ---


@pytest.mark.asyncio
async def test_get_artist_image_url_returns_none_when_no_key():
    """Without an API key, get_artist_image_url returns None."""
    with patch("rompmusic_server.services.lastfm.settings") as mock_settings:
        mock_settings.lastfm_api_key = None
        result = await get_artist_image_url("Some Artist", api_key=None)
    assert result is None


@pytest.mark.asyncio
async def test_get_artist_image_url_parses_valid_response():
    """With a valid API key and mocked artist.getInfo response, image URL is returned."""
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "artist": {
            "image": [
                {"#text": "https://lastfm.fake/img/small.png", "size": "small"},
                {"#text": "https://lastfm.fake/img/medium.png", "size": "medium"},
            ]
        }
    }

    mock_client = MagicMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("rompmusic_server.services.lastfm.httpx.AsyncClient", return_value=mock_client):
        result = await get_artist_image_url("The Offspring", api_key="test-key")

    assert result == "https://lastfm.fake/img/medium.png"
    mock_client.get.assert_called_once()
    call_kwargs = mock_client.get.call_args[1]
    assert call_kwargs["params"]["method"] == "artist.getInfo"
    assert call_kwargs["params"]["api_key"] == "test-key"


# --- Optional: real API smoke test (run with LASTFM_API_KEY set to verify key works) ---


@pytest.mark.asyncio
@pytest.mark.skipif(
    not __import__("os").environ.get("LASTFM_API_KEY"),
    reason="LASTFM_API_KEY not set; set it to run real Last.fm API smoke test",
)
async def test_lastfm_api_key_works_live():
    """Call real Last.fm track.getSimilar and artist.getInfo to confirm API key works."""
    import os

    key = os.environ["LASTFM_API_KEY"]
    # Similar tracks for a well-known song
    similar = await _fetch_lastfm_similar("The Offspring", "Pretty Fly (For a White Guy)", limit=5, api_key=key)
    assert len(similar) > 0, "Last.fm track.getSimilar should return at least one result with a valid key"
    assert similar[0][0] and similar[0][1], "Each result should have artist and track name"

    # Artist image for a well-known artist
    url = await get_artist_image_url("The Offspring", api_key=key)
    assert url is not None, "Last.fm artist.getInfo should return an image URL with a valid key"
    assert url.startswith("http"), "Image URL should be absolute"
