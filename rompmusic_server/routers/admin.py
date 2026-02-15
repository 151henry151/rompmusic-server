# Copyright (C) 2024 RompMusic Contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Admin API - scan library, etc. Requires admin user."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from rompmusic_server.auth import get_current_user_id
from rompmusic_server.database import get_db
from rompmusic_server.models import User
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
