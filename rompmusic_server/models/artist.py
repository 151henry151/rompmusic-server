# Copyright (C) 2024 RompMusic Contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Artist model."""

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from rompmusic_server.models.base import Base
from rompmusic_server.models.timestamp import TimestampMixin


class Artist(Base, TimestampMixin):
    """Music artist."""

    __tablename__ = "artists"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    beets_id: Mapped[int | None] = mapped_column(Integer, unique=True, nullable=True, index=True)
    artwork_path: Mapped[str | None] = mapped_column(String(512), nullable=True)

    albums: Mapped[list["Album"]] = relationship(
        "Album", back_populates="artist", cascade="all, delete-orphan"
    )
    tracks: Mapped[list["Track"]] = relationship(
        "Track", back_populates="artist", cascade="all, delete-orphan"
    )


