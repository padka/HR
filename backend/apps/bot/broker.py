"""Notification transport layer backed by Redis streams or in-memory queue."""

from __future__ import annotations

import asyncio
import heapq
import json
import time
import uuid
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple

try:
    from redis.asyncio import Redis
    from redis.exceptions import ResponseError
except Exception:  # pragma: no cover - redis may be optional in some environments
    Redis = None  # type: ignore
    ResponseError = Exception  # type: ignore


__all__ = [
    "BrokerMessage",
    "NotificationBroker",
    "InMemoryNotificationBroker",
    "NotificationBrokerProtocol",
]


@dataclass
class BrokerMessage:
    """Envelope representing a queued notification."""

    id: str
    payload: Dict[str, Any]

    def attempts(self) -> int:
        return int(self.payload.get("attempt", 0))

    def max_attempts(self) -> int:
        return int(self.payload.get("max_attempts", 0) or 0)

    def not_before(self) -> Optional[float]:
        value = self.payload.get("not_before")
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None


class NotificationBrokerProtocol:
    """Protocol exposing the minimal interface required by NotificationService."""

    async def start(self) -> None:  # pragma: no cover - interface
        raise NotImplementedError

    async def publish(self, payload: Dict[str, Any], *, delay_seconds: float = 0.0) -> str:  # pragma: no cover
        raise NotImplementedError

    async def read(self, *, count: int, block_ms: int) -> List[BrokerMessage]:  # pragma: no cover
        raise NotImplementedError

    async def ack(self, message_id: str) -> None:  # pragma: no cover
        raise NotImplementedError

    async def requeue(self, message: BrokerMessage, *, delay_seconds: float) -> str:  # pragma: no cover
        raise NotImplementedError

    async def to_dlq(self, message: BrokerMessage, *, reason: str) -> None:  # pragma: no cover
        raise NotImplementedError

    async def claim_stale(self, *, min_idle_ms: int, count: int) -> List[BrokerMessage]:  # pragma: no cover
        raise NotImplementedError

    async def close(self) -> None:  # pragma: no cover
        raise NotImplementedError


class NotificationBroker(NotificationBrokerProtocol):
    """Redis streams backed broker ensuring at-least-once delivery."""

    def __init__(
        self,
        redis: Redis,
        *,
        stream_key: str = "bot:notifications",
        dlq_key: str = "bot:notifications:dlq",
        group: str = "bot_notification_workers",
        consumer_name: Optional[str] = None,
    ) -> None:
        if redis is None:  # pragma: no cover - defensive
            raise RuntimeError("Redis client is required for NotificationBroker.")
        self._redis = redis
        self._stream_key = stream_key
        self._dlq_key = dlq_key
        self._group = group
        self._consumer = consumer_name or f"consumer-{uuid.uuid4().hex}"
        self._closed = False

    async def start(self) -> None:
        try:
            await self._redis.xgroup_create(
                name=self._stream_key,
                groupname=self._group,
                id="0",
                mkstream=True,
            )
        except ResponseError as exc:  # pragma: no cover - BUSYGROUP is expected
            if "BUSYGROUP" not in str(exc):
                raise

    async def publish(self, payload: Dict[str, Any], *, delay_seconds: float = 0.0) -> str:
        event = dict(payload)
        now = time.time()
        event.setdefault("attempt", 0)
        event.setdefault("max_attempts", 5)
        event.setdefault("created_at", now)
        event["not_before"] = now + max(0.0, float(delay_seconds))
        encoded = self._encode(event)
        return await self._redis.xadd(self._stream_key, encoded)

    async def read(self, *, count: int, block_ms: int) -> List[BrokerMessage]:
        if self._closed:
            return []
        response = await self._redis.xreadgroup(
            groupname=self._group,
            consumername=self._consumer,
            streams={self._stream_key: ">"},
            count=count,
            block=block_ms,
        )
        if not response:
            return []
        messages: List[BrokerMessage] = []
        for _stream, entries in response:
            for message_id, fields in entries:
                data = self._decode(fields)
                messages.append(BrokerMessage(id=self._decode_value(message_id), payload=data))
        return messages

    async def ack(self, message_id: str) -> None:
        if not message_id:
            return
        await self._redis.xack(self._stream_key, self._group, message_id)
        await self._redis.xdel(self._stream_key, message_id)

    async def requeue(self, message: BrokerMessage, *, delay_seconds: float) -> str:
        payload = dict(message.payload)
        # Next attempt will be processed by consumer; keep same attempt counter.
        return await self.publish(payload, delay_seconds=delay_seconds)

    async def to_dlq(self, message: BrokerMessage, *, reason: str) -> None:
        payload = dict(message.payload)
        payload["dlq_reason"] = reason
        payload["failed_at"] = time.time()
        await self._redis.xadd(self._dlq_key, self._encode(payload))
        await self.ack(message.id)

    async def claim_stale(self, *, min_idle_ms: int, count: int) -> List[BrokerMessage]:
        if self._closed:
            return []
        try:
            next_id = "0"
            reclaimed: List[BrokerMessage] = []
            while len(reclaimed) < count:
                # xautoclaim returns (next_id, entries, deleted_ids) in redis-py >= 4.2.0
                result = await self._redis.xautoclaim(
                    self._stream_key,
                    self._group,
                    self._consumer,
                    min_idle_time=min_idle_ms,
                    start_id=next_id,
                    count=count - len(reclaimed),
                )
                next_id, entries = result[0], result[1]
                if not entries:
                    break
                for message_id, fields in entries:
                    data = self._decode(fields)
                    reclaimed.append(BrokerMessage(id=self._decode_value(message_id), payload=data))
                if next_id == "0-0":
                    break
            return reclaimed
        except ResponseError:  # pragma: no cover - defensive safety
            return []

    async def close(self) -> None:
        self._closed = True
        try:
            await self._redis.close()
        except Exception:  # pragma: no cover - defensive
            pass

    def _encode(self, payload: Dict[str, Any]) -> Dict[str, str]:
        encoded: Dict[str, str] = {}
        for key, value in payload.items():
            if isinstance(value, (dict, list)):
                encoded[key] = json.dumps(value)
            elif isinstance(value, float):
                encoded[key] = f"{value:.6f}"
            else:
                encoded[key] = str(value)
        return encoded

    def _decode(self, fields: Dict[bytes, bytes]) -> Dict[str, Any]:
        decoded: Dict[str, Any] = {}
        for key_b, value_b in fields.items():
            key = self._decode_value(key_b)
            value_raw = self._decode_value(value_b)
            if key in {"payload", "payload_json"}:
                try:
                    decoded[key] = json.loads(value_raw)
                except (TypeError, json.JSONDecodeError):
                    decoded[key] = value_raw
            elif key in {"attempt", "max_attempts"}:
                try:
                    decoded[key] = int(value_raw)
                except (TypeError, ValueError):
                    decoded[key] = 0
            elif key in {"not_before", "created_at"}:
                try:
                    decoded[key] = float(value_raw)
                except (TypeError, ValueError):
                    decoded[key] = None
            elif key in {"outbox_id", "booking_id", "candidate_tg_id", "recruiter_tg_id"}:
                try:
                    decoded[key] = int(value_raw)
                except (TypeError, ValueError):
                    decoded[key] = None
            else:
                decoded[key] = value_raw
        return decoded

    @staticmethod
    def _decode_value(value: Any) -> str:
        if isinstance(value, (bytes, bytearray)):
            return value.decode()
        return str(value)


