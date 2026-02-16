# Copyright (C) 2024 RompMusic Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Add index on tracks.file_path for scanner and dedup lookups.

Revision ID: 0001_file_path_idx
Revises:
Create Date: 2026-02-16

"""
from typing import Sequence, Union

from alembic import op

revision: str = "0001_file_path_idx"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_tracks_file_path",
        "tracks",
        ["file_path"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_tracks_file_path", table_name="tracks")
