import asyncio
from typing import Dict, Optional

import pytest

from backend.apps.bot.state_store import (
    InMemoryStateStore,
    RedisStateStore,
    StateManager,
)

try:
    from fakeredis import aioredis as fakeredis_aioredis
except ImportError:  # pragma: no cover - dependency guarded in tests only
    fakeredis_aioredis = None


@pytest.mark.parametrize("store_factory", ["memory", "redis"])
@pytest.mark.asyncio
async def test_state_store_roundtrip(store_factory: str) -> None:
    store = await _make_store(store_factory)
    try:
        assert await store.get(1) is None
        assert store.metrics.state_misses == 1

        payload: Dict[str, object] = {"foo": "bar"}
        await store.set(1, payload)

        loaded = await store.get(1)
        assert loaded == payload
        assert store.metrics.state_hits >= 1
    finally:
        await store.clear()
        await store.close()


@pytest.mark.parametrize("store_factory", ["memory", "redis"])
@pytest.mark.asyncio
async def test_state_store_ttl_eviction(store_factory: str) -> None:
    store = await _make_store(store_factory, ttl_seconds=1)
    try:
        await store.set(1, {"value": 42})
        await asyncio.sleep(1.2)
        assert await store.get(1) is None
        assert store.metrics.state_evictions >= 1
    finally:
        await store.clear()
        await store.close()


@pytest.mark.parametrize("store_factory", ["memory", "redis"])
@pytest.mark.asyncio
async def test_atomic_update_parallel(store_factory: str) -> None:
    store = await _make_store(store_factory)
    manager = StateManager(store)

    async def worker(iterations: int) -> None:
        for _ in range(iterations):
            await manager.atomic_update(1, _increment_counter)

    try:
        await manager.set(1, {"counter": 0})
        tasks = [asyncio.create_task(worker(25)) for _ in range(8)]
        await asyncio.gather(*tasks)

        final = await manager.get(1, default={})
        assert final["counter"] == 25 * 8
    finally:
        await store.clear()
        await manager.close()


def _increment_counter(state: Dict[str, int]):
    counter = int(state.get("counter", 0)) + 1
    state["counter"] = counter
    return state, counter


async def _make_store(kind: str, ttl_seconds: int = 5):
    if kind == "memory":
        return InMemoryStateStore(ttl_seconds=ttl_seconds)

    if fakeredis_aioredis is None:
        pytest.skip("fakeredis is required for Redis store tests")

    fake = fakeredis_aioredis.FakeRedis()
    return RedisStateStore(fake, ttl_seconds=ttl_seconds)
