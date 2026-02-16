# Copyright (C) 2024 RompMusic Contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""In-memory rate limiting for auth endpoints (brute-force protection)."""

import time
from collections import defaultdict
from fastapi import Request

# (client_key, endpoint) -> list of request timestamps in window
_buckets: defaultdict[tuple[str, str], list[float]] = defaultdict(list)
# Window seconds; max requests per window per endpoint
WINDOW = 60
LIMITS: dict[str, int] = {
    "/api/v1/auth/login": 10,
    "/api/v1/auth/register": 5,
    "/api/v1/auth/forgot-password": 5,
    "/api/v1/auth/verify-email": 10,
    "/api/v1/auth/reset-password": 10,
}


def _client_key(request: Request) -> str:
    """Prefer X-Forwarded-For when behind a proxy."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host or "unknown"
    return "unknown"


def _clean_old(bucket: list[float], now: float) -> None:
    cutoff = now - WINDOW
    while bucket and bucket[0] < cutoff:
        bucket.pop(0)


def check_rate_limit(request: Request, path: str) -> None:
    """
    Raise 429 if the client has exceeded the limit for this path.
    Call this at the start of the endpoint (or via a dependency).
    """
    now = time.monotonic()
    key = (_client_key(request), path)
    bucket = _buckets[key]
    _clean_old(bucket, now)
    limit = LIMITS.get(path)
    if limit is None:
        return
    if len(bucket) >= limit:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=429,
            detail="Too many requests. Please try again later.",
        )
    bucket.append(now)


async def rate_limit_auth_dep(request: Request) -> None:
    """FastAPI dependency: rate limit auth endpoints. Add Depends(rate_limit_auth_dep) to routes."""
    path = request.url.path.rstrip("/")
    if path in LIMITS:
        check_rate_limit(request, path)
