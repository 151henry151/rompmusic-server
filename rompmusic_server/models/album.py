# Copyright (C) 2024 RompMusic Contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Album model."""

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from rompmusic_server.models.base import Base
from rompmusic_server.models.timestamp import TimestampMixin


class Album(Base, TimestampMixin):
    """Music album."""

    __tablename__ = "albums"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    artist_id: Mapped[int] = mapped_column(ForeignKey("artists.id"), nullable=False)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    artwork_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    has_artwork: Mapped[bool | None] = mapped_column(Boolean, nullable=True, default=None)
    artwork_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    beets_id: Mapped[int | None] = mapped_column(Integer, unique=True, nullable=True, index=True)

    artist: Mapped["Artist"] = relationship("Artist", back_populates="albums")
    tracks: Mapped[list["Track"]] = relationship(
        "Track",
        back_populates="album",
        cascade="all, delete-orphan",
        order_by="Track.disc_number, Track.track_number",
    )


