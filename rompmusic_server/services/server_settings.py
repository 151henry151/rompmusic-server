# Copyright (C) 2024 RompMusic Contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Server settings (registration, library, API keys) from DB."""

import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from rompmusic_server.models.server_config import DEFAULT_SERVER_SETTINGS, ServerConfig


async def get_server_settings(db: AsyncSession) -> dict:
    """Return server_settings from DB or defaults."""
    result = await db.execute(
        select(ServerConfig).where(ServerConfig.key == "server_settings")
    )
    row = result.scalar_one_or_none()
    if row:
        try:
            out = json.loads(row.value)
            return {**DEFAULT_SERVER_SETTINGS, **out}
        except json.JSONDecodeError:
            pass
    return dict(DEFAULT_SERVER_SETTINGS)


async def get_api_keys(db: AsyncSession) -> dict:
    """Return api_keys from DB (e.g. lastfm, beets). Keys not set are absent."""
    result = await db.execute(
        select(ServerConfig).where(ServerConfig.key == "api_keys")
    )
    row = result.scalar_one_or_none()
    if row:
        try:
            return json.loads(row.value)
        except json.JSONDecodeError:
            pass
    return {}


def get_effective_library_config(server_settings: dict, env_auto_scan: float, env_beets_interval: float, env_run_beets_after_scan: bool) -> dict:
    """Merge DB server_settings with env for library; DB overrides env when key present."""
    return {
        "auto_scan_interval_hours": server_settings.get("auto_scan_interval_hours") if server_settings.get("auto_scan_interval_hours") is not None else env_auto_scan,
        "beets_auto_interval_hours": server_settings.get("beets_auto_interval_hours") if server_settings.get("beets_auto_interval_hours") is not None else env_beets_interval,
        "run_beets_after_scan": server_settings.get("run_beets_after_scan") if "run_beets_after_scan" in server_settings else env_run_beets_after_scan,
    }
