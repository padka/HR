"""State manager and reminder scheduler helpers for the Telegram bot."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Dict, Iterable, List, Optional

from aiogram import Bot
from aiogram.fsm.storage.base import BaseStorage, StorageKey
from aiogram.fsm.storage.memory import MemoryStorage

try:  # pragma: no cover - optional dependency
    from aiogram.fsm.storage.redis import DefaultKeyBuilder, RedisStorage
except Exception:  # pragma: no cover - redis is optional in tests
    RedisStorage = None  # type: ignore[assignment]
    DefaultKeyBuilder = None  # type: ignore[assignment]

from backend.core.settings import Settings


@dataclass(slots=True)
class ReminderMeta:
    """Metadata describing a reminder event."""

    slot_id: int
    candidate_id: int
    notify_at: datetime
    kind: str
    payload: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "slot_id": self.slot_id,
            "candidate_id": self.candidate_id,
            "notify_at": self.notify_at.astimezone(timezone.utc).isoformat(),
            "kind": self.kind,
            "payload": self.payload,
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "ReminderMeta":
        notify_at = raw.get("notify_at")
        if isinstance(notify_at, str):
            notify_at_dt = datetime.fromisoformat(notify_at)
        elif isinstance(notify_at, datetime):
            notify_at_dt = notify_at
        else:  # pragma: no cover - defensive branch
            raise ValueError("notify_at must be provided")
        if notify_at_dt.tzinfo is None:
            notify_at_dt = notify_at_dt.replace(tzinfo=timezone.utc)
        return cls(
            slot_id=int(raw["slot_id"]),
            candidate_id=int(raw["candidate_id"]),
            notify_at=notify_at_dt.astimezone(timezone.utc),
            kind=str(raw["kind"]),
            payload=dict(raw.get("payload") or {}),
        )


class StateManager:
    """Encapsulates access to aiogram FSM storage and reminder metadata."""

    REMINDER_DESTINY = "reminders"

    def __init__(self, storage: BaseStorage):
        self._storage = storage
        self._bot_id: Optional[int] = None
        self._lock = asyncio.Lock()

    def set_bot_id(self, bot_id: int) -> None:
        self._bot_id = bot_id

    def require_ready(self) -> None:
        if self._bot_id is None:
            raise RuntimeError("StateManager is not initialised with bot_id yet")

    def _user_key(self, user_id: int) -> StorageKey:
        self.require_ready()
        return StorageKey(bot_id=self._bot_id, chat_id=user_id, user_id=user_id)

    def _reminder_key(self) -> StorageKey:
        self.require_ready()
        return StorageKey(
            bot_id=self._bot_id,
            chat_id=0,
            user_id=0,
            destiny=self.REMINDER_DESTINY,
        )

    async def load_state(self, user_id: int) -> Dict[str, Any]:
        """Return per-user state stored in FSM storage."""
        key = self._user_key(user_id)
        data = await self._storage.get_data(key)
        return dict(data)

    async def save_state(self, user_id: int, data: Dict[str, Any]) -> None:
        """Persist per-user state."""
        key = self._user_key(user_id)
        await self._storage.set_data(key, dict(data))

    async def update_state(self, user_id: int, **changes: Any) -> Dict[str, Any]:
        """Utility helper to update state atomically."""
        async with self._lock:
            state = await self.load_state(user_id)
            state.update(changes)
            await self.save_state(user_id, state)
            return state

    async def clear_state(self, user_id: int) -> None:
        key = self._user_key(user_id)
        await self._storage.set_data(key, {})

    async def schedule_reminder(
        self,
        *,
        slot_id: int,
        candidate_id: int,
        notify_at: datetime,
        kind: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> ReminderMeta:
        """Store reminder metadata in persistent storage."""
        reminder = ReminderMeta(
            slot_id=slot_id,
            candidate_id=candidate_id,
            notify_at=notify_at.astimezone(timezone.utc),
            kind=kind,
            payload=payload or {},
        )
        async with self._lock:
            reminders = await self._load_reminders()
            key = (slot_id, candidate_id, kind)
            filtered = [
                r for r in reminders if (r.slot_id, r.candidate_id, r.kind) != key
            ]
            filtered.append(reminder)
            await self._save_reminders(filtered)
        return reminder

    async def cancel_reminder(
        self,
        *,
        slot_id: int,
        candidate_id: int,
        kind: Optional[str] = None,
    ) -> None:
        """Remove reminder metadata for a slot/candidate."""
        async with self._lock:
            reminders = await self._load_reminders()
            if kind is None:
                filtered = [
                    r
                    for r in reminders
                    if (r.slot_id, r.candidate_id) != (slot_id, candidate_id)
                ]
            else:
                filtered = [
                    r
                    for r in reminders
                    if (r.slot_id, r.candidate_id, r.kind)
                    != (slot_id, candidate_id, kind)
                ]
            if len(filtered) != len(reminders):
                await self._save_reminders(filtered)

    async def pop_due_reminders(self, *, now: Optional[datetime] = None) -> List[ReminderMeta]:
        """Retrieve and remove reminders that are due."""
        current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        async with self._lock:
            reminders = await self._load_reminders()
            due: List[ReminderMeta] = []
            future: List[ReminderMeta] = []
            for reminder in reminders:
                if reminder.notify_at <= current:
                    due.append(reminder)
                else:
                    future.append(reminder)
            if len(future) != len(reminders):
                await self._save_reminders(future)
        return due

    async def _load_reminders(self) -> List[ReminderMeta]:
        key = self._reminder_key()
        raw = await self._storage.get_data(key)
        entries = raw.get("reminders", []) if isinstance(raw, dict) else []
        return [ReminderMeta.from_dict(item) for item in entries]

    async def _save_reminders(self, reminders: Iterable[ReminderMeta]) -> None:
        key = self._reminder_key()
        await self._storage.set_data(
            key,
            {"reminders": [item.to_dict() for item in reminders]},
        )


class ReminderWorker:
    """Background worker that dispatches reminders when they become due."""

    def __init__(
        self,
        state_manager: StateManager,
        *,
        poll_interval: float = 5.0,
    ) -> None:
        self._state_manager = state_manager
        self._poll_interval = poll_interval
        self._callbacks: Dict[str, Callable[[ReminderMeta], Awaitable[None]]] = {}
        self._task: Optional[asyncio.Task[None]] = None
        self._stop_event = asyncio.Event()

    def register_handler(
        self, kind: str, handler: Callable[[ReminderMeta], Awaitable[None]]
    ) -> None:
        self._callbacks[kind] = handler

    async def start(self) -> None:
        if self._task:
            return
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if not self._task:
            return
        self._stop_event.set()
        await self._task
        self._task = None

    async def _run(self) -> None:
        try:
            while not self._stop_event.is_set():
                due = await self._state_manager.pop_due_reminders()
                for reminder in due:
                    handler = self._callbacks.get(reminder.kind)
                    if not handler:
                        continue
                    try:
                        await handler(reminder)
                    except Exception:  # pragma: no cover - logging happens in caller
                        # Handler is responsible for logging, but we must not crash the loop.
                        pass
                await asyncio.wait(
                    [self._stop_event.wait()],
                    timeout=self._poll_interval,
                )
        finally:
            self._task = None


def create_storage(settings: Settings) -> BaseStorage:
    """Factory creating FSM storage based on settings."""
    backend = (settings.state_storage_backend or "").lower()
    if backend == "redis":
        if RedisStorage is None or DefaultKeyBuilder is None:  # pragma: no cover
            raise RuntimeError("Redis storage backend requires aiogram redis extras")
        if not settings.state_storage_dsn:
            raise ValueError("REDIS_DSN must be provided for redis backend")
        return RedisStorage.from_url(
            settings.state_storage_dsn,
            key_builder=DefaultKeyBuilder(with_destiny=True),
        )
    # Default: in-memory storage suitable for tests and development.
    return MemoryStorage()


async def ensure_state_manager_ready(bot: Bot, state_manager: StateManager) -> None:
    """Populate bot id in the state manager."""
    if getattr(bot, "id", None) is None:
        me = await bot.get_me()
        state_manager.set_bot_id(me.id)
    else:
        state_manager.set_bot_id(bot.id)
