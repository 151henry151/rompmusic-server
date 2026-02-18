# Copyright (C) 2024 RompMusic Contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Web admin panel routes."""

import asyncio
import json
import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from rompmusic_server.auth import create_access_token, get_current_user_id, verify_password
from rompmusic_server.database import async_session_maker, get_db
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


def _api_base() -> str:
    """Base URL for API - same origin as server."""
    return "/api/v1"


@router.get("/dashboard", response_class=HTMLResponse)
async def admin_dashboard(
    request: Request,
    user: User = Depends(require_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Admin dashboard with library stats."""
    from rompmusic_server.config import settings
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
            "api_base": _api_base(),
            "auto_scan_interval_hours": settings.auto_scan_interval_hours,
            "beets_auto_interval_hours": settings.beets_auto_interval_hours,
            "run_beets_after_scan": getattr(settings, "run_beets_after_scan", False),
        },
    )


@router.post("/scan", response_class=HTMLResponse)
async def admin_trigger_scan(
    request: Request,
    _user: User = Depends(require_admin_user),
):
    """Start library scan in background. Returns HTML partial. Use POST /server/scan/stream for progress."""
    started = start_background_scan(request.app)
    state = _get_scan_state(request.app)
    return templates.TemplateResponse(
        "partials/scan_result.html",
        {"request": request, "counts": state, "started": started},
    )


def _get_scan_state(app: FastAPI) -> dict:
    """Get or create app-state for background scan."""
    if not hasattr(app.state, "scan_progress"):
        app.state.scan_progress = {
            "processed": 0,
            "total": 0,
            "current_file": None,
            "artists": 0,
            "albums": 0,
            "tracks": 0,
            "done": False,
            "error": None,
        }
    if not hasattr(app.state, "scan_task"):
        app.state.scan_task = None
    return app.state.scan_progress


def get_scan_progress(app: FastAPI) -> dict:
    """Return current scan progress (read-only copy)."""
    return dict(_get_scan_state(app))


def start_background_scan(app: FastAPI) -> bool:
    """Start library scan in background if not already running. Returns True if started."""
    state = _get_scan_state(app)
    if app.state.scan_task is not None and not app.state.scan_task.done():
        return False

    state.update(
        processed=0, total=0, current_file=None, artists=0, albums=0, tracks=0, done=False, error=None
    )

    async def run_scan_background():
        async with async_session_maker() as session:
            try:
                def on_progress(processed, total, current_file, artists, albums, tracks):
                    state.update(
                        processed=processed,
                        total=total,
                        current_file=current_file,
                        artists=artists,
                        albums=albums,
                        tracks=tracks,
                        done=False,
                        error=None,
                    )

                await scan_library(session, on_progress=on_progress)
                await session.commit()
                state["done"] = True

                from rompmusic_server.config import settings
                from rompmusic_server.services.server_settings import get_server_settings, get_effective_library_config
                s = await get_server_settings(session)
                effective = get_effective_library_config(
                    s, settings.auto_scan_interval_hours, settings.beets_auto_interval_hours,
                    getattr(settings, "run_beets_after_scan", False),
                )
                if effective.get("run_beets_after_scan", False):
                    beet = shutil.which("beet") or "beet"
                    music_path = str(settings.music_path)
                    try:
                        proc = await asyncio.create_subprocess_exec(
                            beet, "fetch-art", "-y",
                            cwd=music_path,
                            stdout=asyncio.subprocess.DEVNULL,
                            stderr=asyncio.subprocess.PIPE,
                        )
                        await proc.communicate()
                    except Exception:
                        pass
            except Exception as e:
                state["done"] = True
                state["error"] = str(e)
            finally:
                app.state.scan_task = None

    app.state.scan_task = asyncio.create_task(run_scan_background())
    return True


@router.post("/scan/stream")
async def admin_trigger_scan_stream(
    request: Request,
    _user: User = Depends(require_admin_user),
):
    """Stream scan progress via Server-Sent Events. Scan runs in background with its own
    DB session so it continues even if the browser tab is closed."""

    start_background_scan(request.app)
    state = _get_scan_state(request.app)

    async def event_generator():
        last = None
        while True:
            current = dict(state)
            if current != last:
                last = current
                yield f"data: {json.dumps(current)}\n\n"
            if current.get("done"):
                break
            await asyncio.sleep(0.3)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
