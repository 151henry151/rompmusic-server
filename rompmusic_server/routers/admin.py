# Copyright (C) 2024 RompMusic Contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Admin API - scan library, client config, etc. Requires admin user."""

import json

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from rompmusic_server.admin import views as admin_views
from rompmusic_server.auth import get_current_user_id
from rompmusic_server.database import get_db
from rompmusic_server.models import PasswordResetToken, User
from rompmusic_server.models.server_config import DEFAULT_CLIENT_SETTINGS, ServerConfig
from rompmusic_server.services.server_settings import (
    get_api_keys,
    get_effective_library_config,
    get_server_settings,
)
from rompmusic_server.services.email import send_email

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
    request: Request,
    _user_id: int = Depends(require_admin),
) -> dict:
    """Start library scan in background. Admin only. Poll GET /admin/scan/status for progress."""
    started = admin_views.start_background_scan(request.app)
    return {"status": "started" if started else "already_running"}


@router.get("/scan/status")
async def get_scan_status(
    request: Request,
    _user_id: int = Depends(require_admin),
) -> dict:
    """Return current scan progress. Admin only."""
    state = admin_views.get_scan_progress(request.app)
    return state


@router.get("/stats")
async def get_admin_stats(
    _user_id: int = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Usage statistics. Admin only."""
    from sqlalchemy import func
    from rompmusic_server.models import PlayHistory, User

    users_total = await db.scalar(select(func.count()).select_from(User)) or 0
    users_pending = await db.scalar(
        select(func.count()).select_from(User).where(User.is_active == False)
    ) or 0
    plays_total = await db.scalar(select(func.count()).select_from(PlayHistory)) or 0
    return {
        "users_total": users_total,
        "users_pending_approval": users_pending,
        "plays_total": plays_total,
    }


@router.get("/users")
async def list_users(
    _user_id: int = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """List all users. Admin only."""
    result = await db.execute(
        select(User).order_by(User.created_at.desc())
    )
    users = result.scalars().all()
    return [
        {
            "id": u.id,
            "username": u.username,
            "email": u.email,
            "is_active": u.is_active,
            "is_admin": u.is_admin,
            "created_at": u.created_at.isoformat() if u.created_at else None,
        }
        for u in users
    ]


@router.post("/users/{user_id}/approve")
async def approve_user(
    user_id: int,
    _admin_id: int = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Set user is_active=True (e.g. after registration when approval required). Admin only."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_active = True
    await db.flush()
    return {"id": user.id, "is_active": True}


@router.post("/users/{user_id}/send-password-reset")
async def send_password_reset_to_user(
    user_id: int,
    _admin_id: int = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Create a password reset token and email it to the user. Admin only."""
    import secrets
    from datetime import datetime, timezone, timedelta

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    code = "".join(secrets.choice("0123456789") for _ in range(6))
    await db.execute(delete(PasswordResetToken).where(PasswordResetToken.email == user.email))
    prt = PasswordResetToken(
        email=user.email,
        token=code,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    db.add(prt)
    await db.commit()
    await send_email(
        user.email,
        "Reset your RompMusic password",
        f"Your password reset code is: {code}\n\nEnter this code in the app along with your new password.\n\nThe code expires in 1 hour.",
    )
    return {"message": "Password reset email sent."}


@router.get("/server-config")
async def get_server_config(
    _user_id: int = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return server config: effective library (DB + env), server_settings, api_keys (masked). Admin only."""
    from rompmusic_server.config import settings
    server_settings = await get_server_settings(db)
    api_keys = await get_api_keys(db)
    env_scan = settings.auto_scan_interval_hours
    env_beets = settings.beets_auto_interval_hours
    env_run_beets = getattr(settings, "run_beets_after_scan", False)
    effective = get_effective_library_config(server_settings, env_scan, env_beets, env_run_beets)
    lastfm_key = api_keys.get("lastfm") or settings.lastfm_api_key
    return {
        "auto_scan_interval_hours": effective["auto_scan_interval_hours"],
        "beets_auto_interval_hours": effective["beets_auto_interval_hours"],
        "run_beets_after_scan": effective["run_beets_after_scan"],
        "lastfm_configured": bool(lastfm_key),
        "server_settings": server_settings,
        "api_keys": {
            "lastfm": "***" if (api_keys.get("lastfm") or settings.lastfm_api_key) else "",
            "beets": "***" if api_keys.get("beets") else "",
        },
    }


class ServerSettingsUpdate(BaseModel):
    """Request body for updating server settings."""

    registration_enabled: bool = True
    registration_requires_approval: bool = False
    public_server_enabled: bool = False
    auto_scan_interval_hours: float | None = None
    beets_auto_interval_hours: float | None = None
    run_beets_after_scan: bool | None = None
    api_keys: dict[str, str] | None = None


@router.put("/server-config")
async def update_server_config(
    body: ServerSettingsUpdate,
    _user_id: int = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Update server settings and optionally API keys. Admin only."""
    server_settings = await get_server_settings(db)
    updates = dict(server_settings) if server_settings else {}
    updates["registration_enabled"] = body.registration_enabled
    updates["registration_requires_approval"] = body.registration_requires_approval
    updates["public_server_enabled"] = body.public_server_enabled
    if body.auto_scan_interval_hours is not None:
        updates["auto_scan_interval_hours"] = body.auto_scan_interval_hours
    if body.beets_auto_interval_hours is not None:
        updates["beets_auto_interval_hours"] = body.beets_auto_interval_hours
    if body.run_beets_after_scan is not None:
        updates["run_beets_after_scan"] = body.run_beets_after_scan
    value_str = json.dumps(updates)
    result = await db.execute(
        select(ServerConfig).where(ServerConfig.key == "server_settings")
    )
    row = result.scalar_one_or_none()
    if row:
        row.value = value_str
    else:
        db.add(ServerConfig(key="server_settings", value=value_str))
    if body.api_keys is not None:
        current_keys = await get_api_keys(db)
        for key, val in body.api_keys.items():
            if val.strip() == "" or val == "***":
                current_keys.pop(key, None)
            else:
                current_keys[key] = val.strip()
        key_str = json.dumps(current_keys)
        r2 = await db.execute(select(ServerConfig).where(ServerConfig.key == "api_keys"))
        row2 = r2.scalar_one_or_none()
        if row2:
            row2.value = key_str
        else:
            db.add(ServerConfig(key="api_keys", value=key_str))
    await db.flush()
    server_settings = await get_server_settings(db)
    return {"server_settings": server_settings}


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
