# Copyright (C) 2024 RompMusic Contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Database models."""

from rompmusic_server.models.base import Base
from rompmusic_server.models.user import User
from rompmusic_server.models.artist import Artist
from rompmusic_server.models.album import Album
from rompmusic_server.models.track import Track
from rompmusic_server.models.playlist import Playlist, PlaylistTrack
from rompmusic_server.models.play_history import PlayHistory

__all__ = [
    "Base",
    "User",
    "Artist",
    "Album",
    "Track",
    "Playlist",
    "PlaylistTrack",
    "PlayHistory",
]
