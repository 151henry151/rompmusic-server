# Copyright (C) 2024 RompMusic Contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Track model."""

from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from rompmusic_server.models.base import Base
from rompmusic_server.models.timestamp import TimestampMixin


class Track(Base, TimestampMixin):
    """Music track."""

    __tablename__ = "tracks"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    album_id: Mapped[int] = mapped_column(ForeignKey("albums.id"), nullable=False)
    artist_id: Mapped[int] = mapped_column(ForeignKey("artists.id"), nullable=False)
    track_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    disc_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    duration: Mapped[float] = mapped_column(Float, nullable=False)  # seconds
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    bitrate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    format: Mapped[str | None] = mapped_column(String(16), nullable=True)

    album: Mapped["Album"] = relationship("Album", back_populates="tracks")
    artist: Mapped["Artist"] = relationship("Artist", back_populates="tracks")
    playlist_tracks: Mapped[list["PlaylistTrack"]] = relationship(
        "PlaylistTrack", back_populates="track", cascade="all, delete-orphan"
    )
