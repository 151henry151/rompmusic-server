# Copyright (C) 2024 RompMusic Contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""RompMusic Server - Main FastAPI application."""

import asyncio
import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from rompmusic_server.database import init_db
from rompmusic_server.routers import auth, config, library, streaming, search, playlists, artwork, admin
from rompmusic_server.admin import views as admin_views

logger = logging.getLogger(__name__)


def _get_cors_origins() -> list[str]:
    from rompmusic_server.config import settings
    raw = (settings.cors_origins or "*").strip()
    if raw == "*":
        return ["*"]
    return [o.strip() for o in raw.split(",") if o.strip()]


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    await init_db()
    from rompmusic_server.config import settings
    from rompmusic_server.database import async_session_maker
    from rompmusic_server.services.server_settings import get_server_settings, get_effective_library_config

    # Check Last.fm (env or DB checked at request time)
    if not settings.lastfm_api_key:
        logger.info(
            "LASTFM_API_KEY not set - set in env or Admin → Server Settings. "
            "Get a free key at https://last.fm/api/account/create"
        )
    app.state.scan_task = None
    app.state.scan_progress = {
        "processed": 0, "total": 0, "current_file": None,
        "artists": 0, "albums": 0, "tracks": 0, "done": False, "error": None,
    }

    async def scheduled_scan_loop():
        while True:
            async with async_session_maker() as db:
                s = await get_server_settings(db)
            env_scan = settings.auto_scan_interval_hours
            env_beets = settings.beets_auto_interval_hours
            env_run_beets = getattr(settings, "run_beets_after_scan", False)
            effective = get_effective_library_config(s, env_scan, env_beets, env_run_beets)
            interval_h = effective["auto_scan_interval_hours"]
            if interval_h <= 0:
                interval_h = 24.0  # check again later
            await asyncio.sleep(interval_h * 3600)
            if admin_views.start_background_scan(app):
                logger.info("Scheduled library scan started")

    asyncio.create_task(scheduled_scan_loop())

    async def beets_loop():
        import shutil
        beet = shutil.which("beet") or "beet"
        music_path = str(settings.music_path)
        while True:
            async with async_session_maker() as db:
                s = await get_server_settings(db)
            env_scan = settings.auto_scan_interval_hours
            env_beets = settings.beets_auto_interval_hours
            env_run_beets = getattr(settings, "run_beets_after_scan", False)
            effective = get_effective_library_config(s, env_scan, env_beets, env_run_beets)
            interval_h = effective["beets_auto_interval_hours"]
            if interval_h <= 0:
                interval_h = 24.0
            await asyncio.sleep(interval_h * 3600)
            try:
                proc = await asyncio.create_subprocess_exec(
                    beet, "fetch-art", "-y",
                    cwd=music_path,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.PIPE,
                )
                _, stderr = await proc.communicate()
                if proc.returncode == 0:
                    logger.info("Beets fetch-art completed")
                else:
                    logger.warning("Beets fetch-art exited %s: %s", proc.returncode, (stderr or b"").decode()[:200])
            except Exception as e:
                logger.warning("Beets fetch-art failed: %s", e)

    asyncio.create_task(beets_loop())
    yield
    # shutdown


app = FastAPI(
    title="RompMusic Server",
    description="Libre self-hosted music streaming API",
    version="0.1.0-beta.2",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log method, path, status, and duration for each request (no body or auth headers)."""
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000
    logger.info("%s %s %s %.1fms", request.method, request.url.path, response.status_code, duration_ms)
    # Set anonymous cookie for public server when dependency set request.state.anonymous_id_to_set
    if getattr(request.state, "anonymous_id_to_set", None):
        from rompmusic_server.auth import ANONYMOUS_COOKIE_MAX_AGE, ANONYMOUS_COOKIE_NAME
        response.set_cookie(
            ANONYMOUS_COOKIE_NAME,
            request.state.anonymous_id_to_set,
            max_age=ANONYMOUS_COOKIE_MAX_AGE,
            httponly=True,
            samesite="lax",
        )
    return response

# API v1
app.include_router(auth.router, prefix="/api/v1")
app.include_router(config.router, prefix="/api/v1")
app.include_router(library.router, prefix="/api/v1")
app.include_router(streaming.router, prefix="/api/v1")
app.include_router(search.router, prefix="/api/v1")
app.include_router(playlists.router, prefix="/api/v1")
app.include_router(artwork.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")
app.include_router(admin_views.router)


@app.get("/")
async def root():
    """Health check / API info."""
    return {
        "name": "RompMusic Server",
        "version": "0.1.0-beta.2",
        "api": "/api/v1",
        "docs": "/api/docs",
    }


@app.get("/api/v1/health")
async def health():
    """Health check for load balancers."""
    return {"status": "ok"}
