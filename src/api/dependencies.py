"""Shared FastAPI dependencies."""

from __future__ import annotations

import hmac

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader

from src.core.config import settings

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def require_api_key(key: str | None = Security(_api_key_header)) -> None:
    """Reject requests that don't carry a valid X-API-Key header.

    No-ops when ``API_KEY`` is not configured (local dev / CI).
    Uses constant-time comparison to prevent timing-based enumeration.
    """
    if not settings.api_key:
        return

    if key and hmac.compare_digest(key, settings.api_key):
        return

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing API key",
        headers={"WWW-Authenticate": "ApiKey"},
    )
