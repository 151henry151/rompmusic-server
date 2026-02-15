# Copyright (C) 2024 RompMusic Contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Web admin panel routes."""

from pathlib import Path

from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from rompmusic_server.auth import create_access_token, verify_password
from rompmusic_server.database import get_db
from rompmusic_server.models import Album, Artist, Track, User
from rompmusic_server.services.scanner import scan_library

router = APIRouter(prefix="/server", tags=["admin-web"])

templates_dir = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))


async def require_admin_user(
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> User:
    from fastapi import HTTPException
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


@router.get("", response_class=HTMLResponse)
async def admin_login_page(request: Request):
    """Admin login page."""
    return templates.TemplateResponse("login.html", {"request": request})


@router.post("/login", response_class=RedirectResponse)
async def admin_login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    """Authenticate and set admin cookie, redirect to dashboard."""
    from fastapi import HTTPException
    result = await db.execute(
        select(User).where(User.username == username, User.is_active == True)
    )
    user = result.scalar_one_or_none()
    if not user or not verify_password(password, user.password_hash) or not user.is_admin:
        return RedirectResponse(url="/server?error=invalid", status_code=303)
    token = create_access_token({"sub": str(user.id)})
    response = RedirectResponse(url="/server/dashboard", status_code=303)
    response.set_cookie(key="admin_token", value=token, httponly=True, samesite="lax")
    return response


@router.get("/dashboard", response_class=HTMLResponse)
async def admin_dashboard(
    request: Request,
    user: User = Depends(require_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Admin dashboard with library stats."""
    artists_count = await db.scalar(select(func.count()).select_from(Artist)) or 0
    albums_count = await db.scalar(select(func.count()).select_from(Album)) or 0
    tracks_count = await db.scalar(select(func.count()).select_from(Track)) or 0
    users_count = await db.scalar(select(func.count()).select_from(User)) or 0

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "user": user,
            "artists_count": artists_count,
            "albums_count": albums_count,
            "tracks_count": tracks_count,
            "users_count": users_count,
        },
    )


@router.post("/scan", response_class=HTMLResponse)
async def admin_trigger_scan(
    request: Request,
    _user: User = Depends(require_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Trigger library scan. Returns HTML partial for HTMX."""
    counts = await scan_library(db)
    return templates.TemplateResponse(
        "partials/scan_result.html",
        {"request": request, "counts": counts},
    )
