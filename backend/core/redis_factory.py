"""Shared helpers for Redis client creation and logging."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RedisTarget:
    host: str
    port: int
    db: int
    password: Optional[str]


def parse_redis_target(redis_url: str, *, component: str) -> RedisTarget:
    parsed = urlparse(redis_url)
    host = parsed.hostname or "localhost"
    port = parsed.port or 6379
    try:
        db = int(parsed.path.strip("/") or "0") if parsed.path else 0
    except ValueError:
        db = 0
    masked_url = f"redis://{host}:{port}/{db}"
    logger.info("Redis %s target: %s", component, masked_url)
    return RedisTarget(
        host=host,
        port=port,
        db=db,
        password=parsed.password,
    )


def create_redis_client(redis_url: str, *, component: str, **kwargs):
    from redis.asyncio import Redis

    parse_redis_target(redis_url, component=component)
    return Redis.from_url(redis_url, **kwargs)


__all__ = ["RedisTarget", "parse_redis_target", "create_redis_client"]
