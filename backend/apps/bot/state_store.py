"""State storage backends for bot flow management."""

from __future__ import annotations

import abc
import asyncio
import copy
import json
import logging
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any, TypeVar, cast

import redis.asyncio as aioredis
from redis.exceptions import WatchError

from backend.core.redis_factory import parse_redis_target

from .config import State

logger = logging.getLogger(__name__)

T = TypeVar("T")
Mutator = Callable[[State], tuple[State, T]]


@dataclass
class StateStoreMetrics:
    """Simple counters describing state store behaviour."""

    state_hits: int = 0
    state_misses: int = 0
    state_evictions: int = 0


class StateStore(abc.ABC):
    """Abstract storage backend for candidate state."""

    def __init__(self, ttl_seconds: int, *, namespace: str = "bot:state") -> None:
        self.ttl_seconds = ttl_seconds
        self.namespace = namespace.rstrip(":")
        self.metrics = StateStoreMetrics()
        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    # Metrics helpers -----------------------------------------------------

    def _record_hit(self) -> None:
        self.metrics.state_hits += 1

    def _record_miss(self) -> None:
        self.metrics.state_misses += 1

    def _record_eviction(self, user_id: int) -> None:
        self.metrics.state_evictions += 1
        self.metrics.state_misses += 1
        self._logger.warning("State TTL expired; evicting", extra={"user_id": user_id})

    # Abstract API --------------------------------------------------------

    @abc.abstractmethod
    async def get(self, user_id: int) -> State | None:
        """Fetch state for user identifier."""

    async def get_many(self, user_ids: Iterable[int]) -> dict[int, State]:
        """Fetch multiple states at once, omitting missing entries."""

        result: dict[int, State] = {}
        for raw_user_id in user_ids:
            try:
                user_id = int(raw_user_id)
            except (TypeError, ValueError):
                continue
            state = await self.get(user_id)
            if state is not None:
                result[user_id] = state
        return result

    @abc.abstractmethod
    async def set(self, user_id: int, state: State) -> None:
        """Persist full state for the user."""

    @abc.abstractmethod
    async def delete(self, user_id: int) -> State | None:
        """Remove state for user, returning previous value if present."""

    @abc.abstractmethod
    async def clear(self) -> None:
        """Clear all stored states."""

    @abc.abstractmethod
    async def atomic_update(self, user_id: int, mutator: Mutator[T]) -> T:
        """Perform atomic read-modify-write operation for the user state."""

    async def update(self, user_id: int, patch: dict[str, Any]) -> State:
        """Apply shallow patch to the state and return updated snapshot."""

        def _merge(state: State) -> tuple[State, State]:
            new_state = _clone_state(state)
            new_state.update(patch)
            return new_state, new_state

        return await self.atomic_update(user_id, _merge)

    async def close(self) -> None:  # pragma: no cover - optional override
        """Close underlying resources if supported."""

        return None


def _clone_state(state: State | None) -> State:
    """Return a deep copy of the provided state for safe mutation."""

    if not state:
        return cast(State, {})
    return cast(State, copy.deepcopy(state))


