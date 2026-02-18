# Copyright (C) 2024 RompMusic Contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Public invite API - accept invitation via token from email link."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from rompmusic_server.auth import create_access_token, hash_password
from rompmusic_server.database import get_db
from rompmusic_server.models import Invitation, User
from rompmusic_server.api.schemas import Token

router = APIRouter(prefix="/invite", tags=["invite"])


async def get_valid_invitation(
    token: str,
    db: AsyncSession,
) -> Invitation:
    """Load invitation by token; raise if not found, used, or expired."""
    result = await db.execute(
        select(Invitation).where(
            Invitation.token == token,
            Invitation.used_at.is_(None),
            Invitation.expires_at > datetime.now(timezone.utc),
        )
    )
    inv = result.scalar_one_or_none()
    if not inv:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired invitation",
        )
    return inv


@router.get("/status")
async def invite_status(
    token: str = Query(..., description="Invitation token from email link"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get invitation status. Returns email and whether admin set username/password (invitee only needs to activate)."""
    inv = await get_valid_invitation(token, db)
    return {
        "email": inv.email,
        "has_credentials": inv.username is not None and inv.password_hash is not None,
    }


class InviteActivate(BaseModel):
    """Request to activate account when admin set username/password."""

    token: str


@router.post("/activate", response_model=Token)
async def invite_activate(
    body: InviteActivate,
    db: AsyncSession = Depends(get_db),
) -> Token:
    """Activate account from invitation (admin already set username and password). Returns JWT."""
    inv = await get_valid_invitation(body.token, db)
    if not inv.username or not inv.password_hash:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invitation requires choosing username and password; use /invite/complete",
        )
    existing = await db.execute(select(User).where(User.email == inv.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="User already exists")
    existing_u = await db.execute(select(User).where(User.username == inv.username))
    if existing_u.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Username already taken")

    user = User(
        username=inv.username,
        email=inv.email,
        password_hash=inv.password_hash,
        is_active=True,
    )
    db.add(user)
    await db.flush()
    inv.used_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(user)
    token = create_access_token({"sub": str(user.id)})
    return Token(access_token=token)


class InviteComplete(BaseModel):
    """Request to complete invitation by choosing username and password."""

    token: str
    username: str
    password: str


@router.post("/complete", response_model=Token)
async def invite_complete(
    body: InviteComplete,
    db: AsyncSession = Depends(get_db),
) -> Token:
    """Complete invitation by setting username and password. Returns JWT."""
    inv = await get_valid_invitation(body.token, db)
    if inv.username and inv.password_hash:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invitation already has credentials; use /invite/activate",
        )
    username = body.username.strip()
    if not username:
        raise HTTPException(status_code=400, detail="Username required")
    if len(username) > 64:
        raise HTTPException(status_code=400, detail="Username too long")
    if not body.password:
        raise HTTPException(status_code=400, detail="Password required")

    existing = await db.execute(select(User).where(User.email == inv.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="User already exists")
    existing_u = await db.execute(select(User).where(User.username == username))
    if existing_u.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Username already taken")

    user = User(
        username=username,
        email=inv.email,
        password_hash=hash_password(body.password),
        is_active=True,
    )
    db.add(user)
    await db.flush()
    inv.used_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(user)
    token = create_access_token({"sub": str(user.id)})
    return Token(access_token=token)
