# Copyright (C) 2024 RompMusic Contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Play history model."""

from datetime import datetime
from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from rompmusic_server.models.base import Base


class PlayHistory(Base):
    """Record of tracks played by users or anonymous (cookie) sessions."""

    __tablename__ = "play_history"
    __table_args__ = (
        CheckConstraint(
            "(user_id IS NOT NULL) OR (anonymous_id IS NOT NULL)",
            name="play_history_user_or_anonymous",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    anonymous_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    track_id: Mapped[int] = mapped_column(ForeignKey("tracks.id"), nullable=False)
    played_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    duration_played: Mapped[float | None] = mapped_column(Float, nullable=True)
