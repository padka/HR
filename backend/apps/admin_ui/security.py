"""Admin UI security helpers."""

from __future__ import annotations

import base64
import logging
import os
import secrets
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Literal, Optional

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jwt import InvalidTokenError
from slowapi import Limiter, _rate_limit_exceeded_handler as _slowapi_rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import select
from starlette.requests import HTTPConnection
from starlette_wtf import csrf_token

from backend.core.audit import AuditContext, set_audit_context
from backend.core.db import async_session
from backend.core.settings import get_settings
from backend.domain.auth_account import AuthAccount
from backend.domain.models import Recruiter

logger = logging.getLogger(__name__)

# Replaced Basic auth with OAuth2 (Bearer token)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token", auto_error=False)
_LOCAL_ONLY_HOSTS = {"127.0.0.1", "::1", "localhost", "testclient"}
_TRUTHY = {"1", "true", "yes", "on"}
_CSRF_DEV_ALLOWLIST_ENV = "CSRF_DEV_ALLOWLIST"


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


async def _rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    response = _slowapi_rate_limit_exceeded_handler(request, exc)
    if hasattr(response, "__await__"):
        return await response
    return response


# ---- Principal helpers ------------------------------------------------------

PrincipalType = Literal["admin", "recruiter"]


@dataclass
class Principal:
    type: PrincipalType
    id: int


ADMIN_PRINCIPAL_ID = 0
LEGACY_ADMIN_PRINCIPAL_ID = -1
SESSION_KEY = "principal"
principal_ctx: ContextVar[Optional[Principal]] = ContextVar("principal_ctx", default=None)


def normalize_admin_principal_id(principal_id: int | None) -> int:
    if principal_id in {None, LEGACY_ADMIN_PRINCIPAL_ID}:
        return ADMIN_PRINCIPAL_ID
    return int(principal_id)


def admin_principal(principal_id: int | None = None) -> Principal:
    return Principal(type="admin", id=normalize_admin_principal_id(principal_id))


def _connection_client_host(connection: Request | HTTPConnection) -> str:
    return (
        connection.client.host.strip().lower()
        if connection and getattr(connection, "client", None) and connection.client.host
        else ""
    )


def _is_local_connection(connection: Request | HTTPConnection) -> bool:
    host = (connection.url.hostname or "").strip().lower() if connection and getattr(connection, "url", None) else ""
    client_host = _connection_client_host(connection)
    return host in _LOCAL_ONLY_HOSTS or client_host in _LOCAL_ONLY_HOSTS


def _csrf_dev_allowlist_hosts() -> set[str]:
    raw = os.getenv(_CSRF_DEV_ALLOWLIST_ENV, "")
    hosts = {
        item.strip().lower()
        for chunk in raw.split(",")
        for item in chunk.split()
        if item.strip()
    }
    return hosts | _LOCAL_ONLY_HOSTS


def _is_csrf_dev_bypass_allowed(connection: Request | HTTPConnection, settings) -> bool:
    if settings.environment not in {"development", "test"}:
        return False
    host = (connection.url.hostname or "").strip().lower() if connection and getattr(connection, "url", None) else ""
    return bool(host and host in _csrf_dev_allowlist_hosts())


def _extract_bearer_token(connection: Request | HTTPConnection) -> str:
    auth_header = connection.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        return auth_header.split(" ", 1)[1].strip()
    return ""


def _allow_legacy_basic(connection: Request | HTTPConnection, settings) -> bool:
    env_flag = os.getenv("ALLOW_LEGACY_BASIC", "false").lower() in _TRUTHY
    configured = bool(getattr(settings, "allow_legacy_basic", False))
    if not (env_flag or configured):
        return False
    if settings.environment not in {"development", "test"}:
        return False
    return _is_local_connection(connection)


def _allow_dev_autoadmin(connection: Request | HTTPConnection, settings) -> bool:
    env_flag = os.getenv("ALLOW_DEV_AUTOADMIN", "0").lower() in _TRUTHY
    if not env_flag:
        return False
    if settings.environment not in {"development", "test"}:
        return False
    return _is_local_connection(connection)


def _assign_principal(
    connection: Request | HTTPConnection,
    principal: Principal,
    *,
    username: str,
) -> Principal:
    principal_ctx.set(principal)
    connection.state.principal = principal
    set_audit_context(
        AuditContext(
            username=username,
            ip_address=_connection_client_host(connection) or None,
            user_agent=connection.headers.get("user-agent"),
        )
    )
    return principal


async def _resolve_session_principal(
    connection: Request | HTTPConnection,
) -> Optional[Principal]:
    principal_data = connection.session.get(SESSION_KEY) if hasattr(connection, "session") else None
    if not principal_data or not isinstance(principal_data, dict):
        return None

    p_type = principal_data.get("type")
    p_id = principal_data.get("id")
    if p_type == "admin" and isinstance(p_id, int):
        return _assign_principal(
            connection,
            admin_principal(p_id),
            username=f"admin:{p_id}",
        )

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
                session_username = connection.session.get("username") if hasattr(connection, "session") else None
                return _assign_principal(
                    connection,
                    Principal(type="recruiter", id=recruiter.id),
                    username=str(session_username or f"recruiter:{recruiter.id}"),
                )

    if hasattr(connection, "session"):
        connection.session.pop(SESSION_KEY, None)
        connection.session.pop("username", None)
    return None


