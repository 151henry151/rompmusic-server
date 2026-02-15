# Copyright (C) 2024 RompMusic Contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Metadata quality helpers for home page filtering.

The home page should only show albums and tracks with complete, accurate metadata:
- Albums with embedded artwork (has_artwork=True)
- Tracks with real titles (not placeholders like "track 11", "track 22")
"""

import re

# Matches placeholder titles: "track 1", "track 11", "Track 22", "track01", etc.
_PLACEHOLDER_PATTERN = re.compile(r"^track\s*\d+\s*$", re.IGNORECASE)


def is_placeholder_track_title(title: str | None) -> bool:
    """Return True if the track title is a placeholder (e.g. 'track 11', 'track 22')."""
    if not title or not title.strip():
        return True
    return bool(_PLACEHOLDER_PATTERN.match(title.strip()))


def is_home_quality_track(track_title: str | None, album_has_artwork: bool | None) -> bool:
    """Return True if the track meets home page quality: real title + album has artwork."""
    if is_placeholder_track_title(track_title):
        return False
    # Only include when we know the album has artwork (exclude None and False)
    return album_has_artwork is True
