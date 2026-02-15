# Copyright (C) 2024 RompMusic Contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Server configuration - admin-controlled client settings policy."""

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from rompmusic_server.models.base import Base

# Default client settings policy when none is stored
DEFAULT_CLIENT_SETTINGS = {
    "display_albums_without_artwork": {"visible": True, "default": False},
    "display_artists_without_artwork": {"visible": True, "default": False},
    "group_artists_by_capitalization": {"visible": True, "default": True},
    "group_collaborations_by_primary": {"visible": True, "default": False},
    "audio_format": {"visible": True, "default": "original", "allowed": ["original", "ogg"]},
}


class ServerConfig(Base):
    """Key-value server configuration. Used for client settings policy."""

    __tablename__ = "server_config"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