async def _resolve_current_principal(
    connection: Request | HTTPConnection,
    *,
    token: str = "",
) -> Principal:
    """
    Resolve principal from:
    1. JWT Token (Bearer header)
    2. Session (Cookie)
    3. Legacy Basic Auth (local dev/test only)
    """
    settings = get_settings()

    token_provided = bool((token or "").strip())
    prefer_session_for_local_browser = (
        token_provided
        and _is_local_connection(connection)
        and hasattr(connection, "session")
        and bool(connection.session.get(SESSION_KEY))
    )

    if prefer_session_for_local_browser:
        session_principal = await _resolve_session_principal(connection)
        if session_principal is not None:
            return session_principal

    # 1. JWT Token Check
    if token:
        try:
            payload = jwt.decode(
                token,
                settings.session_secret,
                algorithms=["HS256"],
            )
            username = str(payload.get("sub") or "").strip()
            if username and secrets.compare_digest(username, settings.admin_username):
                return _assign_principal(
                    connection,
                    admin_principal(),
                    username=f"admin:{username}",
                )
            if username:
                async with async_session() as session:
                    account = await session.scalar(
                        select(AuthAccount).where(
                            AuthAccount.username == username,
                            AuthAccount.is_active.is_(True),
                        )
                    )
                    if account:
                        account_type = (account.principal_type or "").strip().lower()
                        if account_type == "admin":
                            return _assign_principal(
                                connection,
                                Principal(type="admin", id=int(account.principal_id)),
                                username=f"admin:{username}",
                            )
                        if account_type == "recruiter":
                            recruiter = await session.get(Recruiter, int(account.principal_id))
                            if recruiter and getattr(recruiter, "active", True):
                                now = datetime.now(timezone.utc)
                                last_seen = getattr(recruiter, "last_seen_at", None)
                                if last_seen and last_seen.tzinfo is None:
                                    last_seen = last_seen.replace(tzinfo=timezone.utc)
                                if last_seen is None or (now - last_seen) > timedelta(minutes=5):
                                    recruiter.last_seen_at = now
                                    await session.commit()
                                return _assign_principal(
                                    connection,
                                    Principal(type="recruiter", id=recruiter.id),
                                    username=f"recruiter:{recruiter.id}",
                                )
                if token_provided:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Invalid authentication token",
                        headers={"WWW-Authenticate": "Bearer"},
                    )
        except InvalidTokenError as exc:
            if token_provided:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid authentication token",
                    headers={"WWW-Authenticate": "Bearer"},
                ) from exc

    # 2. Session principal
    session_principal = await _resolve_session_principal(connection)
    if session_principal is not None:
        return session_principal

    # Legacy Basic admin fallback (strictly local dev/test only)
    legacy_user = settings.admin_username
    legacy_pass = settings.admin_password
    auth_header = connection.headers.get("authorization", "")
    if _allow_legacy_basic(connection, settings) and auth_header.lower().startswith("basic ") and legacy_user and legacy_pass:
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
            if hasattr(connection, "session"):
                connection.session[SESSION_KEY] = {"type": "admin", "id": ADMIN_PRINCIPAL_ID}
                connection.session["username"] = candidate_user
            return _assign_principal(
                connection,
                admin_principal(),
                username=f"admin:{candidate_user}",
            )

    # Development/test safety valve: allow anonymous admin locally only.
    if _allow_dev_autoadmin(connection, settings):
        return _assign_principal(
            connection,
            admin_principal(),
            username="anon-admin",
        )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_principal(
    request: Request,
    token: str = Depends(oauth2_scheme),
) -> Principal:
    return await _resolve_current_principal(request, token=token or "")


async def try_get_current_principal(
    connection: Request | HTTPConnection,
    *,
    token: Optional[str] = None,
) -> Optional[Principal]:
    try:
        resolved_token = token if token is not None else _extract_bearer_token(connection)
        return await _resolve_current_principal(connection, token=resolved_token or "")
    except AssertionError:
        return None
    except HTTPException as exc:
        if exc.status_code in {status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN}:
            return None
        raise


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
    "try_get_current_principal",
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
    "ADMIN_PRINCIPAL_ID",
    "LEGACY_ADMIN_PRINCIPAL_ID",
    "admin_principal",
    "normalize_admin_principal_id",
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
        if _is_csrf_dev_bypass_allowed(request, settings):
            logger.warning(
                "CSRF token check relaxed (local/allowlisted dev host)",
                extra={
                    "provided": bool(provided),
                    "expected": bool(expected),
                    "env": settings.environment,
                },
            )
            return

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF token missing or invalid",
        )
