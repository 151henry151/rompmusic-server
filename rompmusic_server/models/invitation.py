# Copyright (C) 2024 RompMusic Contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Invitation model - admin-invited users by email."""

from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from rompmusic_server.models.base import Base


class Invitation(Base):
    """Invitation to create an account. Admin sends email; invitee clicks link to set password or activate."""

    __tablename__ = "invitations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    invited_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
