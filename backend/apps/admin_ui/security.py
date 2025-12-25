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


def get_client_ip(request: Request) -> str:
    """
    Extract client IP from request, supporting X-Forwarded-For when enabled.

    This function respects TRUST_PROXY_HEADERS setting:
    - When enabled (behind reverse proxy): uses X-Forwarded-For header
    - When disabled (direct connection): uses request.client.host

    Always returns a valid IP address string for rate limiting.
    """
    settings = get_settings()

    if settings.trust_proxy_headers:
        # Check X-Forwarded-For header (set by reverse proxies)
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            # X-Forwarded-For can contain multiple IPs: "client, proxy1, proxy2"
            # Use the leftmost (original client) IP
            client_ip = forwarded_for.split(",")[0].strip()
            if client_ip:
                return client_ip

    # Fallback to direct client IP
    return request.client.host if request and request.client else "unknown"


def _build_limiter() -> Limiter:
    """
    Create rate limiter with Redis storage in production.

    Storage backend selection:
    - Test environment: Disabled entirely (enabled=False)
    - Production with Redis: Redis storage at RATE_LIMIT_REDIS_URL (DB 1 by default)
    - Development/Redis unavailable: In-memory storage (fallback)

    Redis storage provides:
    - Multi-worker consistency (shared rate limits across all app instances)
    - Persistence across restarts
    - Distributed rate limiting

    In-memory storage limitations:
    - Per-worker limits (not global in multi-worker deployments)
    - Lost on restart
    - Not suitable for production
    """
    env = (os.getenv("ENVIRONMENT") or "development").strip().lower()

    # Test environment: disable rate limiting entirely
    if env == "test":
        return Limiter(
            key_func=get_admin_identifier,
            default_limits=[],
            enabled=False,
        )

    settings = get_settings()
    storage_uri = None

    # Production/staging: use Redis storage if enabled and URL available
    if settings.rate_limit_enabled and settings.rate_limit_redis_url:
        storage_uri = settings.rate_limit_redis_url
        logger.info(
            "Rate limiter using Redis storage",
            extra={
                "storage_uri": storage_uri.split("@")[-1] if "@" in storage_uri else storage_uri,
                "trust_proxy_headers": settings.trust_proxy_headers,
            }
        )
    else:
        # Fallback to in-memory storage
        logger.warning(
            "Rate limiter using in-memory storage (not recommended for production). "
            "Set RATE_LIMIT_ENABLED=true and RATE_LIMIT_REDIS_URL to enable Redis storage."
        )

    return Limiter(
        key_func=get_admin_identifier,
        default_limits=[],
        enabled=settings.rate_limit_enabled,
        storage_uri=storage_uri,
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
    "get_client_ip",
    "require_csrf_token",
]


async def require_csrf_token(request: Request) -> None:
    """Validate CSRF token for state-changing API calls."""
    state = getattr(request, "state", None)
    if state is not None and not getattr(state, "csrf_config", None):
        # Ensure CSRF config is present even if middleware didn't set it
        settings = get_settings()
        request.scope.setdefault("session", {})
        state.csrf_config = {
            "csrf_secret": settings.session_secret,
            "csrf_field_name": "csrf_token",
        }

    expected = csrf_token(request)
    settings = get_settings()

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

    tokens_match = expected and provided and secrets.compare_digest(str(provided), str(expected))
    if not tokens_match:
        host = (request.url.hostname or "").lower()
        client_host = request.client.host if request and request.client else ""
        is_local = host in {"localhost", "127.0.0.1"} or client_host in {"127.0.0.1", "::1", "localhost"}
        is_http = request.url.scheme == "http"

        if settings.environment != "production" or is_local or is_http:
            logger.warning(
                "CSRF token check relaxed (dev/local/http)",
                extra={
                    "provided": bool(provided),
                    "expected": bool(expected),
                    "host": host,
                    "client_host": client_host,
                    "env": settings.environment,
                    "scheme": request.url.scheme,
                },
            )
            return

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF token missing or invalid",
        )
