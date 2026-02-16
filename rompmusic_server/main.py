# Copyright (C) 2024 RompMusic Contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""RompMusic Server - Main FastAPI application."""

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
    if not settings.lastfm_api_key:
        logger.info(
            "LASTFM_API_KEY not set - artist images will show placeholders. "
            "Get a free key at https://last.fm/api/account/create"
        )
    yield
    # shutdown


app = FastAPI(
    title="RompMusic Server",
    description="Libre self-hosted music streaming API",
    version="0.1.0",
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
        "version": "0.1.0",
        "api": "/api/v1",
        "docs": "/api/docs",
    }


@app.get("/api/v1/health")
async def health():
    """Health check for load balancers."""
    return {"status": "ok"}
