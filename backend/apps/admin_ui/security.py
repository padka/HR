"""Admin UI security helpers."""

from __future__ import annotations

import logging
import secrets

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from backend.core.settings import get_settings

logger = logging.getLogger(__name__)

_basic = HTTPBasic(auto_error=False)


async def require_admin(credentials: HTTPBasicCredentials = Depends(_basic)) -> None:
    """Ensure the incoming request is authenticated via HTTP Basic."""

    settings = get_settings()
    username = settings.admin_username
    password = settings.admin_password

    if not username or not password:
        logger.error("Admin credentials are not configured; refusing request")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin credentials are not configured",
        )

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Basic"},
        )

    user_ok = secrets.compare_digest(credentials.username, username)
    pass_ok = secrets.compare_digest(credentials.password, password)
    if not (user_ok and pass_ok):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )


__all__ = ["require_admin"]

