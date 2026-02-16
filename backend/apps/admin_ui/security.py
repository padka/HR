"""Admin UI security helpers."""

from __future__ import annotations

import logging
import base64
from datetime import datetime, timezone, timedelta
import os
import secrets
from dataclasses import dataclass
from typing import Optional, Literal
from contextvars import ContextVar

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from jose import JWTError, jwt

from backend.core.audit import AuditContext, set_audit_context
from backend.core.db import async_session
from backend.core.auth import verify_password
from backend.domain.auth_account import AuthAccount
from backend.domain.models import Recruiter
from starlette_wtf import csrf_token
from backend.core.settings import get_settings

logger = logging.getLogger(__name__)

# Replaced Basic auth with OAuth2 (Bearer token)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token", auto_error=False)


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


def get_principal_identifier(request: Request) -> str:
    """Return rate-limit key using resolved principal when available.

    FastAPI resolves dependencies (and sets request.state.principal) before
    entering slowapi's wrapper, so we can reliably rate-limit per user rather
    than per shared IP/NAT.
    """
    try:
        principal = getattr(getattr(request, "state", None), "principal", None)
        p_type = getattr(principal, "type", None)
        p_id = getattr(principal, "id", None)
        if p_type and isinstance(p_id, int):
            return f"{p_type}:{p_id}"
    except Exception:
        pass
    return get_admin_identifier(request)


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
            key_style="endpoint",
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
        key_style="endpoint",
    )


limiter = _build_limiter()


# ---- Principal helpers ------------------------------------------------------

PrincipalType = Literal["admin", "recruiter"]


@dataclass
class Principal:
    type: PrincipalType
    id: int


SESSION_KEY = "principal"
principal_ctx: ContextVar[Optional[Principal]] = ContextVar("principal_ctx", default=None)
def _allow_legacy_basic() -> bool:
    env_flag = os.getenv("ALLOW_LEGACY_BASIC", "false").lower() in {"1", "true", "yes"}
    settings = get_settings()
    return bool(env_flag or getattr(settings, "allow_legacy_basic", False))


