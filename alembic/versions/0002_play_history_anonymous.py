# Copyright (C) 2024 RompMusic Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Add anonymous_id to play_history for public server (cookie-based) support.

Revision ID: 0002_play_anonymous
Revises: 0001_file_path_idx
Create Date: 2026-02-17

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002_play_anonymous"
down_revision: Union[str, None] = "0001_file_path_idx"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"]: column for column in inspector.get_columns("play_history")}
    if "anonymous_id" not in columns:
        op.add_column("play_history", sa.Column("anonymous_id", sa.String(64), nullable=True))
    if not columns.get("user_id", {}).get("nullable", False):
        op.alter_column(
            "play_history",
            "user_id",
            existing_type=sa.Integer(),
            nullable=True,
        )
    check_constraints = {constraint.get("name") for constraint in inspector.get_check_constraints("play_history")}
    if "play_history_user_or_anonymous" not in check_constraints:
        op.create_check_constraint(
            "play_history_user_or_anonymous",
            "play_history",
            "(user_id IS NOT NULL) OR (anonymous_id IS NOT NULL)",
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    check_constraints = {constraint.get("name") for constraint in inspector.get_check_constraints("play_history")}
    if "play_history_user_or_anonymous" in check_constraints:
        op.drop_constraint("play_history_user_or_anonymous", "play_history", type_="check")
    columns = {column["name"]: column for column in inspector.get_columns("play_history")}
    if columns.get("user_id", {}).get("nullable", True):
        op.alter_column(
            "play_history",
            "user_id",
            existing_type=sa.Integer(),
            nullable=False,
        )
    if "anonymous_id" in columns:
        op.drop_column("play_history", "anonymous_id")
