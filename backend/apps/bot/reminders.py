"""Reminder scheduling primitives for the Telegram bot."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Awaitable, Callable, Dict, Protocol, Tuple

from .config import RemKey

ReminderCallback = Callable[[], Awaitable[None]]
ReminderKind = str
ReminderQueueKey = Tuple[ReminderKind, RemKey]


class ReminderQueue(Protocol):
    """Abstract queue interface for scheduling reminder callbacks."""

    async def enqueue(
        self, key: ReminderQueueKey, when: datetime, callback: ReminderCallback
    ) -> None:
        """Schedule ``callback`` to run at ``when`` (UTC)."""

    def cancel(self, key: ReminderQueueKey) -> None:
        """Cancel a scheduled callback if it is still pending."""

    async def flush(self) -> None:
        """Cancel all scheduled callbacks and wait for them to finish."""


@dataclass(slots=True)
class AsyncioReminderQueue(ReminderQueue):
    """In-memory reminder queue powered by ``asyncio`` tasks."""

    _tasks: Dict[ReminderQueueKey, asyncio.Task[None]] = field(default_factory=dict)

    async def enqueue(
        self, key: ReminderQueueKey, when: datetime, callback: ReminderCallback
    ) -> None:
        existing = self._tasks.pop(key, None)
        if existing and not existing.done():
            existing.cancel()

        now = datetime.now(timezone.utc)
        delay = (when - now).total_seconds()
        if delay <= 0:
            await _run_callback_immediately(callback)
            return

        async def _runner() -> None:
            try:
                await asyncio.sleep(delay)
                await callback()
            except asyncio.CancelledError:
                pass
            except Exception as exc:  # pragma: no cover - logging path
                logging.exception("Reminder callback %s failed: %s", key, exc)

        self._tasks[key] = asyncio.create_task(_runner())

    def cancel(self, key: ReminderQueueKey) -> None:
        task = self._tasks.pop(key, None)
        if task and not task.done():
            task.cancel()

    async def flush(self) -> None:
        for key, task in list(self._tasks.items()):
            if not task.done():
                task.cancel()
            self._tasks.pop(key, None)
            try:
                await task
            except asyncio.CancelledError:
                pass


async def _run_callback_immediately(callback: ReminderCallback) -> None:
    try:
        await callback()
    except Exception as exc:  # pragma: no cover - logging path
        logging.exception("Reminder callback immediate execution failed: %s", exc)
