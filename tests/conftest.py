# Copyright (C) 2024 RompMusic Contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Pytest fixtures. Tests require DATABASE_URL (e.g. postgresql+asyncpg) to be set."""

import pytest


@pytest.fixture
def anyio_backend():
    return "asyncio"
