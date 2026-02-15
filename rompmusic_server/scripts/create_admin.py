#!/usr/bin/env python3
# Copyright (C) 2024 RompMusic Contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Create admin user. Run: python -m rompmusic_server.scripts.create_admin"""

import asyncio
import getpass
import sys

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from rompmusic_server.database import async_session_maker, init_db
from rompmusic_server.models import User
from rompmusic_server.auth import hash_password


async def main():
    await init_db()
    username = input("Admin username: ").strip()
    email = input("Admin email: ").strip()
    password = getpass.getpass("Password: ")
    if not username or not email or not password:
        print("All fields required")
        sys.exit(1)

    async with async_session_maker() as session:
        result = await session.execute(select(User).where(User.username == username))
        if result.scalar_one_or_none():
            print("User already exists")
            sys.exit(1)
        user = User(
            username=username,
            email=email,
            password_hash=hash_password(password),
            is_admin=True,
        )
        session.add(user)
        await session.commit()
        print("Admin user created.")


if __name__ == "__main__":
    asyncio.run(main())
