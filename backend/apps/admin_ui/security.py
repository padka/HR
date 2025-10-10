"""Admin UI security helpers."""

from __future__ import annotations

import asyncio
import logging
import secrets
import time
from collections import deque
from typing import Deque, Dict, MutableMapping, Tuple

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from backend.core.settings import get_settings

logger = logging.getLogger(__name__)

_basic = HTTPBasic(auto_error=False)
_SESSION_FAILURE_KEY = "admin_auth_failures"


class _RateLimiter:
    """Simple in-memory rate limiter keyed by a requester identifier."""

    def __init__(self, max_attempts: int, window_seconds: int) -> None:
        self._max_attempts = max_attempts
        self._window_seconds = window_seconds
        self._buckets: Dict[str, Deque[float]] = {}
        self._lock = asyncio.Lock()

    async def configure(self, max_attempts: int, window_seconds: int) -> None:
        async with self._lock:
            if (
                self._max_attempts != max_attempts
                or self._window_seconds != window_seconds
            ):
                self._max_attempts = max_attempts
                self._window_seconds = window_seconds
                self._buckets.clear()

    async def is_limited(self, key: str) -> Tuple[bool, int | None]:
        now = time.monotonic()
        async with self._lock:
            bucket = self._buckets.get(key)
            if not bucket:
                return False, None
            self._prune(bucket, now)
            if len(bucket) < self._max_attempts:
                return False, None
            retry_after = max(1, int(self._window_seconds - (now - bucket[0])))
            return True, retry_after

    async def record_failure(self, key: str) -> None:
        now = time.monotonic()
        async with self._lock:
            bucket = self._buckets.setdefault(key, deque())
            self._prune(bucket, now)
            bucket.append(now)

    async def reset(self, key: str) -> None:
        async with self._lock:
            self._buckets.pop(key, None)

    def _prune(self, bucket: Deque[float], now: float) -> None:
        window = self._window_seconds
        while bucket and now - bucket[0] > window:
            bucket.popleft()


_limiter: _RateLimiter | None = None
_limiter_config: Tuple[int, int] | None = None


def _get_limiter(max_attempts: int, window_seconds: int) -> _RateLimiter:
    global _limiter, _limiter_config
    config = (max_attempts, window_seconds)
    if _limiter is None or _limiter_config != config:
        _limiter = _RateLimiter(max_attempts, window_seconds)
        _limiter_config = config
        return _limiter

    return _limiter


def _client_identifier(request: Request) -> str:
    client = request.client
    return client.host if client else "unknown"


def _session_failures(
    session: MutableMapping[str, object],
    *,
    window_seconds: int,
) -> Tuple[int, float | None]:
    now = time.time()
    raw = session.get(_SESSION_FAILURE_KEY)
    if not isinstance(raw, list):
        session[_SESSION_FAILURE_KEY] = []
        return 0, None
    valid = [timestamp for timestamp in raw if isinstance(timestamp, (int, float))]
    filtered = [ts for ts in valid if now - ts < window_seconds]
    session[_SESSION_FAILURE_KEY] = filtered
    if not filtered:
        return 0, None
    retry_after = max(0.0, window_seconds - (now - filtered[0]))
    return len(filtered), retry_after


def _record_session_failure(
    session: MutableMapping[str, object],
    *,
    timestamp: float,
    window_seconds: int,
) -> None:
    _session_failures(session, window_seconds=window_seconds)
    entries = session.get(_SESSION_FAILURE_KEY, [])
    if isinstance(entries, list):
        entries.append(timestamp)
        session[_SESSION_FAILURE_KEY] = entries
    else:
        session[_SESSION_FAILURE_KEY] = [timestamp]


def _reset_session_failures(session: MutableMapping[str, object]) -> None:
    session.pop(_SESSION_FAILURE_KEY, None)


async def require_admin(
    request: Request, credentials: HTTPBasicCredentials = Depends(_basic)
) -> None:
    """Ensure the incoming request is authenticated via HTTP Basic."""

    settings = get_settings()
    limiter = _get_limiter(
        settings.admin_rate_limit_attempts, settings.admin_rate_limit_window_seconds
    )
    client_id = _client_identifier(request)

    limited, retry_after = await limiter.is_limited(client_id)
    if limited:
        logger.warning("Admin auth rate limit triggered for %s", client_id)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many authentication attempts",
            headers={"Retry-After": str(retry_after or 0)},
        )

    failures, session_retry_after = _session_failures(
        request.session, window_seconds=settings.admin_rate_limit_window_seconds
    )
    if failures >= settings.admin_rate_limit_attempts:
        retry_after_seconds = int(session_retry_after or 0)
        logger.warning(
            "Session rate limit triggered for %s after %s failures",
            client_id,
            failures,
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many authentication attempts",
            headers={"Retry-After": str(retry_after_seconds)},
        )

    username = settings.admin_username
    password = settings.admin_password

    if not username or not password:
        logger.error("Admin credentials are not configured; refusing request")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin credentials are not configured",
        )

    if credentials is None:
        logger.info("Missing credentials for admin endpoint from %s", client_id)
        now = time.time()
        await limiter.record_failure(client_id)
        _record_session_failure(
            request.session,
            timestamp=now,
            window_seconds=settings.admin_rate_limit_window_seconds,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Basic"},
        )

    user_ok = secrets.compare_digest(credentials.username, username)
    pass_ok = secrets.compare_digest(credentials.password, password)
    if not (user_ok and pass_ok):
        now = time.time()
        await limiter.record_failure(client_id)
        _record_session_failure(
            request.session,
            timestamp=now,
            window_seconds=settings.admin_rate_limit_window_seconds,
        )
        logger.warning(
            "Invalid admin credentials for user '%s' from %s",
            credentials.username,
            client_id,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )

    await limiter.reset(client_id)
    _reset_session_failures(request.session)
    logger.info("Admin user '%s' successfully authenticated from %s", username, client_id)


__all__ = ["require_admin"]

