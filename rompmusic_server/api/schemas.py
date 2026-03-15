# Copyright (C) 2024 RompMusic Contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Pydantic schemas for API request/response."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


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
    has_artwork: bool | None = None
    primary_album_id: int | None = None
    primary_album_title: str | None = None
    created_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class AlbumResponse(BaseModel):
    id: int
    title: str
    artist_id: int
    artist_name: str | None = None
    year: int | None = None
    artwork_path: str | None = None
    has_artwork: bool | None = None
    artwork_hash: str | None = None
    track_count: int = 0
    created_at: datetime | None = None

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
    year: int | None = None  # Album year, for sorting/decade grouping
    created_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


# Playlist
class PlaylistTrackOut(BaseModel):
    id: int
    title: str
    album_id: int
    artist_id: int
    artist: str
    album: str
    duration: float
    position: int


class PlaylistCreate(BaseModel):
    name: str
    description: str | None = None


class PlaylistUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class PlaylistSummary(BaseModel):
    id: int
    name: str
    description: str | None = None
    owner_id: int
    created_at: datetime
    updated_at: datetime
    track_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class PlaylistOut(PlaylistSummary):
    tracks: list[PlaylistTrackOut] = Field(default_factory=list)


class AddTrackRequest(BaseModel):
    track_id: int
    position: int | None = None


class ReorderRequest(BaseModel):
    track_ids: list[int]
