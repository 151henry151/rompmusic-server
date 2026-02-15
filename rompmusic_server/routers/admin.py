# Copyright (C) 2024 RompMusic Contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Admin API - scan library, client config, etc. Requires admin user."""

import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from rompmusic_server.auth import get_current_user_id
from rompmusic_server.database import get_db
from rompmusic_server.models import User
from rompmusic_server.models.server_config import DEFAULT_CLIENT_SETTINGS, ServerConfig
from rompmusic_server.services.scanner import scan_library

router = APIRouter(prefix="/admin", tags=["admin"])


async def require_admin(
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> int:
    """Dependency: require admin user."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin required")
    return user_id


@router.post("/scan")
async def trigger_scan(
    _user_id: int = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Trigger library scan. Admin only."""
    counts = await scan_library(db)
    return {"status": "ok", "counts": counts}


class ClientSettingsPolicy(BaseModel):
    """Schema for a single client setting policy."""

    visible: bool
    default: bool | str
    allowed: list[str] | None = None  # For audio_format: ["original", "ogg"]


class ClientConfigUpdate(BaseModel):
    """Request body for updating client config."""

    client_settings: dict[str, dict]


@router.get("/client-config")
async def get_client_config_admin(
    _user_id: int = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get client settings policy. Admin only."""
    result = await db.execute(
        select(ServerConfig).where(ServerConfig.key == "client_settings")
    )
    row = result.scalar_one_or_none()
    if row:
        try:
            return json.loads(row.value)
        except json.JSONDecodeError:
            pass
    return {"client_settings": DEFAULT_CLIENT_SETTINGS}


@router.put("/client-config")
async def update_client_config(
    body: ClientConfigUpdate,
    _user_id: int = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Update client settings policy. Admin only."""
    payload = {"client_settings": body.client_settings}
    value_str = json.dumps(payload)
    result = await db.execute(
        select(ServerConfig).where(ServerConfig.key == "client_settings")
    )
    row = result.scalar_one_or_none()
    if row:
        row.value = value_str
    else:
        db.add(ServerConfig(key="client_settings", value=value_str))
    await db.flush()
    return payload
