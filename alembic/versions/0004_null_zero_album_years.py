# Copyright (C) 2024 RompMusic Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Set placeholder album year 0 (and negative years) to NULL.

Revision ID: 0004_null_zero_album_years
Revises: 0003_playlists_ordering
Create Date: 2026-08-12
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0004_null_zero_album_years"
down_revision: Union[str, None] = "0003_playlists_ordering"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("UPDATE albums SET year = NULL WHERE year IS NOT NULL AND year <= 0")


def downgrade() -> None:
    # Placeholder years cannot be restored.
    pass
