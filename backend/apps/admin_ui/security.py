"""Admin UI security helpers."""

from __future__ import annotations

import asyncio
import logging
import secrets
import time
from collections import deque
from typing import Any, Deque, Dict, MutableMapping, Optional, Tuple, cast

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from backend.core.settings import Settings, get_settings

logger = logging.getLogger(__name__)

_basic = HTTPBasic(auto_error=False)
_SESSION_FAILURE_KEY = "admin_auth_failures"

try:  # pragma: no cover - optional dependency
    import redis.asyncio as redis_async
except Exception:  # pragma: no cover - redis is optional
    redis_async = None  # type: ignore[assignment]


def _get_request_session(request: Request) -> MutableMapping[str, object]:
    """Return a mutable session mapping, falling back to an in-memory store."""

    if "session" in request.scope:
        session_obj = request.session
        if isinstance(session_obj, MutableMapping):
            return session_obj
        return cast(MutableMapping[str, object], session_obj)

    fallback: MutableMapping[str, object] | None = getattr(
        request.state, "_fallback_session", None
    )
    if fallback is None or not isinstance(fallback, MutableMapping):
        fallback = {}
        request.state._fallback_session = fallback  # type: ignore[attr-defined]
    return fallback


class _RateLimitStore:
    async def configure(self, max_attempts: int, window_seconds: int) -> None:
        raise NotImplementedError

    async def is_limited(self, key: str) -> Tuple[bool, Optional[int]]:
        raise NotImplementedError

    async def record_failure(self, key: str) -> None:
        raise NotImplementedError

    async def reset(self, key: str) -> None:
        raise NotImplementedError


class _InMemoryRateLimitStore(_RateLimitStore):
    def __init__(self) -> None:
        self._max_attempts = 1
        self._window_seconds = 60
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

    async def is_limited(self, key: str) -> Tuple[bool, Optional[int]]:
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


class _RedisRateLimitStore(_RateLimitStore):
    def __init__(self, url: str) -> None:
        if redis_async is None:  # pragma: no cover - optional dependency
            raise RuntimeError("redis.asyncio is not available")
        self._redis = redis_async.from_url(url)
        self._max_attempts = 1
        self._window_seconds = 60
        self._key_prefix = "admin-rate-limit:"

    async def configure(self, max_attempts: int, window_seconds: int) -> None:
        self._max_attempts = max_attempts
        self._window_seconds = window_seconds

    def _key(self, key: str) -> str:
        return f"{self._key_prefix}{key}"

    async def is_limited(self, key: str) -> Tuple[bool, Optional[int]]:
        redis_key = self._key(key)
        try:
            pipe = self._redis.pipeline()
            pipe.get(redis_key)
            pipe.ttl(redis_key)
            count_raw, ttl = await pipe.execute()
        except Exception as exc:  # pragma: no cover - redis failures
            logger.warning("Redis rate limit check failed: %s", exc)
            return False, None

        if count_raw is None:
            return False, None

        if isinstance(count_raw, bytes):
            try:
                count = int(count_raw.decode("utf-8"))
            except ValueError:
                count = 0
        else:
            try:
                count = int(count_raw)
            except (TypeError, ValueError):
                count = 0

        if count < self._max_attempts:
            return False, None

        if isinstance(ttl, int) and ttl > 0:
            retry_after = ttl
        else:
            retry_after = self._window_seconds
        return True, retry_after

    async def record_failure(self, key: str) -> None:
        redis_key = self._key(key)
        try:
            count = await self._redis.incr(redis_key)
            ttl = await self._redis.ttl(redis_key)
            if count == 1 or (isinstance(ttl, int) and ttl < 0):
                await self._redis.expire(redis_key, self._window_seconds)
        except Exception as exc:  # pragma: no cover - redis failures
            logger.warning("Redis rate limit update failed: %s", exc)

    async def reset(self, key: str) -> None:
        redis_key = self._key(key)
        try:
            await self._redis.delete(redis_key)
        except Exception as exc:  # pragma: no cover - redis failures
            logger.warning("Redis rate limit reset failed: %s", exc)


class _RateLimiter:
    """Rate limiter backed by a pluggable store."""

    def __init__(
        self,
        max_attempts: int,
        window_seconds: int,
        *,
        store: Optional[_RateLimitStore] = None,
    ) -> None:
        self._max_attempts = max_attempts
        self._window_seconds = window_seconds
        self._store = store or _InMemoryRateLimitStore()
        self._lock = asyncio.Lock()
        self._configured = False

    async def configure(self, max_attempts: int, window_seconds: int) -> None:
        async with self._lock:
            if (
                self._max_attempts != max_attempts
                or self._window_seconds != window_seconds
            ):
                self._max_attempts = max_attempts
                self._window_seconds = window_seconds
                self._configured = False
            await self._store.configure(self._max_attempts, self._window_seconds)
            self._configured = True

    async def _ensure_configured(self) -> None:
        if not self._configured:
            await self.configure(self._max_attempts, self._window_seconds)

    async def is_limited(self, key: str) -> Tuple[bool, Optional[int]]:
        await self._ensure_configured()
        return await self._store.is_limited(key)

    async def record_failure(self, key: str) -> None:
        await self._ensure_configured()
        await self._store.record_failure(key)

    async def reset(self, key: str) -> None:
        await self._ensure_configured()
        await self._store.reset(key)


_limiter: _RateLimiter | None = None
_limiter_config: Tuple[int, int, Optional[str]] | None = None


def _get_limiter(settings: Settings) -> _RateLimiter:
    global _limiter, _limiter_config
    config = (
        settings.admin_rate_limit_attempts,
        settings.admin_rate_limit_window_seconds,
        settings.redis_url or None,
    )
    if _limiter is None or _limiter_config != config:
        store: Optional[_RateLimitStore] = None
        if settings.redis_url:
            try:
                store = _RedisRateLimitStore(settings.redis_url)
                logger.info("Using Redis-backed rate limit store")
            except Exception as exc:  # pragma: no cover - optional dependency
                logger.warning("Falling back to in-memory rate limiter: %s", exc)
                store = None
        _limiter = _RateLimiter(
            settings.admin_rate_limit_attempts,
            settings.admin_rate_limit_window_seconds,
            store=store,
        )
        _limiter_config = config
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
    limiter = _get_limiter(settings)
    await limiter.configure(
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

    session = _get_request_session(request)
    failures, session_retry_after = _session_failures(
        session, window_seconds=settings.admin_rate_limit_window_seconds
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
            session,
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
            session,
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
    _reset_session_failures(session)
    logger.info("Admin user '%s' successfully authenticated from %s", username, client_id)


__all__ = ["require_admin"]

