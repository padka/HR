"""Recovery worker for outbound MAX chat messages."""

from __future__ import annotations

import asyncio
import logging
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from backend.core.db import async_session
from backend.core.messenger.bootstrap import ensure_max_adapter
from backend.core.messenger.protocol import InlineButton
from backend.core.settings import Settings
from backend.domain.candidates.models import User
from backend.domain.candidates.services import (
    RecoverableMaxMessage,
    claim_recoverable_max_messages,
    mark_max_message_dead,
    mark_max_message_retryable_failure,
    mark_max_message_sent,
)
from backend.domain.idempotency import (
    has_max_provider_boundary,
    max_provider_message_id,
)

logger = logging.getLogger(__name__)


def serialize_inline_buttons(
    buttons: list[list[InlineButton]] | None,
) -> list[list[dict[str, Any]]] | None:
    if not buttons:
        return None
    return [
        [
            {
                "text": button.text,
                "callback_data": button.callback_data,
                "url": button.url,
                "kind": button.kind,
            }
            for button in row
        ]
        for row in buttons
    ]


def deserialize_inline_buttons(
    raw_buttons: Any,
) -> list[list[InlineButton]] | None:
    if not isinstance(raw_buttons, list):
        return None
    restored: list[list[InlineButton]] = []
    for row in raw_buttons:
        if not isinstance(row, list):
            continue
        restored_row: list[InlineButton] = []
        for item in row:
            if not isinstance(item, dict):
                continue
            text = str(item.get("text") or "").strip()
            if not text:
                continue
            restored_row.append(
                InlineButton(
                    text=text,
                    callback_data=str(item.get("callback_data") or "").strip() or None,
                    url=str(item.get("url") or "").strip() or None,
                    kind=str(item.get("kind") or "").strip() or None,
                )
            )
        if restored_row:
            restored.append(restored_row)
    return restored or None


def compute_max_delivery_retry_delay(
    *,
    attempt: int,
    retry_base_seconds: int,
    retry_max_seconds: int,
) -> int:
    base = max(1, int(retry_base_seconds)) * (2 ** max(0, int(attempt) - 1))
    return int(min(max(1, int(retry_max_seconds)), base))


def compute_max_delivery_next_retry_at(
    *,
    attempt: int,
    retry_base_seconds: int,
    retry_max_seconds: int,
    now: datetime | None = None,
) -> datetime:
    current = now or datetime.now(UTC)
    return current + timedelta(
        seconds=compute_max_delivery_retry_delay(
            attempt=attempt,
            retry_base_seconds=retry_base_seconds,
            retry_max_seconds=retry_max_seconds,
        )
    )


@dataclass(frozen=True)
class MaxDeliveryRecoveryConfig:
    poll_interval: float
    batch_size: int
    lock_timeout_seconds: int
    max_attempts: int
    retry_base_seconds: int
    retry_max_seconds: int


class MaxDeliveryRecoveryWorker:
    def __init__(
        self,
        *,
        settings: Settings,
        config: MaxDeliveryRecoveryConfig | None = None,
    ) -> None:
        self._settings = settings
        self._config = config or MaxDeliveryRecoveryConfig(
            poll_interval=max(0.5, float(getattr(settings, "max_delivery_recovery_poll_interval", 5.0))),
            batch_size=max(1, int(getattr(settings, "max_delivery_recovery_batch_size", 25))),
            lock_timeout_seconds=max(1, int(getattr(settings, "max_delivery_recovery_lock_timeout_seconds", 60))),
            max_attempts=max(1, int(getattr(settings, "max_delivery_recovery_max_attempts", 5))),
            retry_base_seconds=max(1, int(getattr(settings, "max_delivery_recovery_retry_base_seconds", 30))),
            retry_max_seconds=max(1, int(getattr(settings, "max_delivery_recovery_retry_max_seconds", 900))),
        )
        self._task: asyncio.Task | None = None
        self._stopped = asyncio.Event()

    def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        self._stopped.clear()
        self._task = asyncio.create_task(self._run_loop(), name="max_delivery_recovery")

    async def shutdown(self) -> None:
        self._stopped.set()
        if self._task is not None:
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task
            self._task = None

    async def run_once(self) -> int:
        claimed = await claim_recoverable_max_messages(
            batch_size=self._config.batch_size,
            lock_timeout=timedelta(seconds=self._config.lock_timeout_seconds),
        )
        processed = 0
        for item in claimed:
            processed += 1
            try:
                await self._process_message(item)
            except Exception:
                logger.exception(
                    "max.recovery.process_failed",
                    extra={"message_id": item.id, "client_request_id": item.client_request_id},
                )
        return processed

    async def _run_loop(self) -> None:
        while not self._stopped.is_set():
            try:
                await self.run_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("max.recovery.loop_failed")
            try:
                await asyncio.wait_for(self._stopped.wait(), timeout=self._config.poll_interval)
            except TimeoutError:
                continue

    async def _process_message(self, item: RecoverableMaxMessage) -> None:
        attempted_at = datetime.now(UTC)
        attempt = int(item.delivery_attempts or 0) + 1
        candidate = await self._load_candidate(item.candidate_id)
        max_user_id = str(getattr(candidate, "max_user_id", "") or "").strip() if candidate is not None else ""
        if not max_user_id:
            await self._mark_failure(
                item.id,
                attempt=attempt,
                attempted_at=attempted_at,
                error="candidate_not_bound",
            )
            return

        adapter = await ensure_max_adapter(settings=self._settings)
        if adapter is None:
            await self._mark_failure(
                item.id,
                attempt=attempt,
                attempted_at=attempted_at,
                error="adapter_unavailable",
            )
            return

        payload = dict(item.payload_json or {})
        if has_max_provider_boundary(status=item.status, payload_json=payload):
            await mark_max_message_sent(
                item.id,
                provider_message_id=max_provider_message_id(payload),
                attempted_at=attempted_at,
                record_attempt=False,
            )
            return

        buttons = deserialize_inline_buttons(payload.get("buttons"))
        result = await adapter.send_message(
            max_user_id,
            item.text or "",
            buttons=buttons,
            correlation_id=str(payload.get("correlation_id") or "").strip() or None,
        )
        if result.success:
            await mark_max_message_sent(
                item.id,
                provider_message_id=result.message_id,
                attempted_at=attempted_at,
            )
            return

        await self._mark_failure(
            item.id,
            attempt=attempt,
            attempted_at=attempted_at,
            error=result.error or "max_send_failed",
        )

    async def _load_candidate(self, candidate_id: int) -> User | None:
        async with async_session() as session:
            return await session.get(User, candidate_id)

    async def _mark_failure(
        self,
        message_id: int,
        *,
        attempt: int,
        attempted_at: datetime,
        error: str,
    ) -> None:
        if attempt >= self._config.max_attempts:
            await mark_max_message_dead(
                message_id,
                attempted_at=attempted_at,
                error=error,
                attempts=attempt,
            )
            return
        await mark_max_message_retryable_failure(
            message_id,
            attempted_at=attempted_at,
            error=error,
            next_retry_at=compute_max_delivery_next_retry_at(
                attempt=attempt,
                retry_base_seconds=self._config.retry_base_seconds,
                retry_max_seconds=self._config.retry_max_seconds,
                now=attempted_at,
            ),
            attempts=attempt,
        )