@limiter.limit("60/minute", key_func=get_client_ip)
async def get_current_principal(
    request: Request, 
    token: str = Depends(oauth2_scheme),
) -> Principal:
    """
    Resolve principal from:
    1. JWT Token (Bearer header)
    2. Session (Cookie)
    3. Legacy Basic Auth (if enabled)
    """
    settings = get_settings()

    # 1. JWT Token Check
    if token:
        try:
            payload = jwt.decode(
                token, 
                settings.session_secret, 
                algorithms=["HS256"]
            )
            username: str = payload.get("sub")
            if username:
                # Validate admin username from token
                # In a real DB-backed system, we'd fetch the user here.
                # For this simple admin setup:
                if secrets.compare_digest(username, settings.admin_username):
                    principal = Principal(type="admin", id=-1)
                    principal_ctx.set(principal)
                    request.state.principal = principal
                    set_audit_context(
                        AuditContext(
                            username=f"admin:{username}",
                            ip_address=request.client.host if request and request.client else None,
                            user_agent=request.headers.get("user-agent"),
                        )
                    )
                    return principal
        except JWTError:
            # Invalid token, proceed to other methods or fail if only token expected
            pass

    # 2. Session principal
    principal_data = request.session.get(SESSION_KEY) if hasattr(request, "session") else None
    if principal_data and isinstance(principal_data, dict):
        p_type = principal_data.get("type")
        p_id = principal_data.get("id")
        if p_type == "admin" and isinstance(p_id, int):
            principal = Principal(type="admin", id=p_id)
            principal_ctx.set(principal)
            request.state.principal = principal
            set_audit_context(
                AuditContext(
                    username=f"admin:{p_id}",
                    ip_address=request.client.host if request and request.client else None,
                    user_agent=request.headers.get("user-agent"),
                )
            )
            return principal
        if p_type == "recruiter" and isinstance(p_id, int):
            async with async_session() as session:
                recruiter = await session.get(Recruiter, p_id)
                if recruiter and getattr(recruiter, "active", True):
                    now = datetime.now(timezone.utc)
                    last_seen = getattr(recruiter, "last_seen_at", None)
                    if last_seen and last_seen.tzinfo is None:
                        last_seen = last_seen.replace(tzinfo=timezone.utc)
                    if last_seen is None or (now - last_seen) > timedelta(minutes=5):
                        recruiter.last_seen_at = now
                        await session.commit()
                    principal = Principal(type="recruiter", id=recruiter.id)
                    principal_ctx.set(principal)
                    request.state.principal = principal
                    set_audit_context(
                        AuditContext(
                            username=f"recruiter:{recruiter.id}",
                            ip_address=request.client.host if request and request.client else None,
                            user_agent=request.headers.get("user-agent"),
                        )
                    )
                    return principal
            # stale session -> clear
            request.session.pop(SESSION_KEY, None)

    # Legacy Basic admin fallback
    settings = get_settings()
    legacy_user = settings.admin_username
    legacy_pass = settings.admin_password
    auth_header = request.headers.get("authorization", "")
    if _allow_legacy_basic() and auth_header.lower().startswith("basic ") and legacy_user and legacy_pass:
        # Important: don't use FastAPI's HTTPBasic dependency here.
        # Even with auto_error=False, having HTTPBasic in the dependency graph can
        # cause some servers to advertise "WWW-Authenticate: Basic" on 401, which
        # triggers the browser's native Basic Auth modal and breaks UX.
        encoded = auth_header.split(" ", 1)[1].strip()
        try:
            decoded = base64.b64decode(encoded).decode("utf-8")
            candidate_user, candidate_pass = decoded.split(":", 1)
        except Exception:
            candidate_user, candidate_pass = "", ""

        user_ok = secrets.compare_digest(candidate_user, legacy_user)
        pass_ok = secrets.compare_digest(candidate_pass, legacy_pass)
        if user_ok and pass_ok:
            # Persist into session for subsequent requests
            if hasattr(request, "session"):
                request.session[SESSION_KEY] = {"type": "admin", "id": -1}
            principal = Principal(type="admin", id=-1)
            principal_ctx.set(principal)
            request.state.principal = principal
            set_audit_context(
                AuditContext(
                    username=f"admin:{candidate_user}",
                    ip_address=request.client.host if request and request.client else None,
                    user_agent=request.headers.get("user-agent"),
                )
            )
            return principal

    # Development/test safety valve: allow anonymous admin when not in production.
    # Disabled by default; set ALLOW_DEV_AUTOADMIN=1 to skip login locally.
    allow_dev_autoadmin = os.getenv("ALLOW_DEV_AUTOADMIN", "0").lower() in {"1", "true", "yes"}
    if settings.environment != "production" and allow_dev_autoadmin:
        principal = Principal(type="admin", id=-1)
        principal_ctx.set(principal)
        request.state.principal = principal
        set_audit_context(
            AuditContext(
                username="anon-admin",
                ip_address=request.client.host if request and request.client else None,
                user_agent=request.headers.get("user-agent"),
            )
        )
        return principal

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def require_principal(principal: Principal = Depends(get_current_principal)) -> Principal:
    return principal


async def require_admin(principal: Principal = Depends(get_current_principal)) -> Principal:
    if principal.type != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
    return principal


__all__ = [
    "require_admin",
    "require_principal",
    "get_current_principal",
    "principal_ctx",
    "limiter",
    "RateLimitExceeded",
    "_rate_limit_exceeded_handler",
    "get_admin_identifier",
    "get_principal_identifier",
    "get_client_ip",
    "require_csrf_token",
    "Principal",
    "PrincipalType",
    "SESSION_KEY",
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
