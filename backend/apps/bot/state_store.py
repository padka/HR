"""State storage backends for bot flow management."""

from __future__ import annotations

import abc
import asyncio
import copy
import logging
import pickle
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple, TypeVar, cast

import redis.asyncio as aioredis
from redis.exceptions import WatchError

from .config import State

T = TypeVar("T")
Mutator = Callable[[State], Tuple[State, T]]


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
    async def get(self, user_id: int) -> Optional[State]:
        """Fetch state for user identifier."""

    @abc.abstractmethod
    async def set(self, user_id: int, state: State) -> None:
        """Persist full state for the user."""

    @abc.abstractmethod
    async def delete(self, user_id: int) -> Optional[State]:
        """Remove state for user, returning previous value if present."""

    @abc.abstractmethod
    async def clear(self) -> None:
        """Clear all stored states."""

    @abc.abstractmethod
    async def atomic_update(self, user_id: int, mutator: Mutator[T]) -> T:
        """Perform atomic read-modify-write operation for the user state."""

    async def update(self, user_id: int, patch: Dict[str, Any]) -> State:
        """Apply shallow patch to the state and return updated snapshot."""

        def _merge(state: State) -> Tuple[State, State]:
            new_state = _clone_state(state)
            new_state.update(patch)
            return new_state, new_state

        return await self.atomic_update(user_id, _merge)

    async def close(self) -> None:  # pragma: no cover - optional override
        """Close underlying resources if supported."""

        return None


def _clone_state(state: Optional[State]) -> State:
    """Return a deep copy of the provided state for safe mutation."""

    if not state:
        return cast(State, {})
    return cast(State, copy.deepcopy(state))


class InMemoryStateStore(StateStore):
    """In-process state storage with TTL semantics."""

    @dataclass
    class _Entry:
        value: State
        expires_at: Optional[float]

    def __init__(self, ttl_seconds: int, *, namespace: str = "bot:state") -> None:
        super().__init__(ttl_seconds, namespace=namespace)
        self._data: Dict[int, InMemoryStateStore._Entry] = {}
        self._locks: Dict[int, asyncio.Lock] = defaultdict(asyncio.Lock)

    # Helpers -------------------------------------------------------------

    @staticmethod
    def _now() -> float:
        return time.monotonic()

    def _deadline(self) -> Optional[float]:
        if self.ttl_seconds <= 0:
            return None
        return self._now() + float(self.ttl_seconds)

    async def get(self, user_id: int) -> Optional[State]:
        entry = self._data.get(user_id)
        if entry is None:
            self._record_miss()
            return None

        if entry.expires_at is not None and entry.expires_at <= self._now():
            # TTL eviction
            self._data.pop(user_id, None)
            self._record_eviction(user_id)
            return None

        self._record_hit()
        return cast(State, copy.deepcopy(entry.value))

    async def set(self, user_id: int, state: State) -> None:
        snapshot = cast(State, copy.deepcopy(state))
        self._data[user_id] = InMemoryStateStore._Entry(snapshot, self._deadline())

    async def delete(self, user_id: int) -> Optional[State]:
        entry = self._data.pop(user_id, None)
        if entry is None:
            self._record_miss()
            return None
        self._record_hit()
        return cast(State, copy.deepcopy(entry.value))

    async def clear(self) -> None:
        self._data.clear()

    async def atomic_update(self, user_id: int, mutator: Mutator[T]) -> T:
        lock = self._locks[user_id]
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
    ) -> "RedisStateStore":
        client = aioredis.from_url(url, decode_responses=False, **kwargs)
        return cls(client, ttl_seconds, namespace=namespace)

    def _key(self, user_id: int) -> str:
        return f"{self._prefix}{user_id}"

    def _serialize(self, state: State) -> bytes:
        return pickle.dumps(state, protocol=pickle.HIGHEST_PROTOCOL)

    def _deserialize(self, payload: bytes) -> State:
        return cast(State, pickle.loads(payload))

    async def get(self, user_id: int) -> Optional[State]:
        key = self._key(user_id)
        payload = await self._redis.get(key)
        if payload is None:
            known = await self._redis.sismember(self._index_key, user_id)
            if known:
                self._record_eviction(user_id)
            else:
                self._record_miss()
            return None

        self._record_hit()
        return self._deserialize(payload)

    async def set(self, user_id: int, state: State) -> None:
        key = self._key(user_id)
        payload = self._serialize(state)
        if self.ttl_seconds > 0:
            await self._redis.set(key, payload, ex=self.ttl_seconds)
        else:
            await self._redis.set(key, payload)
        await self._redis.sadd(self._index_key, user_id)

    async def delete(self, user_id: int) -> Optional[State]:
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
        keys: List[bytes] = []
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
            finally:
                await pipe.reset()

    async def close(self) -> None:  # pragma: no cover - depends on driver internals
        try:
            if hasattr(self._redis, "aclose"):
                await self._redis.aclose()
            else:  # pragma: no branch - backwards compatibility path
                await self._redis.close()
        except Exception:
            pass


class StateManager:
    """High-level facade for working with bot state stores."""

    def __init__(self, store: StateStore) -> None:
        self._store = store

    @property
    def metrics(self) -> StateStoreMetrics:
        return self._store.metrics

    async def get(self, user_id: int, default: Optional[State] = None) -> Optional[State]:
        state = await self._store.get(user_id)
        if state is None:
            return default
        return state

    async def set(self, user_id: int, state: State) -> None:
        await self._store.set(user_id, state)

    async def update(self, user_id: int, patch: Dict[str, Any]) -> State:
        return await self._store.update(user_id, patch)

    async def delete(self, user_id: int) -> Optional[State]:
        return await self._store.delete(user_id)

    async def clear(self) -> None:
        await self._store.clear()

    async def atomic_update(self, user_id: int, mutator: Mutator[T]) -> T:
        def _wrapped(current: State) -> Tuple[State, T]:
            working = _clone_state(current)
            new_state, result = mutator(working)
            return cast(State, new_state), result

        return await self._store.atomic_update(user_id, _wrapped)

    async def close(self) -> None:
        await self._store.close()


def build_state_manager(
    *,
    redis_url: Optional[str],
    ttl_seconds: int,
    namespace: str = "bot:state",
) -> StateManager:
    """Factory helper producing a state manager based on configuration."""

    if redis_url:
        store = RedisStateStore.from_url(redis_url, ttl_seconds, namespace=namespace)
    else:
        store = InMemoryStateStore(ttl_seconds, namespace=namespace)
    return StateManager(store)


__all__ = [
    "build_state_manager",
    "InMemoryStateStore",
    "Mutator",
    "RedisStateStore",
    "StateManager",
    "StateStore",
    "StateStoreMetrics",
]
