# Copyright (C) 2024 RompMusic Contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""RompMusic Server - Main FastAPI application."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from rompmusic_server.database import init_db
from rompmusic_server.routers import auth, config, library, streaming, search, playlists, artwork, admin
from rompmusic_server.admin import views as admin_views


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    await init_db()
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
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
