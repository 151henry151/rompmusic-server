# Copyright (C) 2024 RompMusic Contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Client configuration API - returns admin-controlled settings policy."""

import json

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from rompmusic_server.auth import get_optional_user_id
from rompmusic_server.database import get_db
from rompmusic_server.models.server_config import DEFAULT_CLIENT_SETTINGS, ServerConfig

router = APIRouter(prefix="/config", tags=["config"])


@router.get("/client")
async def get_client_config(
    _user_id: int | None = Depends(get_optional_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Get client settings policy. Tells the app which settings to show and their defaults.
    When visible=false, the client hides the setting and uses the server default for all users.
    """
    result = await db.execute(
        select(ServerConfig).where(ServerConfig.key == "client_settings")
    )
    row = result.scalar_one_or_none()
    if row:
        try:
            parsed = json.loads(row.value)
            if isinstance(parsed, dict):
                return parsed if "client_settings" in parsed else {"client_settings": parsed}
        except json.JSONDecodeError:
            pass
    return {"client_settings": DEFAULT_CLIENT_SETTINGS}
