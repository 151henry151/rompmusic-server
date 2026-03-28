# Copyright (C) 2024 RompMusic Contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Admin HTML routes. Requires DATABASE_URL (lifespan runs init_db)."""

import pytest
from httpx import ASGITransport, AsyncClient

from rompmusic_server.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def test_admin_login_page_returns_html(client: AsyncClient):
    """GET /server must render (Starlette 1.x TemplateResponse is request-first)."""
    r = await client.get("/server")
    assert r.status_code == 200
    assert "text/html" in r.headers.get("content-type", "")
    assert "RompMusic Admin" in r.text
