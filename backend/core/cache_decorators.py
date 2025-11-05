"""Cache decorators for repository methods.

Provides decorators to add caching to repository methods with:
- Automatic key generation
- TTL management
- Invalidation on writes
- Result pattern integration
"""

from __future__ import annotations

import functools
import inspect
import logging
from datetime import timedelta
from typing import Any, Callable, Optional, TypeVar

from backend.core.cache import CacheTTL, get_cache
from backend.core.result import Result, Success

logger = logging.getLogger(__name__)

T = TypeVar("T")
E = TypeVar("E")


def cached(
    key_builder: Callable[..., str],
    ttl: Optional[timedelta] = CacheTTL.MEDIUM,
    cache_none: bool = False,
) -> Callable:
    """
    Decorator to cache repository method results.

    Usage:
        @cached(
            key_builder=lambda self, id: f"user:{id}",
            ttl=CacheTTL.LONG
        )
        async def get(self, id: int) -> Result[User, Error]:
            ...

    Args:
        key_builder: Function to build cache key from method args
        ttl: Time to live for cached value
        cache_none: Whether to cache None results

    Returns:
        Decorated function with caching
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Build cache key
            try:
                cache_key = key_builder(*args, **kwargs)
            except Exception as e:
                logger.warning(f"Failed to build cache key: {e}")
                return await func(*args, **kwargs)

            # Try to get from cache
            try:
                cache = get_cache()
                cached_result = await cache.get(cache_key)

                if cached_result.is_success():
                    cached_value = cached_result.unwrap()

                    if cached_value is not None:
                        logger.debug(f"Cache hit: {cache_key}")
                        return Success(cached_value)

            except Exception as e:
                logger.warning(f"Cache read failed for {cache_key}: {e}")
                # Continue to execute function

            # Execute function
            result = await func(*args, **kwargs)

            # Cache successful results
            if isinstance(result, Success):
                value = result.value

                # Check if we should cache None
                if value is None and not cache_none:
                    return result

                try:
                    cache = get_cache()
                    await cache.set(cache_key, value, ttl=ttl)
                    logger.debug(f"Cache set: {cache_key}")
                except Exception as e:
                    logger.warning(f"Cache write failed for {cache_key}: {e}")
                    # Don't fail the request

            return result

        return wrapper

    return decorator


def invalidate_cache(*patterns: str) -> Callable:
    """
    Decorator to invalidate cache patterns after method execution.

    Usage:
        @invalidate_cache("users:*", "user:{self.user_id}")
        async def update_user(self, user: User) -> Result[User, Error]:
            ...

    Args:
        *patterns: Cache key patterns to invalidate

    Returns:
        Decorated function that invalidates cache
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Execute function first
            result = await func(*args, **kwargs)

            # Only invalidate on success
            if isinstance(result, Success):
                try:
                    cache = get_cache()

                    for pattern in patterns:
                        # Replace {self.attr} placeholders
                        resolved_pattern = _resolve_pattern(pattern, args, kwargs)

                        if "*" in resolved_pattern:
                            await cache.delete_pattern(resolved_pattern)
                        else:
                            await cache.delete(resolved_pattern)

                        logger.debug(f"Cache invalidated: {resolved_pattern}")

                except Exception as e:
                    logger.warning(f"Cache invalidation failed: {e}")
                    # Don't fail the request

            return result

        return wrapper

    return decorator


def _resolve_pattern(pattern: str, args: tuple, kwargs: dict) -> str:
    """
    Resolve placeholders in cache pattern.

    Supports:
    - {self.attr} - instance attributes
    - {arg0}, {arg1} - positional arguments
    - {kwarg_name} - keyword arguments
    """
    resolved = pattern

    # Replace {self.attr}
    if "{self." in resolved and len(args) > 0:
        self_obj = args[0]
        # Find all {self.xxx} patterns
        import re

        for match in re.finditer(r"\{self\.(\w+)\}", resolved):
            attr_name = match.group(1)
            if hasattr(self_obj, attr_name):
                attr_value = getattr(self_obj, attr_name)
                resolved = resolved.replace(match.group(0), str(attr_value))

    # Replace {argN}
    for i, arg in enumerate(args):
        placeholder = f"{{arg{i}}}"
        if placeholder in resolved:
            resolved = resolved.replace(placeholder, str(arg))

    # Replace {kwarg}
    for key, value in kwargs.items():
        placeholder = f"{{{key}}}"
        if placeholder in resolved:
            resolved = resolved.replace(placeholder, str(value))

    return resolved


class CacheInvalidator:
    """
    Helper class for manual cache invalidation.

    Usage:
        invalidator = CacheInvalidator()
        await invalidator.invalidate_recruiter(recruiter_id)
    """

    def __init__(self):
        self.cache = get_cache()

    async def invalidate_recruiter(self, recruiter_id: int) -> None:
        """Invalidate all recruiter-related cache."""
        await self.cache.delete(f"recruiter:{recruiter_id}")
        await self.cache.delete_pattern("recruiters:*")

    async def invalidate_city(self, city_id: int) -> None:
        """Invalidate all city-related cache."""
        await self.cache.delete(f"city:{city_id}")
        await self.cache.delete_pattern("cities:*")
        await self.cache.delete_pattern(f"recruiters:city:{city_id}")
        await self.cache.delete_pattern(f"templates:city:{city_id}")

    async def invalidate_slot(self, slot_id: int, recruiter_id: Optional[int] = None) -> None:
        """Invalidate all slot-related cache."""
        await self.cache.delete(f"slot:{slot_id}")

        if recruiter_id:
            await self.cache.delete_pattern(f"slots:free:recruiter:{recruiter_id}")

    async def invalidate_template(self, template_id: int, city_id: Optional[int] = None) -> None:
        """Invalidate all template-related cache."""
        await self.cache.delete(f"template:{template_id}")

        if city_id:
            await self.cache.delete_pattern(f"templates:city:{city_id}")

    async def invalidate_user(self, user_id: int, telegram_id: Optional[int] = None) -> None:
        """Invalidate all user-related cache."""
        await self.cache.delete(f"user:{user_id}")

        if telegram_id:
            await self.cache.delete(f"user:telegram:{telegram_id}")

    async def invalidate_all(self) -> None:
        """Clear entire cache (use with caution)."""
        await self.cache.clear_all()
        logger.warning("All cache invalidated")
