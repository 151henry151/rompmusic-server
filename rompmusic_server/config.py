# Copyright (C) 2024 RompMusic Contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Configuration for RompMusic Server."""

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database
    database_url: str = "postgresql+asyncpg://rompmusic:rompmusic@localhost:5432/rompmusic"

    # Redis
    redis_url: str | None = "redis://localhost:6379/0"

    # JWT
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 10080  # 7 days

    # Music library
    music_path: Path = Path("/music")

    # Server
    host: str = "0.0.0.0"
    port: int = 8080
    base_url: str = "http://localhost:8080"

    # FFmpeg
    ffmpeg_path: str = "ffmpeg"

    # Transcoding bitrates (kbps)
    transcode_bitrates: list[int] = [320, 128, 64]

    # Email (for password reset, verification)
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_from: str = "noreply@rompmusic.local"
    app_base_url: str = "http://localhost:8080"

    # Recommendations: Last.fm API (optional; free key at last.fm/api/account/create)
    lastfm_api_key: str | None = None


settings = Settings()