class InMemoryStateStore(StateStore):
    """In-process state storage with TTL semantics."""

    @dataclass
    class _Entry:
        value: State
        expires_at: float | None

    _MAX_LOCKS = 10_000

    def __init__(self, ttl_seconds: int, *, namespace: str = "bot:state") -> None:
        super().__init__(ttl_seconds, namespace=namespace)
        self._data: dict[int, InMemoryStateStore._Entry] = {}
        self._locks: dict[int, asyncio.Lock] = {}

    # Helpers -------------------------------------------------------------

    @staticmethod
    def _now() -> float:
        return time.monotonic()

    def _deadline(self) -> float | None:
        if self.ttl_seconds <= 0:
            return None
        return self._now() + float(self.ttl_seconds)

    def _cleanup_lock(self, user_id: int) -> None:
        lock = self._locks.get(user_id)
        if lock is not None and not lock.locked():
            self._locks.pop(user_id, None)

    def _get_lock(self, user_id: int) -> asyncio.Lock:
        lock = self._locks.get(user_id)
        if lock is None:
            if len(self._locks) >= self._MAX_LOCKS:
                unlocked = [k for k, v in self._locks.items() if not v.locked()]
                for k in unlocked[:len(self._locks) // 2]:
                    del self._locks[k]
            lock = asyncio.Lock()
            self._locks[user_id] = lock
        return lock

    async def get(self, user_id: int) -> State | None:
        entry = self._data.get(user_id)
        if entry is None:
            self._record_miss()
            return None

        if entry.expires_at is not None and entry.expires_at <= self._now():
            # TTL eviction
            self._data.pop(user_id, None)
            self._cleanup_lock(user_id)
            self._record_eviction(user_id)
            return None

        self._record_hit()
        return cast(State, copy.deepcopy(entry.value))

    async def get_many(self, user_ids: Iterable[int]) -> dict[int, State]:
        result: dict[int, State] = {}
        for raw_user_id in user_ids:
            try:
                user_id = int(raw_user_id)
            except (TypeError, ValueError):
                continue
            state = await self.get(user_id)
            if state is not None:
                result[user_id] = state
        return result

    async def set(self, user_id: int, state: State) -> None:
        snapshot = cast(State, copy.deepcopy(state))
        self._data[user_id] = InMemoryStateStore._Entry(snapshot, self._deadline())

    async def delete(self, user_id: int) -> State | None:
        entry = self._data.pop(user_id, None)
        self._cleanup_lock(user_id)
        if entry is None:
            self._record_miss()
            return None
        self._record_hit()
        return cast(State, copy.deepcopy(entry.value))

    async def clear(self) -> None:
        self._data.clear()
        self._locks.clear()

    async def atomic_update(self, user_id: int, mutator: Mutator[T]) -> T:
        lock = self._get_lock(user_id)
        async with lock:
            entry = self._data.get(user_id)
            if entry is None:
                current = cast(State, {})
                self._record_miss()
            else:
                expired = entry.expires_at is not None and entry.expires_at <= self._now()
                if expired:
                    self._data.pop(user_id, None)
                    self._record_eviction(user_id)
                    current = cast(State, {})
                else:
                    self._record_hit()
                    current = cast(State, copy.deepcopy(entry.value))

            new_state, result = mutator(current)
            snapshot = cast(State, copy.deepcopy(new_state))
            self._data[user_id] = InMemoryStateStore._Entry(snapshot, self._deadline())
            return result


class RedisStateStore(StateStore):
    """Redis-based persistent state storage with TTL."""

    def __init__(
        self,
        redis: aioredis.Redis,
        ttl_seconds: int,
        *,
        namespace: str = "bot:state",
    ) -> None:
        super().__init__(ttl_seconds, namespace=namespace)
        self._redis = redis
        self._prefix = f"{self.namespace}:"
        self._index_key = f"{self.namespace}:__keys"

    @classmethod
    def from_url(
        cls,
        url: str,
        ttl_seconds: int,
        *,
        namespace: str = "bot:state",
        **kwargs: Any,
    ) -> RedisStateStore:
        parse_redis_target(url, component="state_store")
        client = aioredis.from_url(url, decode_responses=False, **kwargs)
        return cls(client, ttl_seconds, namespace=namespace)

    def _key(self, user_id: int) -> str:
        return f"{self._prefix}{user_id}"

    def _serialize(self, state: State) -> bytes:
        return json.dumps(state, ensure_ascii=False, default=str).encode("utf-8")

    def _deserialize(self, payload: bytes) -> State:
        return cast(State, json.loads(payload))

    async def _repair_index_entry(self, user_id: int) -> None:
        key = self._key(user_id)
        while True:
            try:
                async with self._redis.pipeline(transaction=True) as pipe:
                    await pipe.watch(key)
                    if await pipe.exists(key):
                        return
                    pipe.multi()
                    pipe.srem(self._index_key, user_id)
                    await pipe.execute()
                    return
            except WatchError:
                continue
            except Exception:
                logger.debug("state_store.index_repair_failed", exc_info=True)
                return

    async def _repair_index_entries(self, user_ids: Iterable[int]) -> None:
        for user_id in user_ids:
            await self._repair_index_entry(user_id)

    async def get(self, user_id: int) -> State | None:
        key = self._key(user_id)
        payload = await self._redis.get(key)
        if payload is None:
            known = await self._redis.sismember(self._index_key, user_id)
            if known:
                await self._repair_index_entry(user_id)
                self._record_eviction(user_id)
            else:
                self._record_miss()
            return None

        self._record_hit()
        return self._deserialize(payload)

    async def get_many(self, user_ids: Iterable[int]) -> dict[int, State]:
        normalized_ids: list[int] = []
        seen: set[int] = set()
        for raw_user_id in user_ids:
            try:
                user_id = int(raw_user_id)
            except (TypeError, ValueError):
                continue
            if user_id in seen:
                continue
            seen.add(user_id)
            normalized_ids.append(user_id)

        if not normalized_ids:
            return {}

        keys = [self._key(user_id) for user_id in normalized_ids]
        payloads = await self._redis.mget(keys)

        result: dict[int, State] = {}
        missing_ids: list[int] = []
        for user_id, payload in zip(normalized_ids, payloads, strict=False):
            if payload is None:
                missing_ids.append(user_id)
                continue
            self._record_hit()
            result[user_id] = self._deserialize(payload)

        if missing_ids:
            known_results: list[bool] = [False] * len(missing_ids)
            try:
                async with self._redis.pipeline(transaction=False) as pipe:
                    for user_id in missing_ids:
                        pipe.sismember(self._index_key, user_id)
                    raw_known = await pipe.execute()
                known_results = [bool(value) for value in raw_known]
            except Exception:
                known_results = [False] * len(missing_ids)

            stale_ids: list[int] = []
            for user_id, known in zip(missing_ids, known_results, strict=False):
                if known:
                    stale_ids.append(user_id)
                    self._record_eviction(user_id)
                else:
                    self._record_miss()
            if stale_ids:
                await self._repair_index_entries(stale_ids)

        return result

    async def set(self, user_id: int, state: State) -> None:
        key = self._key(user_id)
        payload = self._serialize(state)
        if self.ttl_seconds > 0:
            await self._redis.set(key, payload, ex=self.ttl_seconds)
        else:
            await self._redis.set(key, payload)
        await self._redis.sadd(self._index_key, user_id)

    async def delete(self, user_id: int) -> State | None:
        key = self._key(user_id)
        payload = await self._redis.getdel(key)
        await self._redis.srem(self._index_key, user_id)
        if payload is None:
            self._record_miss()
            return None
        self._record_hit()
        return self._deserialize(payload)

    async def clear(self) -> None:
        pattern = f"{self._prefix}*"
        keys: list[bytes] = []
        async for key in self._redis.scan_iter(match=pattern):
            keys.append(key)
        if keys:
            await self._redis.delete(*keys)
        await self._redis.delete(self._index_key)

    async def atomic_update(self, user_id: int, mutator: Mutator[T]) -> T:
        key = self._key(user_id)
        while True:  # retry loop for optimistic locking
            try:
                async with self._redis.pipeline(transaction=True) as pipe:
                    await pipe.watch(key)
                    payload = await pipe.get(key)
                    if payload is None:
                        known = await self._redis.sismember(self._index_key, user_id)
                        if known:
                            await self._repair_index_entry(user_id)
                            self._record_eviction(user_id)
                        else:
                            self._record_miss()
                        current = cast(State, {})
                    else:
                        self._record_hit()
                        current = self._deserialize(payload)

                    working = _clone_state(current)
                    new_state, result = mutator(working)
                    serialized = self._serialize(new_state)

                    pipe.multi()
                    if self.ttl_seconds > 0:
                        pipe.set(key, serialized, ex=self.ttl_seconds)
                    else:
                        pipe.set(key, serialized)
                    pipe.sadd(self._index_key, user_id)
                    await pipe.execute()
                    return result
            except WatchError:
                continue

    async def close(self) -> None:  # pragma: no cover - depends on driver internals
        try:
            if hasattr(self._redis, "aclose"):
                await self._redis.aclose()
            else:  # pragma: no branch - backwards compatibility path
                await self._redis.close()
        except Exception:
            logger.debug("state_store.close_error", exc_info=True)


class StateManager:
    """High-level facade for working with bot state stores."""

    def __init__(self, store: StateStore) -> None:
        self._store = store

    @property
    def metrics(self) -> StateStoreMetrics:
        return self._store.metrics

    async def get(self, user_id: int, default: State | None = None) -> State | None:
        state = await self._store.get(user_id)
        if state is None:
            return default
        return state

    async def get_many(self, user_ids: Iterable[int]) -> dict[int, State]:
        return await self._store.get_many(user_ids)

    async def set(self, user_id: int, state: State) -> None:
        await self._store.set(user_id, state)

    async def update(self, user_id: int, patch: dict[str, Any]) -> State:
        return await self._store.update(user_id, patch)

    async def delete(self, user_id: int) -> State | None:
        return await self._store.delete(user_id)

    async def clear(self) -> None:
        await self._store.clear()

    async def atomic_update(self, user_id: int, mutator: Mutator[T]) -> T:
        def _wrapped(current: State) -> tuple[State, T]:
            working = _clone_state(current)
            new_state, result = mutator(working)
            return cast(State, new_state), result

        return await self._store.atomic_update(user_id, _wrapped)

    async def close(self) -> None:
        await self._store.close()


def build_state_manager(
    *,
    redis_url: str | None,
    ttl_seconds: int,
    namespace: str = "bot:state",
) -> StateManager:
    """Factory helper producing a state manager based on configuration."""

    if redis_url:
        store = RedisStateStore.from_url(redis_url, ttl_seconds, namespace=namespace)
    else:
        store = InMemoryStateStore(ttl_seconds, namespace=namespace)
    return StateManager(store)


async def can_connect_redis(redis_url: str | None, *, component: str = "state_store") -> bool:
    """Check Redis reachability to decide whether to use it for state storage."""
    if not redis_url:
        return False
    try:
        parse_redis_target(redis_url, component=component)
        client = aioredis.from_url(redis_url, decode_responses=False)
        await client.ping()
        return True
    except Exception as exc:
        logger.warning("Redis %s unavailable; falling back to memory: %s", component, exc)
        return False
    finally:
        try:
            if "client" in locals():
                if hasattr(client, "aclose"):
                    await client.aclose()
                else:
                    await client.close()
        except Exception:
            logger.debug("redis_state_store_close_error", exc_info=True)


__all__ = [
    "build_state_manager",
    "can_connect_redis",
    "InMemoryStateStore",
    "Mutator",
    "RedisStateStore",
    "StateManager",
    "StateStore",
    "StateStoreMetrics",
]
