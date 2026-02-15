# Copyright (C) 2024 RompMusic Contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Pydantic schemas for API request/response."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr


# Auth
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str


class UserLogin(BaseModel):
    username: str
    password: str


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    email: str
    code: str
    new_password: str


class VerifyEmailRequest(BaseModel):
    email: str
    code: str


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    is_admin: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Library
class ArtistResponse(BaseModel):
    id: int
    name: str
    artwork_path: str | None = None

    model_config = ConfigDict(from_attributes=True)


class AlbumResponse(BaseModel):
    id: int
    title: str
    artist_id: int
    artist_name: str | None = None
    year: int | None = None
    artwork_path: str | None = None
    track_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class TrackResponse(BaseModel):
    id: int
    title: str
    album_id: int
    artist_id: int
    album_title: str | None = None
    artist_name: str | None = None
    track_number: int
    disc_number: int
    duration: float
    bitrate: int | None = None
    format: str | None = None

    model_config = ConfigDict(from_attributes=True)


# Playlist
class PlaylistCreate(BaseModel):
    name: str
    description: str | None = None
    is_public: bool = False


class PlaylistUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    is_public: bool | None = None


class PlaylistResponse(BaseModel):
    id: int
    name: str
    description: str | None = None
    is_public: bool
    created_at: datetime
    track_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class PlaylistTrackAdd(BaseModel):
    track_id: int
    position: int | None = None
