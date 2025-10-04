"""Cached registry for candidate cities used by the Telegram bot."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

from backend.domain.models import City
from backend.domain.repositories import get_candidate_cities

_CACHE_TTL_SECONDS = 300


@dataclass(frozen=True)
class CityInfo:
    """Immutable snapshot of a city relevant for bot lookups."""

    id: int
    name: str
    tz: str


class CandidateCityRegistry:
    """Lightweight async cache wrapping the candidate city repository."""

    def __init__(self, ttl_seconds: int = _CACHE_TTL_SECONDS) -> None:
        self._ttl_seconds = ttl_seconds
        self._lock = asyncio.Lock()
        self._cache: List[CityInfo] = []
        self._expires_at: float = 0.0

    async def list_cities(self) -> List[CityInfo]:
        now = time.monotonic()
        if self._cache and now < self._expires_at:
            return self._cache

        async with self._lock:
            if self._cache and time.monotonic() < self._expires_at:
                return self._cache
            records: Iterable[City] = await get_candidate_cities()
            snapshot = [CityInfo(id=city.id, name=city.name, tz=city.tz) for city in records]
            self._cache = snapshot
            self._expires_at = time.monotonic() + self._ttl_seconds
            return snapshot

    async def find_by_id(self, city_id: int) -> Optional[CityInfo]:
        for city in await self.list_cities():
            if city.id == city_id:
                return city
        return None

    async def find_by_name(self, name: str) -> Optional[CityInfo]:
        name_norm = name.strip().lower()
        if not name_norm:
            return None
        for city in await self.list_cities():
            if city.name.lower() == name_norm:
                return city
        return None

    async def invalidate(self) -> None:
        async with self._lock:
            self._cache = []
            self._expires_at = 0.0


_registry = CandidateCityRegistry()


async def list_candidate_cities() -> List[CityInfo]:
    """Return cached candidate cities."""

    return await _registry.list_cities()


async def find_candidate_city_by_id(city_id: int) -> Optional[CityInfo]:
    return await _registry.find_by_id(city_id)


async def find_candidate_city_by_name(name: str) -> Optional[CityInfo]:
    return await _registry.find_by_name(name)


async def invalidate_candidate_cities_cache() -> None:
    await _registry.invalidate()


__all__ = [
    "CityInfo",
    "CandidateCityRegistry",
    "find_candidate_city_by_id",
    "find_candidate_city_by_name",
    "invalidate_candidate_cities_cache",
    "list_candidate_cities",
]
