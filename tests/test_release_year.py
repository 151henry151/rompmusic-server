# Copyright (C) 2024 RompMusic Contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Treat missing/placeholder album years as null so Android does not crash on year=0."""

from datetime import datetime, timezone

from rompmusic_server.api.schemas import AlbumResponse, TrackResponse
from rompmusic_server.release_year import normalize_release_year
from rompmusic_server.services.scanner import _parse_year_tag


def test_normalize_release_year_none_stays_none():
    assert normalize_release_year(None) is None


def test_normalize_release_year_zero_becomes_none():
    assert normalize_release_year(0) is None


def test_normalize_release_year_negative_becomes_none():
    assert normalize_release_year(-1) is None


def test_normalize_release_year_keeps_real_year():
    assert normalize_release_year(1996) == 1996


def test_album_response_serializes_year_zero_as_null():
    album = AlbumResponse(
        id=6412,
        title="The Very Best of The Ink Spots",
        artist_id=1063,
        year=0,
    )
    assert album.year is None
    assert album.model_dump()["year"] is None


def test_album_response_keeps_real_year():
    album = AlbumResponse(id=1, title="Kind of Blue", artist_id=1, year=1959)
    assert album.year == 1959


def test_track_response_serializes_year_zero_as_null():
    track = TrackResponse(
        id=1,
        title="If I Didn't Care",
        album_id=6282,
        artist_id=1063,
        track_number=1,
        disc_number=1,
        duration=180.0,
        year=0,
        created_at=datetime.now(timezone.utc),
    )
    assert track.year is None


def test_parse_year_tag_zero_and_0000_are_missing():
    assert _parse_year_tag("0") is None
    assert _parse_year_tag("0000") is None


def test_parse_year_tag_reads_leading_four_digits():
    assert _parse_year_tag("1996") == 1996
    assert _parse_year_tag("1996-01-01") == 1996


def test_parse_year_tag_invalid_is_missing():
    assert _parse_year_tag(None) is None
    assert _parse_year_tag("") is None
    assert _parse_year_tag("abcd") is None