class InMemoryNotificationBroker(NotificationBrokerProtocol):
    """Minimal in-memory broker for development and tests."""

    def __init__(self) -> None:
        self._queue: List[Tuple[float, int, BrokerMessage]] = []
        self._pending: Dict[str, BrokerMessage] = {}
        self._dlq: List[BrokerMessage] = []
        self._cond = asyncio.Condition()
        self._counter = 0
        self._closed = False

    async def start(self) -> None:
        return None

    async def publish(self, payload: Dict[str, Any], *, delay_seconds: float = 0.0) -> str:
        if self._closed:
            raise RuntimeError("Broker is closed")
        message_id = f"inmem-{uuid.uuid4().hex}"
        event = dict(payload)
        now = time.time()
        event.setdefault("attempt", 0)
        event.setdefault("max_attempts", 5)
        event.setdefault("created_at", now)
        event["not_before"] = now + max(0.0, float(delay_seconds))
        message = BrokerMessage(id=message_id, payload=event)

        async with self._cond:
            self._counter += 1
            heapq.heappush(self._queue, (event["not_before"], self._counter, message))
            self._cond.notify_all()
        return message_id

    async def read(self, *, count: int, block_ms: int) -> List[BrokerMessage]:
        timeout = block_ms / 1000.0 if block_ms else None
        deadline = time.time() + timeout if timeout else None
        messages: List[BrokerMessage] = []
        while not messages and not self._closed:
            async with self._cond:
                now = time.time()
                while self._queue and self._queue[0][0] <= now and len(messages) < count:
                    _, _, message = heapq.heappop(self._queue)
                    self._pending[message.id] = message
                    messages.append(message)
                if messages:
                    break
                sleep_timeout = None
                if self._queue:
                    sleep_timeout = max(0.0, self._queue[0][0] - now)
                if deadline is not None:
                    remaining = max(0.0, deadline - now)
                    if sleep_timeout is None or sleep_timeout > remaining:
                        sleep_timeout = remaining
                if sleep_timeout == 0:
                    continue
                if sleep_timeout is None:
                    await self._cond.wait()
                elif sleep_timeout > 0:
                    try:
                        await asyncio.wait_for(self._cond.wait(), timeout=sleep_timeout)
                    except asyncio.TimeoutError:
                        pass
                if deadline is not None and time.time() >= deadline:
                    break
        return messages

    async def ack(self, message_id: str) -> None:
        async with self._cond:
            self._pending.pop(message_id, None)

    async def requeue(self, message: BrokerMessage, *, delay_seconds: float) -> str:
        async with self._cond:
            self._pending.pop(message.id, None)
        return await self.publish(message.payload, delay_seconds=delay_seconds)

    async def to_dlq(self, message: BrokerMessage, *, reason: str) -> None:
        async with self._cond:
            self._pending.pop(message.id, None)
            payload = dict(message.payload)
            payload["dlq_reason"] = reason
            payload["failed_at"] = time.time()
            self._dlq.append(BrokerMessage(id=message.id, payload=payload))

    async def claim_stale(self, *, min_idle_ms: int, count: int) -> List[BrokerMessage]:
        # In-memory broker delivers messages eagerly; pending messages remain until acked.
        async with self._cond:
            reclaimed: List[BrokerMessage] = list(self._pending.values())[:count]
        return reclaimed

    async def close(self) -> None:
        self._closed = True
        async with self._cond:
            self._queue.clear()
            self._pending.clear()
            self._cond.notify_all()

    def dlq_messages(self) -> Iterable[BrokerMessage]:
        return list(self._dlq)
