"""Admin UI security helpers."""

from __future__ import annotations

import base64
import logging
import os
import secrets
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from backend.core.audit import AuditContext, set_audit_context
from starlette_wtf import csrf_token
from backend.core.settings import get_settings

logger = logging.getLogger(__name__)

_basic = HTTPBasic(auto_error=False)


def get_admin_identifier(request: Request) -> str:
    """Return rate-limit key preferring admin username over IP."""
    auth_header = request.headers.get("authorization", "")
    if auth_header.lower().startswith("basic "):
        encoded = auth_header.split(" ", 1)[1].strip()
        try:
            decoded = base64.b64decode(encoded).decode()
            username = decoded.split(":", 1)[0]
            if username:
                return f"admin:{username.lower()}"
        except Exception:
            pass
    client_ip = request.client.host if request and request.client else "unknown"
    return f"ip:{client_ip}"


def _build_limiter() -> Limiter:
    """Create rate limiter with test-friendly defaults."""
    env = (os.getenv("ENVIRONMENT") or "development").strip().lower()
    return Limiter(
        key_func=get_admin_identifier,
        default_limits=[],
        enabled=env != "test",
    )


limiter = _build_limiter()


@limiter.limit("60/minute", key_func=get_remote_address)
@limiter.limit("20/minute")
async def require_admin(
    request: Request, credentials: HTTPBasicCredentials = Depends(_basic)
) -> None:
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
        logger.warning(
            "Missing admin credentials",
            extra={"remote_ip": request.client.host if request and request.client else None},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Basic"},
        )

    user_ok = secrets.compare_digest(credentials.username, username)
    pass_ok = secrets.compare_digest(credentials.password, password)
    if not (user_ok and pass_ok):
        logger.warning(
            "Invalid admin credentials",
            extra={
                "remote_ip": request.client.host if request and request.client else None,
                "username": credentials.username,
            },
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    request.state.admin_username = credentials.username
    set_audit_context(
        AuditContext(
            username=credentials.username,
            ip_address=request.client.host if request and request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
    )


__all__ = [
    "require_admin",
    "limiter",
    "RateLimitExceeded",
    "_rate_limit_exceeded_handler",
    "get_admin_identifier",
    "require_csrf_token",
]


async def require_csrf_token(request: Request) -> None:
    """Validate CSRF token for state-changing API calls."""
    expected = csrf_token(request)

    # Check headers first (for AJAX/API calls)
    provided = (
        request.headers.get("x-csrf-token")
        or request.headers.get("x-csrftoken")
        or request.headers.get("x-xsrf-token")
    )

    # If not in headers, check form data (for traditional form submissions)
    if not provided:
        form = await request.form()
        provided = form.get("csrf_token")

    if not expected or not provided or not secrets.compare_digest(str(provided), str(expected)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF token missing or invalid",
        )
