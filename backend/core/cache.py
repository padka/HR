"""Cache infrastructure for performance optimization.

This module provides Redis-based caching with:
- Generic cache operations
- TTL management
- Invalidation patterns
- Async support
"""

from __future__ import annotations

import json
import logging
from datetime import timedelta
from typing import Any, Callable, Optional, TypeVar, cast

from redis.asyncio import Redis, ConnectionPool
from redis.exceptions import RedisError

from backend.core.result import DatabaseError, Result, failure, success

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CacheConfig:
    """Redis cache configuration."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: Optional[str] = None,
        max_connections: int = 50,
        socket_timeout: float = 5.0,
        socket_connect_timeout: float = 5.0,
        decode_responses: bool = True,
    ):
        self.host = host
        self.port = port
        self.db = db
        self.password = password
        self.max_connections = max_connections
        self.socket_timeout = socket_timeout
        self.socket_connect_timeout = socket_connect_timeout
        self.decode_responses = decode_responses


class CacheClient:
    """
    Redis cache client with async support.

    Features:
    - Type-safe operations
    - Result pattern integration
    - TTL management
    - Pattern-based invalidation
    - JSON serialization
    """

    def __init__(self, config: CacheConfig):
        self.config = config
        self._pool: Optional[ConnectionPool] = None
        self._client: Optional[Redis] = None

    async def connect(self) -> None:
        """Initialize Redis connection pool."""
        if self._client is not None:
            return

        self._pool = ConnectionPool(
            host=self.config.host,
            port=self.config.port,
            db=self.config.db,
            password=self.config.password,
            max_connections=self.config.max_connections,
            socket_timeout=self.config.socket_timeout,
            socket_connect_timeout=self.config.socket_connect_timeout,
            decode_responses=self.config.decode_responses,
        )

        self._client = Redis(connection_pool=self._pool)
        logger.info("Redis cache connected")

    async def disconnect(self) -> None:
        """Close Redis connection."""
        if self._client:
            await self._client.close()
            self._client = None

        if self._pool:
            await self._pool.disconnect()
            self._pool = None

        logger.info("Redis cache disconnected")

    @property
    def client(self) -> Redis:
        """Get Redis client (must be connected first)."""
        if self._client is None:
            raise RuntimeError("Cache client not connected. Call connect() first.")
        return self._client

    async def get(
        self, key: str, default: Optional[T] = None
    ) -> Result[Optional[T], DatabaseError]:
        """
        Get value from cache.

        Args:
            key: Cache key
            default: Default value if not found

        Returns:
            Result with cached value or default
        """
        try:
            value = await self.client.get(key)

            if value is None:
                return success(default)

            # Deserialize JSON
            deserialized = json.loads(value)
            return success(deserialized)

        except RedisError as e:
            logger.warning(f"Cache get failed for key {key}: {e}")
            return success(default)  # Fail gracefully
        except Exception as e:
            return failure(
                DatabaseError(
                    operation="Cache.get",
                    message=f"Failed to get cache key {key}: {str(e)}",
                    original_exception=e,
                )
            )

    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[timedelta] = None,
    ) -> Result[bool, DatabaseError]:
        """
        Set value in cache.

        Args:
            key: Cache key
            value: Value to cache (will be JSON serialized)
            ttl: Time to live (optional)

        Returns:
            Result indicating success
        """
        try:
            # Serialize to JSON
            serialized = json.dumps(value, default=str)

            if ttl:
                await self.client.setex(key, int(ttl.total_seconds()), serialized)
            else:
                await self.client.set(key, serialized)

            return success(True)

        except RedisError as e:
            logger.warning(f"Cache set failed for key {key}: {e}")
            return success(False)  # Fail gracefully
        except Exception as e:
            return failure(
                DatabaseError(
                    operation="Cache.set",
                    message=f"Failed to set cache key {key}: {str(e)}",
                    original_exception=e,
                )
            )

    async def delete(self, key: str) -> Result[bool, DatabaseError]:
        """
        Delete key from cache.

        Args:
            key: Cache key

        Returns:
            Result indicating if key was deleted
        """
        try:
            deleted = await self.client.delete(key)
            return success(deleted > 0)

        except RedisError as e:
            logger.warning(f"Cache delete failed for key {key}: {e}")
            return success(False)
        except Exception as e:
            return failure(
                DatabaseError(
                    operation="Cache.delete",
                    message=f"Failed to delete cache key {key}: {str(e)}",
                    original_exception=e,
                )
            )

    async def delete_pattern(self, pattern: str) -> Result[int, DatabaseError]:
        """
        Delete all keys matching pattern.

        Args:
            pattern: Redis pattern (e.g., "users:*")

        Returns:
            Result with count of deleted keys
        """
        try:
            keys = []
            async for key in self.client.scan_iter(match=pattern):
                keys.append(key)

            if not keys:
                return success(0)

            deleted = await self.client.delete(*keys)
            logger.info(f"Deleted {deleted} keys matching pattern: {pattern}")
            return success(deleted)

        except RedisError as e:
            logger.warning(f"Cache delete_pattern failed for pattern {pattern}: {e}")
            return success(0)
        except Exception as e:
            return failure(
                DatabaseError(
                    operation="Cache.delete_pattern",
                    message=f"Failed to delete pattern {pattern}: {str(e)}",
                    original_exception=e,
                )
            )

    async def exists(self, key: str) -> Result[bool, DatabaseError]:
        """
        Check if key exists in cache.

        Args:
            key: Cache key

        Returns:
            Result indicating if key exists
        """
        try:
            exists = await self.client.exists(key)
            return success(exists > 0)

        except RedisError as e:
            logger.warning(f"Cache exists check failed for key {key}: {e}")
            return success(False)
        except Exception as e:
            return failure(
                DatabaseError(
                    operation="Cache.exists",
                    message=f"Failed to check existence of key {key}: {str(e)}",
                    original_exception=e,
                )
            )

    async def clear_all(self) -> Result[bool, DatabaseError]:
        """
        Clear all cache (use with caution).

        Returns:
            Result indicating success
        """
        try:
            await self.client.flushdb()
            logger.warning("Cache cleared (all keys deleted)")
            return success(True)

        except RedisError as e:
            logger.error(f"Failed to clear cache: {e}")
            return success(False)
        except Exception as e:
            return failure(
                DatabaseError(
                    operation="Cache.clear_all",
                    message=f"Failed to clear cache: {str(e)}",
                    original_exception=e,
                )
            )


# Global cache instance
_cache: Optional[CacheClient] = None


def get_cache() -> CacheClient:
    """Get global cache instance."""
    global _cache
    if _cache is None:
        raise RuntimeError("Cache not initialized. Call init_cache() first.")
    return _cache


def init_cache(config: Optional[CacheConfig] = None) -> CacheClient:
    """
    Initialize global cache instance.

    Args:
        config: Cache configuration (uses defaults if None)

    Returns:
        Initialized cache client
    """
    global _cache
    if _cache is None:
        _cache = CacheClient(config or CacheConfig())
    return _cache


async def connect_cache() -> None:
    """Connect to Redis cache."""
    cache = get_cache()
    await cache.connect()


async def disconnect_cache() -> None:
    """Disconnect from Redis cache."""
    cache = get_cache()
    await cache.disconnect()


# Cache key builders
class CacheKeys:
    """Standard cache key patterns."""

    @staticmethod
    def recruiter(recruiter_id: int) -> str:
        return f"recruiter:{recruiter_id}"

    @staticmethod
    def recruiters_active() -> str:
        return "recruiters:active"

    @staticmethod
    def recruiters_for_city(city_id: int) -> str:
        return f"recruiters:city:{city_id}"

    @staticmethod
    def city(city_id: int) -> str:
        return f"city:{city_id}"

    @staticmethod
    def cities_active() -> str:
        return "cities:active"

    @staticmethod
    def slot(slot_id: int) -> str:
        return f"slot:{slot_id}"

    @staticmethod
    def slots_free_for_recruiter(recruiter_id: int) -> str:
        return f"slots:free:recruiter:{recruiter_id}"

    @staticmethod
    def template(template_id: int) -> str:
        return f"template:{template_id}"

    @staticmethod
    def templates_for_city(city_id: int) -> str:
        return f"templates:city:{city_id}"

    @staticmethod
    def user(user_id: int) -> str:
        return f"user:{user_id}"

    @staticmethod
    def user_by_telegram(telegram_id: int) -> str:
        return f"user:telegram:{telegram_id}"


# Standard TTLs
class CacheTTL:
    """Standard cache TTL values."""

    SHORT = timedelta(minutes=5)  # For frequently changing data
    MEDIUM = timedelta(minutes=30)  # For moderate data
    LONG = timedelta(hours=2)  # For stable data
    VERY_LONG = timedelta(hours=24)  # For rarely changing data
