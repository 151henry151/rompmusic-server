# Copyright (C) 2024 RompMusic Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Add anonymous_id to play_history for public server (cookie-based) support.

Revision ID: 0002_play_anonymous
Revises: 0001_file_path_idx
Create Date: 2026-02-17

"""
from typing import Sequence, Union

from alembic import op

revision: str = "0002_play_anonymous"
down_revision: Union[str, None] = "0001_file_path_idx"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("play_history", op.Column("anonymous_id", op.String(64), nullable=True))
    op.alter_column(
        "play_history",
        "user_id",
        existing_type=op.Integer(),
        nullable=True,
    )
    op.create_check_constraint(
        "play_history_user_or_anonymous",
        "play_history",
        "(user_id IS NOT NULL) OR (anonymous_id IS NOT NULL)",
    )


def downgrade() -> None:
    op.drop_constraint("play_history_user_or_anonymous", "play_history", type_="check")
    op.alter_column(
        "play_history",
        "user_id",
        existing_type=op.Integer(),
        nullable=False,
    )
    op.drop_column("play_history", "anonymous_id")
