# Copyright (C) 2024 RompMusic Contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Authentication API routes."""

import secrets
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from rompmusic_server.auth import create_access_token, get_current_user_id, hash_password, verify_password
from rompmusic_server.database import get_db
from rompmusic_server.models import PasswordResetToken, User, VerificationCode
from rompmusic_server.api.schemas import (
    Token,
    UserCreate,
    UserLogin,
    UserResponse,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    VerifyEmailRequest,
)
from rompmusic_server.services.email import send_email

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=Token)
async def login(
    data: UserLogin,
    db: AsyncSession = Depends(get_db),
) -> Token:
    """Authenticate and return JWT."""
    result = await db.execute(
        select(User).where(User.username == data.username, User.is_active == True)
    )
    user = result.scalar_one_or_none()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    token = create_access_token({"sub": str(user.id)})
    return Token(access_token=token)


@router.post("/register", response_model=UserResponse)
async def register(
    data: UserCreate,
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Create a new user account. User must verify email before logging in."""
    result = await db.execute(select(User).where(User.username == data.username))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered",
        )
    result = await db.execute(select(User).where(User.email == data.email))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )
    user = User(
        username=data.username,
        email=data.email,
        password_hash=hash_password(data.password),
        is_active=False,
    )
    db.add(user)
    await db.flush()
    code = "".join(secrets.choice("0123456789") for _ in range(6))
    vc = VerificationCode(
        user_id=user.id,
        code=code,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
    )
    db.add(vc)
    await db.commit()
    await db.refresh(user)
    await send_email(
        data.email,
        "Verify your RompMusic account",
        f"Your verification code is: {code}\n\nEnter this code in the app to complete registration.\n\nThe code expires in 24 hours.",
    )
    return UserResponse.model_validate(user)


@router.post("/verify-email")
async def verify_email(
    data: VerifyEmailRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Verify email with one-time code. Enables login."""
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid email or code")
    result = await db.execute(
        select(VerificationCode).where(
            VerificationCode.user_id == user.id,
            VerificationCode.code == data.code,
            VerificationCode.expires_at > datetime.now(timezone.utc),
        )
    )
    vc = result.scalar_one_or_none()
    if not vc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired code")
    user.is_active = True
    await db.execute(delete(VerificationCode).where(VerificationCode.user_id == user.id))
    await db.commit()
    return {"message": "Email verified. You can now sign in."}


@router.post("/forgot-password")
async def forgot_password(
    data: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Request password reset. Sends token to email."""
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()
    if user:
        code = "".join(secrets.choice("0123456789") for _ in range(6))
        await db.execute(delete(PasswordResetToken).where(PasswordResetToken.email == data.email))
        prt = PasswordResetToken(
            email=data.email,
            token=code,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        db.add(prt)
        await db.commit()
        await send_email(
            data.email,
            "Reset your RompMusic password",
            f"Your password reset code is: {code}\n\nEnter this code in the app along with your new password.\n\nThe code expires in 1 hour.",
        )
    return {"message": "If an account exists, you will receive a password reset link."}


@router.post("/reset-password")
async def reset_password(
    data: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Reset password with code from email."""
    result = await db.execute(
        select(PasswordResetToken).where(
            PasswordResetToken.email == data.email,
            PasswordResetToken.token == data.code,
            PasswordResetToken.expires_at > datetime.now(timezone.utc),
        )
    )
    prt = result.scalar_one_or_none()
    if not prt:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired code")
    result = await db.execute(select(User).where(User.email == prt.email))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid code")
    user.password_hash = hash_password(data.new_password)
    await db.execute(delete(PasswordResetToken).where(PasswordResetToken.id == prt.id))
    await db.commit()
    return {"message": "Password reset successfully."}


@router.get("/me", response_model=UserResponse)
async def get_me(
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Get current user profile."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return UserResponse.model_validate(user)
