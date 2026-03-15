# Copyright (C) 2024 RompMusic Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Add playlist ordering metadata and updated timestamps.

Revision ID: 0003_playlists_ordering
Revises: 0002_play_anonymous
Create Date: 2026-03-15
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003_playlists_ordering"
down_revision: Union[str, None] = "0002_play_anonymous"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_unique_on_columns(
    inspector: sa.Inspector,
    table_name: str,
    columns: set[str],
) -> bool:
    for constraint in inspector.get_unique_constraints(table_name):
        constrained = set(constraint.get("column_names") or [])
        if constrained == columns:
            return True
    return False


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())

    if "playlists" not in table_names:
        op.create_table(
            "playlists",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("is_public", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
        )
    else:
        playlist_columns = {column["name"] for column in inspector.get_columns("playlists")}
        if "updated_at" not in playlist_columns:
            op.add_column(
                "playlists",
                sa.Column(
                    "updated_at",
                    sa.DateTime(timezone=True),
                    nullable=False,
                    server_default=sa.text("now()"),
                ),
            )

    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())
    if "playlist_tracks" not in table_names:
        op.create_table(
            "playlist_tracks",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column(
                "playlist_id",
                sa.Integer(),
                sa.ForeignKey("playlists.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "track_id",
                sa.Integer(),
                sa.ForeignKey("tracks.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("position", sa.Integer(), nullable=False),
            sa.Column(
                "added_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.UniqueConstraint(
                "playlist_id",
                "position",
                name="uq_playlist_tracks_playlist_id_position",
            ),
        )
        return

    playlist_track_columns = {
        column["name"] for column in inspector.get_columns("playlist_tracks")
    }
    if "id" not in playlist_track_columns:
        op.add_column("playlist_tracks", sa.Column("id", sa.Integer(), nullable=True))
        op.execute("CREATE SEQUENCE IF NOT EXISTS playlist_tracks_id_seq")
        op.execute(
            "ALTER TABLE playlist_tracks ALTER COLUMN id "
            "SET DEFAULT nextval('playlist_tracks_id_seq')"
        )
        op.execute("UPDATE playlist_tracks SET id = nextval('playlist_tracks_id_seq') WHERE id IS NULL")
        op.alter_column("playlist_tracks", "id", nullable=False)

    inspector = sa.inspect(bind)
    pk = inspector.get_pk_constraint("playlist_tracks")
    pk_columns = pk.get("constrained_columns") or []
    if pk_columns != ["id"]:
        if pk.get("name"):
            op.drop_constraint(pk["name"], "playlist_tracks", type_="primary")
        op.create_primary_key("pk_playlist_tracks", "playlist_tracks", ["id"])

    inspector = sa.inspect(bind)
    if not _has_unique_on_columns(
        inspector,
        "playlist_tracks",
        {"playlist_id", "position"},
    ):
        op.execute(
            """
            WITH ranked AS (
                SELECT
                    id,
                    ROW_NUMBER() OVER (
                        PARTITION BY playlist_id
                        ORDER BY position ASC, track_id ASC, id ASC
                    ) - 1 AS new_position
                FROM playlist_tracks
            )
            UPDATE playlist_tracks AS pt
            SET position = ranked.new_position
            FROM ranked
            WHERE pt.id = ranked.id
            """
        )
        op.create_unique_constraint(
            "uq_playlist_tracks_playlist_id_position",
            "playlist_tracks",
            ["playlist_id", "position"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())

    if "playlist_tracks" in table_names:
        for constraint in inspector.get_unique_constraints("playlist_tracks"):
            columns = set(constraint.get("column_names") or [])
            name = constraint.get("name")
            if columns == {"playlist_id", "position"} and name:
                op.drop_constraint(name, "playlist_tracks", type_="unique")
                break

    inspector = sa.inspect(bind)
    if "playlists" in set(inspector.get_table_names()):
        playlist_columns = {column["name"] for column in inspector.get_columns("playlists")}
        if "updated_at" in playlist_columns:
            op.drop_column("playlists", "updated_at")
