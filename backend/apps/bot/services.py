"""Supporting services and helpers for the Telegram bot."""

from __future__ import annotations

import asyncio
import html
import importlib
import logging
import math
import random
import time
import uuid
from types import SimpleNamespace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Awaitable, Callable, Dict, Iterable, List, Optional, Tuple, Literal, TYPE_CHECKING
from zoneinfo import ZoneInfo

from aiohttp import ClientError
from aiogram import Bot
from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramRetryAfter,
    TelegramServerError,
)
from aiogram.methods import SendMessage
from aiogram.types import (
    CallbackQuery,
    ForceReply,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    FSInputFile,
)

from pydantic import ValidationError

from backend.core.settings import get_settings
from backend.domain.candidates import services as candidate_services
from backend.domain.models import SlotStatus, Slot
from backend.apps.bot.events import InterviewSuccessEvent
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.schedulers.base import SchedulerAlreadyRunningError

from backend.apps.bot.broker import BrokerMessage, NotificationBrokerProtocol
from backend.domain.repositories import (
    ReservationResult,
    OutboxItem,
    add_notification_log,
    add_outbox_notification,
    approve_slot,
    claim_outbox_batch,
    confirm_slot_by_candidate,
    get_active_recruiters_for_city,
    get_city,
    get_free_slots_by_recruiter,
    get_notification_log,
    get_outbox_item,
    get_outbox_queue_depth,
    get_recruiter,
    get_slot,
    notification_log_exists,
    register_callback,
    reject_slot,
    reserve_slot,
    mark_outbox_notification_sent,
    reset_outbox_entry,
    set_recruiter_chat_id_by_command,
    update_notification_log_fields,
    update_outbox_entry,
)
from sqlalchemy.exc import IntegrityError

if TYPE_CHECKING:
    from aiogram import Dispatcher

from . import templates
from .config import (
    DEFAULT_TZ,
    FOLLOWUP_NOTICE_PERIOD,
    FOLLOWUP_STUDY_MODE,
    FOLLOWUP_STUDY_SCHEDULE,
    FOLLOWUP_STUDY_FLEX,
    MAX_ATTEMPTS,
    PASS_THRESHOLD,
    State,
    TEST1_QUESTIONS,
    TEST2_QUESTIONS,
    TIME_FMT,
    TIME_LIMIT,
)
from .keyboards import (
    create_keyboard,
    kb_approve,
    kb_attendance_confirm,
    kb_recruiters,
    kb_slots_for_recruiter,
    kb_start,
)
from .city_registry import (
    CityInfo,
    find_candidate_city_by_id,
    find_candidate_city_by_name,
    list_candidate_cities,
)
from .metrics import (
    record_circuit_open,
    record_notification_failed,
    record_notification_sent,
    record_notification_poll_cycle,
    record_notification_poll_skipped,
    record_send_retry,
    record_test1_completion,
    record_test1_rejection,
    set_outbox_queue_depth,
)
from .state_store import StateManager
from .test1_validation import Test1Payload, apply_partial_validation, convert_age
from .reminders import ReminderKind, get_reminder_service
from .template_provider import TemplateProvider, RenderedTemplate


logger = logging.getLogger(__name__)


async def _send_with_retry(bot: Bot, method: SendMessage, correlation_id: str) -> Any:
    attempt = 0
    delay = 1.0
    method = method.as_(bot)
    while True:
        attempt += 1
        try:
            session = bot.session
            client = await session.create_session()
            url = session.api.api_url(token=bot.token, method=method.__api_method__)
            form = session.build_form_data(bot=bot, method=method)
            async with client.post(
                url,
                data=form,
                headers={"X-Telegram-Bot-API-Request-ID": correlation_id},
                timeout=session.timeout,
            ) as resp:
                raw_result = await resp.text()
                status_code = resp.status
            response = session.check_response(
                bot=bot,
                method=method,
                status_code=status_code,
                content=raw_result,
            )
            return response.result
        except TelegramRetryAfter as exc:
            if attempt >= 5:
                raise
            await asyncio.sleep(max(exc.retry_after, delay))
        except TelegramServerError:
            if attempt >= 5:
                raise
            await asyncio.sleep(delay)
            delay = min(delay * 2, 10.0)
        except (asyncio.TimeoutError, ClientError):
            if attempt >= 5:
                raise
            await asyncio.sleep(delay)
            delay = min(delay * 2, 10.0)

_settings = get_settings()
REPORTS_DIR: Path = _settings.data_dir / "reports"
TEST1_DIR: Path = _settings.data_dir / "test1"
UPLOADS_DIR: Path = _settings.data_dir / "uploads"

for _path in (REPORTS_DIR, TEST1_DIR, UPLOADS_DIR):
    _path.mkdir(parents=True, exist_ok=True)

_bot: Optional[Bot] = None
_state_manager: Optional[StateManager] = None
_notification_service: Optional["NotificationService"] = None
_template_provider: Optional[TemplateProvider] = None
_interview_success_handlers: List[
    Callable[[InterviewSuccessEvent], Awaitable[None]]
] = []


def get_template_provider() -> TemplateProvider:
    global _template_provider
    if _template_provider is None:
        _template_provider = TemplateProvider()
    return _template_provider


def reset_template_provider() -> None:
    global _template_provider
    _template_provider = None


def register_interview_success_handler(
    handler: Callable[[InterviewSuccessEvent], Awaitable[None]]
) -> Callable[[InterviewSuccessEvent], Awaitable[None]]:
    if handler not in _interview_success_handlers:
        _interview_success_handlers.append(handler)
    return handler


@dataclass
class NotificationResult:
    status: Literal["queued", "sent", "skipped", "scheduled_retry", "failed"]
    reason: Optional[str] = None
    payload: Optional[str] = None


class NotificationService:
    """Minimal outbox worker for interview confirmation notifications."""

    def __init__(
        self,
        *,
        scheduler: Optional[AsyncIOScheduler] = None,
        template_provider: Optional[TemplateProvider] = None,
        broker: Optional[NotificationBrokerProtocol] = None,
        poll_interval: float = 3.0,
        batch_size: int = 100,
        rate_limit_per_sec: float = 5.0,
        max_attempts: int = 8,
        retry_base_delay: int = 30,
        retry_max_delay: int = 3600,
        circuit_break_window: tuple[int, int] = (30, 60),
    ) -> None:
        self._scheduler = scheduler
        if template_provider is None:
            self._template_provider = get_template_provider()
        else:
            self._template_provider = template_provider
            global _template_provider
            _template_provider = template_provider
        self._poll_interval = max(poll_interval, 0.5)
        self._batch_size = max(1, batch_size)
        self._max_attempts = max(1, max_attempts)
        self._retry_base = max(1, retry_base_delay)
        self._retry_max = max(self._retry_base, retry_max_delay)
        low, high = circuit_break_window
        self._breaker_window = (max(1, low), max(1, high))
        self._breaker_open_until: float = 0.0
        self._token_bucket = (
            _TokenBucket(rate_limit_per_sec, max(1, int(rate_limit_per_sec) * 2))
            if rate_limit_per_sec > 0
            else None
        )
        self._broker = broker
        self._job_id = "notification:outbox_worker"
        self._lock = asyncio.Lock()
        self._task: Optional[asyncio.Task] = None
        self._poll_task: Optional[asyncio.Task] = None
        self._claim_idle_ms = 60000
        self._current_message: Optional[BrokerMessage] = None
        self._skipped_runs: int = 0
        self._started: bool = False

    def start(self, *, allow_poll_loop: bool = False) -> None:
        if self._scheduler is not None:
            self._ensure_scheduler_job()
            self._started = True
            return

        if self._started or not allow_poll_loop:
            return

        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._poll_loop())
        self._started = True

    async def shutdown(self) -> None:
        if self._scheduler is not None:
            try:
                self._scheduler.remove_job(self._job_id)
            except Exception:
                pass
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        if self._poll_task is not None:
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
            self._poll_task = None
        if self._broker is not None:
            try:
                await self._broker.close()
            except Exception:
                logger.exception("Failed to close notification broker")
        self._started = False
        self._skipped_runs = 0

    def _ensure_scheduler_job(self) -> None:
        if self._scheduler is None:
            return

        job = self._scheduler.get_job(self._job_id)
        misfire = max(int(self._poll_interval * 2), 1)
        if job is None:
            self._scheduler.add_job(
                self._scheduled_poll,
                "interval",
                seconds=self._poll_interval,
                id=self._job_id,
                replace_existing=True,
                coalesce=True,
                max_instances=1,
                misfire_grace_time=misfire,
                next_run_time=datetime.now(timezone.utc),
            )
        else:
            job.modify(max_instances=1, coalesce=True, misfire_grace_time=misfire)
            job.reschedule("interval", seconds=self._poll_interval)

        if not self._scheduler.running:
            try:
                self._scheduler.start()
            except SchedulerAlreadyRunningError:
                pass


    async def on_booking_status_changed(
        self,
        booking_id: int,
        status: Any,
        *,
        snapshot: Optional[SlotSnapshot] = None,
    ) -> "NotificationResult":
        raw_status = getattr(status, "value", status)
        try:
            status_value = BookingNotificationStatus(raw_status)
        except (ValueError, TypeError):
            return NotificationResult(status="skipped", reason=f"unsupported_status:{raw_status}")

        if snapshot is None:
            return NotificationResult(status="skipped", reason="missing_snapshot")

        candidate_id = snapshot.candidate_id
        if candidate_id is None:
            return NotificationResult(status="skipped", reason="missing_candidate")

        payload = {
            "event": status_value.value,
            "snapshot": _snapshot_payload(snapshot),
        }

        if status_value is BookingNotificationStatus.RESCHEDULE_REQUESTED:
            outbox = await add_outbox_notification(
                notification_type="candidate_reschedule_prompt",
                booking_id=booking_id,
                candidate_tg_id=candidate_id,
                payload=payload,
            )
            await self._enqueue_outbox(outbox.id, attempt=outbox.attempts)
            return NotificationResult(status="queued", reason="reschedule_prompt_queued")

        if status_value is BookingNotificationStatus.CANCELLED:
            outbox = await add_outbox_notification(
                notification_type="candidate_rejection",
                booking_id=booking_id,
                candidate_tg_id=candidate_id,
                payload=payload,
            )
            await self._enqueue_outbox(outbox.id, attempt=outbox.attempts)
            return NotificationResult(status="queued", reason="rejection_queued")

        return NotificationResult(status="skipped", reason=status_value.value)

    async def retry_notification(self, outbox_id: int) -> "NotificationResult":
        await reset_outbox_entry(outbox_id)
        await self._enqueue_outbox(outbox_id, attempt=0)
        return NotificationResult(status="queued")

    async def _poll_loop(self) -> None:
        try:
            while True:
                await self._poll_once()
                await asyncio.sleep(self._poll_interval)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("notification.worker.loop_failed")

    async def _scheduled_poll(self) -> None:
        if self._poll_task is not None and not self._poll_task.done():
            await self._handle_poll_skipped(reason="inflight")
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            logger.warning("notification.worker.loop_unavailable")
            await self._handle_poll_skipped(reason="no_loop")
            return

        self._poll_task = loop.create_task(self._poll_once())
        self._poll_task.add_done_callback(self._on_poll_task_done)

    def _on_poll_task_done(self, task: asyncio.Task) -> None:
        self._poll_task = None
        if task.cancelled():
            return
        exc = task.exception()
        if exc is not None:
            logger.exception("notification.worker.poll_failed", exc_info=exc)

    async def _handle_poll_skipped(self, *, reason: str) -> None:
        self._skipped_runs += 1
        logger.info(
            "notification.worker.poll_skipped",
            extra={"reason": reason, "skipped_total": self._skipped_runs},
        )
        await record_notification_poll_skipped(reason=reason, skipped_total=self._skipped_runs)

    async def _poll_once(self) -> None:
        start = time.perf_counter()
        processed = 0
        source = "idle"
        started_at = datetime.now(timezone.utc).isoformat()

        logger.info(
            "notification.worker.poll_start",
            extra={"started_at": started_at, "skipped_total": self._skipped_runs},
        )

        try:
            async with self._lock:
                if self._broker is not None:
                    processed, source = await self._poll_broker_queue()
                else:
                    processed, source = await self._poll_outbox_queue()
        except Exception as exc:
            source = f"error:{exc.__class__.__name__}"
            logger.exception(
                "notification.worker.poll_error",
                extra={
                    "started_at": started_at,
                    "duration_ms": int((time.perf_counter() - start) * 1000),
                },
            )
            await set_outbox_queue_depth(0)
        finally:
            duration = time.perf_counter() - start
            logger.info(
                "notification.worker.poll_cycle processed=%s source=%s skipped_total=%s",
                processed,
                source,
                self._skipped_runs,
                extra={
                    "started_at": started_at,
                    "duration_ms": int(duration * 1000),
                    "processed": processed,
                    "source": source,
                    "skipped_total": self._skipped_runs,
                },
            )
            await record_notification_poll_cycle(
                duration=duration,
                processed=processed,
                source=source,
                skipped_total=self._skipped_runs,
            )

    async def _process_broker_message(self, message: BrokerMessage) -> None:
        if self._broker is None:
            return
        now = time.time()
        not_before = message.not_before()
        if not_before is not None and not_before > now:
            delay = max(0.0, not_before - now)
            try:
                await self._broker.requeue(message, delay_seconds=delay)
            finally:
                await self._broker.ack(message.id)
            return

        outbox_id_raw = message.payload.get("outbox_id")
        try:
            outbox_id = int(outbox_id_raw)
        except (TypeError, ValueError):
            await self._broker.ack(message.id)
            return

        item = await get_outbox_item(outbox_id)
        if item is None:
            await self._broker.ack(message.id)
            return

        broker_attempt = message.attempts()
        if broker_attempt and broker_attempt > item.attempts:
            item.attempts = broker_attempt

        try:
            await self._process_item(item, broker_message=message)
        finally:
            await self._broker.ack(message.id)

    async def _enqueue_outbox(
        self,
        outbox_id: int,
        *,
        attempt: int = 0,
        delay: float = 0.0,
    ) -> bool:
        if self._broker is None:
            return False
        payload = {
            "outbox_id": outbox_id,
            "attempt": max(0, int(attempt)),
            "max_attempts": self._max_attempts,
        }
        try:
            await self._broker.publish(payload, delay_seconds=delay)
            return True
        except Exception:
            logger.exception(
                "notification.worker.enqueue_failed",
                extra={"outbox_id": outbox_id, "attempt": attempt},
            )
            return False

    async def _enqueue_due_outbox_batch(self) -> int:
        if self._broker is None:
            return 0

        items = await claim_outbox_batch(batch_size=self._batch_size)
        if not items:
            return 0

        enqueued = 0
        for item in items:
            delay = 0.0
            if item.next_retry_at is not None:
                next_retry = item.next_retry_at
                if isinstance(next_retry, datetime) and next_retry.tzinfo is None:
                    next_retry = next_retry.replace(tzinfo=timezone.utc)
                now = datetime.now(timezone.utc)
                delay = max(0.0, (next_retry - now).total_seconds())
            success = await self._enqueue_outbox(
                item.id,
                attempt=item.attempts,
                delay=delay,
            )
            if success:
                enqueued += 1
            else:
                await update_outbox_entry(
                    item.id,
                    attempts=item.attempts,
                )
        return enqueued

    async def _poll_broker_queue(self) -> Tuple[int, str]:
        if self._broker is None:
            return 0, "broker_unavailable"

        block_ms = int(self._poll_interval * 1000)
        messages = await self._broker.read(count=self._batch_size, block_ms=block_ms)
        source = "broker"

        if not messages:
            source = "broker_idle"
            messages = await self._broker.claim_stale(
                min_idle_ms=self._claim_idle_ms,
                count=self._batch_size,
            )

        if not messages:
            enqueued = await self._enqueue_due_outbox_batch()
            if enqueued:
                source = "broker_bootstrap"
                messages = await self._broker.read(count=self._batch_size, block_ms=block_ms)

        if messages:
            processed = len(messages)
            await set_outbox_queue_depth(processed)
            try:
                for message in messages:
                    await self._process_broker_message(message)
            finally:
                await set_outbox_queue_depth(0)
            return processed, source

        items = await claim_outbox_batch(batch_size=self._batch_size)
        if not items:
            await set_outbox_queue_depth(0)
            return 0, source

        processed = len(items)
        await set_outbox_queue_depth(processed)
        try:
            for item in items:
                await self._process_item(item)
        finally:
            await set_outbox_queue_depth(0)
        return processed, "outbox_fallback"

    async def _poll_outbox_queue(self) -> Tuple[int, str]:
        items = await claim_outbox_batch(batch_size=self._batch_size)
        if not items:
            await set_outbox_queue_depth(0)
            return 0, "outbox_idle"

        processed = len(items)
        await set_outbox_queue_depth(processed)
        try:
            for item in items:
                await self._process_item(item)
        finally:
            await set_outbox_queue_depth(0)
        return processed, "outbox"

    async def _process_item(self, item: OutboxItem, *, broker_message: Optional[BrokerMessage] = None) -> None:
        handlers = {
            "interview_confirmed_candidate": self._process_candidate_confirmation,
            "candidate_reschedule_prompt": self._process_candidate_reschedule,
            "candidate_rejection": self._process_candidate_rejection,
            "recruiter_candidate_confirmed_notice": self._process_recruiter_notice,
            "interview_reminder_2h": self._process_interview_reminder,
            "slot_reminder": self._process_interview_reminder,
            "intro_day_invitation": self._process_intro_day_invitation,
        }
        handler = handlers.get(item.type)
        previous_message = self._current_message
        self._current_message = broker_message
        try:
            if handler is None:
                await self._mark_failed(
                    item,
                    item.attempts,
                    item.type,
                    item.type,
                    f"unsupported_type:{item.type}",
                    None,
                    candidate_tg_id=item.candidate_tg_id,
                )
                return
            await handler(item)
        except Exception as exc:
            logger.exception(
                "notification.worker.process_item_error",
                extra={
                    "outbox_id": item.id,
                    "notification_type": item.type,
                    "booking_id": item.booking_id,
                    "candidate_tg_id": item.candidate_tg_id,
                },
            )
            await self._schedule_retry(
                item,
                attempt=item.attempts + 1,
                log_type=item.type,
                notification_type=item.type,
                error=f"unexpected:{exc.__class__.__name__}",
                rendered=None,
                candidate_tg_id=item.candidate_tg_id,
            )
        finally:
            self._current_message = previous_message

    async def _has_sent_log(
        self,
        log_type: str,
        booking_id: Optional[int],
        candidate_tg_id: Optional[int],
    ) -> bool:
        if booking_id is None:
            return False
        existing = await get_notification_log(
            log_type, booking_id, candidate_tg_id=candidate_tg_id
        )
        return existing is not None and getattr(existing, "delivery_status", "") == "sent"

    async def _process_candidate_confirmation(self, item: OutboxItem) -> None:
        slot = await get_slot(item.booking_id) if item.booking_id is not None else None
        if not slot or slot.candidate_tg_id != item.candidate_tg_id:
            await self._mark_failed(
                item,
                item.attempts,
                "candidate_interview_confirmed",
                "interview_confirmed_candidate",
                "slot_mismatch",
                None,
                candidate_tg_id=item.candidate_tg_id,
            )
            return

        candidate_id = slot.candidate_tg_id
        if await self._has_sent_log("candidate_interview_confirmed", slot.id, candidate_id):
            await update_outbox_entry(
                item.id,
                status="sent",
                attempts=item.attempts,
                next_retry_at=None,
                last_error=None,
            )
            return

        rendered_text, _candidate_tz, _candidate_city, template_key, template_version = await _render_candidate_notification(
            slot
        )
        rendered_payload = SimpleNamespace(
            text=rendered_text,
            key=template_key or "interview_confirmed_candidate",
            version=template_version,
        )
        attempt = item.attempts + 1
        await self._ensure_log(
            "candidate_interview_confirmed",
            item,
            attempt,
            rendered_payload,
            candidate_id,
        )

        if self._is_circuit_open():
            await self._schedule_retry(
                item,
                attempt=attempt,
                log_type="candidate_interview_confirmed",
                notification_type="interview_confirmed_candidate",
                error="circuit_open",
                rendered=rendered_payload,
                retry_after=self._breaker_remaining(),
                candidate_tg_id=candidate_id,
                count_failure=False,
            )
            return

        await self._throttle()

        bot = get_bot()
        try:
            logger.info(
                "notification.worker.send_attempt send_callable=%s",
                _send_with_retry,
                extra={
                    "notification_type": "candidate_interview_confirmed",
                    "candidate_id": candidate_id,
                    "booking_id": slot.id,
                },
            )
            await _send_with_retry(
                bot,
                SendMessage(chat_id=candidate_id, text=rendered_text),
                correlation_id=f"outbox:{slot.id}:{uuid.uuid4().hex}",
            )
        except TelegramRetryAfter as exc:
            self._open_circuit()
            await self._schedule_retry(
                item,
                attempt=attempt,
                log_type="candidate_interview_confirmed",
                notification_type="interview_confirmed_candidate",
                error=str(exc),
                rendered=rendered_payload,
                retry_after=exc.retry_after,
                candidate_tg_id=candidate_id,
            )
            return
        except (TelegramServerError, asyncio.TimeoutError, ClientError) as exc:
            self._open_circuit()
            await self._schedule_retry(
                item,
                attempt=attempt,
                log_type="candidate_interview_confirmed",
                notification_type="interview_confirmed_candidate",
                error=str(exc),
                rendered=rendered_payload,
                candidate_tg_id=candidate_id,
            )
            return
        except TelegramBadRequest as exc:
            await self._mark_failed(
                item,
                attempt,
                "candidate_interview_confirmed",
                "interview_confirmed_candidate",
                str(exc),
                rendered_payload,
                candidate_tg_id=candidate_id,
            )
            return
        except Exception as exc:
            await self._schedule_retry(
                item,
                attempt=attempt,
                log_type="candidate_interview_confirmed",
                notification_type="interview_confirmed_candidate",
                error=str(exc),
                rendered=rendered_payload,
                candidate_tg_id=candidate_id,
            )
            return

        await self._mark_sent(
            item,
            attempt,
            "candidate_interview_confirmed",
            "interview_confirmed_candidate",
            rendered_payload,
            candidate_id,
        )

        try:
            reminder_service = get_reminder_service()
        except RuntimeError:
            reminder_service = None
        if reminder_service is not None and item.booking_id is not None:
            await reminder_service.schedule_for_slot(item.booking_id)

    async def _process_candidate_reschedule(self, item: OutboxItem) -> None:
        slot = await get_slot(item.booking_id) if item.booking_id is not None else None
        snapshot: Optional[SlotSnapshot]

        if slot is not None and slot.candidate_tg_id == item.candidate_tg_id:
            snapshot = await _build_slot_snapshot(slot)
        else:
            payload_snapshot = _snapshot_from_payload((item.payload or {}).get("snapshot"))
            if payload_snapshot is not None and payload_snapshot.candidate_id != item.candidate_tg_id:
                payload_snapshot = None
            snapshot = payload_snapshot

        if snapshot is None or snapshot.candidate_id is None:
            await self._mark_failed(
                item,
                item.attempts,
                "candidate_reschedule_prompt",
                "candidate_reschedule_prompt",
                "snapshot_unavailable",
                None,
                candidate_tg_id=item.candidate_tg_id,
            )
            return

        if not snapshot.slot_id and item.booking_id is not None:
            snapshot.slot_id = item.booking_id

        candidate_id = snapshot.candidate_id
        if await self._has_sent_log(
            "candidate_reschedule_prompt",
            item.booking_id,
            candidate_id,
        ):
            await update_outbox_entry(
                item.id,
                status="sent",
                attempts=item.attempts,
                next_retry_at=None,
                last_error=None,
            )
            return

        context = {
            "candidate_name": snapshot.candidate_fio or str(candidate_id or ""),
            "recruiter_name": snapshot.recruiter_name,
            "dt_local": TemplateProvider.format_local_dt(
                snapshot.start_utc, snapshot.candidate_tz
            ),
            "tz_name": snapshot.candidate_tz,
            "join_link": "",
        }
        rendered = await self._template_provider.render(
            "candidate_reschedule_prompt", context
        )
        if rendered is None:
            await self._mark_failed(
                item,
                item.attempts,
                "candidate_reschedule_prompt",
                "candidate_reschedule_prompt",
                "template_missing",
                None,
                candidate_tg_id=candidate_id,
            )
            return

        attempt = item.attempts + 1
        await self._ensure_log(
            "candidate_reschedule_prompt",
            item,
            attempt,
            rendered,
            candidate_id,
        )

        await self._throttle()
        sent = await self._send_reschedule_message(snapshot, rendered.text)
        if not sent:
            await self._schedule_retry(
                item,
                attempt=attempt,
                log_type="candidate_reschedule_prompt",
                notification_type="candidate_reschedule_prompt",
                error="bot_unavailable",
                rendered=rendered,
                candidate_tg_id=candidate_id,
            )
            return

        await self._mark_sent(
            item,
            attempt,
            "candidate_reschedule_prompt",
            "candidate_reschedule_prompt",
            rendered,
            candidate_id,
        )

    async def _process_candidate_rejection(self, item: OutboxItem) -> None:
        slot = await get_slot(item.booking_id) if item.booking_id is not None else None
        snapshot: Optional[SlotSnapshot]

        if slot is not None and slot.candidate_tg_id == item.candidate_tg_id:
            snapshot = await _build_slot_snapshot(slot)
        else:
            payload_snapshot = _snapshot_from_payload((item.payload or {}).get("snapshot"))
            if payload_snapshot is not None and payload_snapshot.candidate_id != item.candidate_tg_id:
                payload_snapshot = None
            snapshot = payload_snapshot

        if snapshot is None or snapshot.candidate_id is None:
            await self._mark_failed(
                item,
                item.attempts,
                "candidate_rejection",
                "candidate_rejection",
                "snapshot_unavailable",
                None,
                candidate_tg_id=item.candidate_tg_id,
            )
            return

        if not snapshot.slot_id and item.booking_id is not None:
            snapshot.slot_id = item.booking_id

        candidate_id = snapshot.candidate_id
        if await self._has_sent_log("candidate_rejection", item.booking_id, candidate_id):
            await update_outbox_entry(
                item.id,
                status="sent",
                attempts=item.attempts,
                next_retry_at=None,
                last_error=None,
            )
            return

        state = await _load_candidate_state(candidate_id)
        context = {
            "candidate_name": snapshot.candidate_fio or state.get("fio") or str(candidate_id or ""),
            "recruiter_name": snapshot.recruiter_name,
            "dt_local": TemplateProvider.format_local_dt(
                snapshot.start_utc, snapshot.candidate_tz
            ),
            "tz_name": snapshot.candidate_tz,
            "join_link": "",
        }
        rendered = await self._template_provider.render(
            "candidate_rejection", context
        )
        if rendered is None:
            await self._mark_failed(
                item,
                item.attempts,
                "candidate_rejection",
                "candidate_rejection",
                "template_missing",
                None,
                candidate_tg_id=candidate_id,
            )
            return

        attempt = item.attempts + 1
        await self._ensure_log(
            "candidate_rejection",
            item,
            attempt,
            rendered,
            candidate_id,
        )

        if self._is_circuit_open():
            await self._schedule_retry(
                item,
                attempt=attempt,
                log_type="candidate_rejection",
                notification_type="candidate_rejection",
                error="circuit_open",
                rendered=rendered,
                retry_after=self._breaker_remaining(),
                candidate_tg_id=candidate_id,
                count_failure=False,
            )
            return

        await self._throttle()

        bot = get_bot()
        try:
            await _send_with_retry(
                bot,
                SendMessage(chat_id=candidate_id, text=rendered.text),
                correlation_id=f"outbox:{snapshot.slot_id}:{uuid.uuid4().hex}",
            )
        except TelegramRetryAfter as exc:
            self._open_circuit()
            await self._schedule_retry(
                item,
                attempt=attempt,
                log_type="candidate_rejection",
                notification_type="candidate_rejection",
                error=str(exc),
                rendered=rendered,
                retry_after=exc.retry_after,
                candidate_tg_id=candidate_id,
            )
            return
        except (TelegramServerError, asyncio.TimeoutError, ClientError) as exc:
            self._open_circuit()
            await self._schedule_retry(
                item,
                attempt=attempt,
                log_type="candidate_rejection",
                notification_type="candidate_rejection",
                error=str(exc),
                rendered=rendered,
                candidate_tg_id=candidate_id,
            )
            return
        except TelegramBadRequest as exc:
            await self._mark_failed(
                item,
                attempt,
                "candidate_rejection",
                "candidate_rejection",
                str(exc),
                rendered,
                candidate_tg_id=candidate_id,
            )
            return
        except Exception as exc:
            await self._schedule_retry(
                item,
                attempt=attempt,
                log_type="candidate_rejection",
                notification_type="candidate_rejection",
                error=str(exc),
                rendered=rendered,
                candidate_tg_id=candidate_id,
            )
            return

        await self._mark_sent(
            item,
            attempt,
            "candidate_rejection",
            "candidate_rejection",
            rendered,
            candidate_id,
        )
        await self._mark_candidate_rejected(candidate_id)

    async def _process_recruiter_notice(self, item: OutboxItem) -> None:
        slot = await get_slot(item.booking_id) if item.booking_id is not None else None
        if not slot:
            await self._mark_failed(
                item,
                item.attempts,
                "recruiter_candidate_confirmed_notice",
                "recruiter_candidate_confirmed_notice",
                "slot_mismatch",
                None,
                candidate_tg_id=item.candidate_tg_id,
            )
            return

        recruiter = await get_recruiter(slot.recruiter_id) if slot.recruiter_id else None
        if recruiter is None or recruiter.tg_chat_id is None:
            await self._mark_failed(
                item,
                item.attempts,
                "recruiter_candidate_confirmed_notice",
                "recruiter_candidate_confirmed_notice",
                "recruiter_chat_missing",
                None,
                candidate_tg_id=item.candidate_tg_id,
            )
            return

        if await self._has_sent_log(
            "recruiter_candidate_confirmed_notice",
            slot.id,
            item.candidate_tg_id,
        ):
            await update_outbox_entry(
                item.id,
                status="sent",
                attempts=item.attempts,
                next_retry_at=None,
                last_error=None,
            )
            return

        context = {
            "candidate_name": slot.candidate_fio or str(slot.candidate_tg_id or ""),
            "recruiter_name": recruiter.name or "",
            "dt_local": TemplateProvider.format_local_dt(
                slot.start_utc, recruiter.tz or DEFAULT_TZ
            ),
            "tz_name": recruiter.tz or DEFAULT_TZ,
            "join_link": getattr(recruiter, "telemost_url", "") or "",
        }
        rendered = await self._template_provider.render(
            "recruiter_candidate_confirmed_notice", context
        )
        if rendered is None:
            await self._mark_failed(
                item,
                item.attempts,
                "recruiter_candidate_confirmed_notice",
                "recruiter_candidate_confirmed_notice",
                "template_missing",
                None,
                candidate_tg_id=item.candidate_tg_id,
            )
            return

        attempt = item.attempts + 1
        await self._ensure_log(
            "recruiter_candidate_confirmed_notice",
            item,
            attempt,
            rendered,
            item.candidate_tg_id,
        )

        if self._is_circuit_open():
            await self._schedule_retry(
                item,
                attempt=attempt,
                log_type="recruiter_candidate_confirmed_notice",
                notification_type="recruiter_candidate_confirmed_notice",
                error="circuit_open",
                rendered=rendered,
                retry_after=self._breaker_remaining(),
                candidate_tg_id=item.candidate_tg_id,
                count_failure=False,
            )
            return

        await self._throttle()
        bot = get_bot()
        try:
            await _send_with_retry(
                bot,
                SendMessage(chat_id=recruiter.tg_chat_id, text=rendered.text),
                correlation_id=f"outbox:{slot.id}:{uuid.uuid4().hex}",
            )
        except TelegramRetryAfter as exc:
            self._open_circuit()
            await self._schedule_retry(
                item,
                attempt=attempt,
                log_type="recruiter_candidate_confirmed_notice",
                notification_type="recruiter_candidate_confirmed_notice",
                error=str(exc),
                rendered=rendered,
                retry_after=exc.retry_after,
                candidate_tg_id=item.candidate_tg_id,
            )
            return
        except (TelegramServerError, asyncio.TimeoutError, ClientError) as exc:
            self._open_circuit()
            await self._schedule_retry(
                item,
                attempt=attempt,
                log_type="recruiter_candidate_confirmed_notice",
                notification_type="recruiter_candidate_confirmed_notice",
                error=str(exc),
                rendered=rendered,
                candidate_tg_id=item.candidate_tg_id,
            )
            return
        except Exception as exc:
            await self._schedule_retry(
                item,
                attempt=attempt,
                log_type="recruiter_candidate_confirmed_notice",
                notification_type="recruiter_candidate_confirmed_notice",
                error=str(exc),
                rendered=rendered,
                candidate_tg_id=item.candidate_tg_id,
            )
            return

        await self._mark_sent(
            item,
            attempt,
            "recruiter_candidate_confirmed_notice",
            "recruiter_candidate_confirmed_notice",
            rendered,
            item.candidate_tg_id,
        )
        await record_candidate_confirmed_notice()

    async def _process_interview_reminder(self, item: OutboxItem) -> None:
        slot = await get_slot(item.booking_id) if item.booking_id is not None else None
        if not slot or slot.candidate_tg_id != item.candidate_tg_id:
            await self._mark_failed(
                item,
                item.attempts,
                "slot_reminder:mismatch",
                "slot_reminder:mismatch",
                "slot_mismatch",
                None,
                candidate_tg_id=item.candidate_tg_id,
            )
            return

        candidate_id = slot.candidate_tg_id
        payload = item.payload or {}
        reminder_raw = payload.get("reminder_kind")
        try:
            reminder_kind = ReminderKind(reminder_raw)
        except (ValueError, TypeError):
            reminder_kind = ReminderKind.REMIND_24H

        log_type = f"slot_reminder:{reminder_kind.value}"
        notification_type = log_type

        if await self._has_sent_log(log_type, slot.id, candidate_id):
            await update_outbox_entry(
                item.id,
                status="sent",
                attempts=item.attempts,
                next_retry_at=None,
                last_error=None,
            )
            return

        recruiter = await get_recruiter(slot.recruiter_id) if slot.recruiter_id else None
        tz = slot.candidate_tz or DEFAULT_TZ
        labels = slot_local_labels(slot.start_utc, tz)
        context = {
            "candidate_name": slot.candidate_fio or str(candidate_id or ""),
            "candidate_fio": slot.candidate_fio or str(candidate_id or ""),
            "recruiter_name": recruiter.name if recruiter else "",
            "dt_local": TemplateProvider.format_local_dt(slot.start_utc, tz),
            "tz_name": tz,
            "join_link": getattr(recruiter, "telemost_url", "") or "",
            **labels,
        }

        confirm_map = {
            ReminderKind.CONFIRM_6H: "confirm_6h",
            ReminderKind.CONFIRM_3H: "confirm_3h",
            ReminderKind.CONFIRM_2H: "confirm_2h",
            ReminderKind.REMIND_2H: "confirm_2h",
        }
        reminder_map = {
            ReminderKind.REMIND_24H: "reminder_24h",
        }

        if reminder_kind in confirm_map:
            template_key = confirm_map[reminder_kind]
            reply_markup = kb_attendance_confirm(slot.id)
        else:
            template_key = reminder_map.get(reminder_kind)
            if template_key is None:
                await self._mark_sent(
                    item,
                    item.attempts + 1,
                    log_type,
                    notification_type,
                    None,
                    candidate_id,
                )
                return
            reply_markup = None

        rendered = await self._template_provider.render(template_key, context)
        if rendered is None:
            await self._mark_failed(
                item,
                item.attempts,
                log_type,
                notification_type,
                "template_missing",
                None,
                candidate_tg_id=candidate_id,
            )
            return

        attempt = item.attempts + 1
        await self._ensure_log(
            log_type,
            item,
            attempt,
            rendered,
            candidate_id,
        )

        if self._is_circuit_open():
            await self._schedule_retry(
                item,
                attempt=attempt,
                log_type=log_type,
                notification_type=notification_type,
                error="circuit_open",
                rendered=rendered,
                retry_after=self._breaker_remaining(),
                candidate_tg_id=candidate_id,
                count_failure=False,
            )
            return

        await self._throttle()
        bot = get_bot()
        try:
            await _send_with_retry(
                bot,
                SendMessage(chat_id=candidate_id, text=rendered.text, reply_markup=reply_markup),
                correlation_id=f"outbox:{slot.id}:{uuid.uuid4().hex}",
            )
        except TelegramRetryAfter as exc:
            self._open_circuit()
            await self._schedule_retry(
                item,
                attempt=attempt,
                log_type=log_type,
                notification_type=notification_type,
                error=str(exc),
                rendered=rendered,
                retry_after=exc.retry_after,
                candidate_tg_id=candidate_id,
            )
            return
        except (TelegramServerError, asyncio.TimeoutError, ClientError) as exc:
            self._open_circuit()
            await self._schedule_retry(
                item,
                attempt=attempt,
                log_type=log_type,
                notification_type=notification_type,
                error=str(exc),
                rendered=rendered,
                candidate_tg_id=candidate_id,
            )
            return
        except TelegramBadRequest as exc:
            await self._mark_failed(
                item,
                attempt,
                log_type,
                notification_type,
                str(exc),
                rendered,
                candidate_tg_id=candidate_id,
            )
            return
        except Exception as exc:
            await self._schedule_retry(
                item,
                attempt=attempt,
                log_type=log_type,
                notification_type=notification_type,
                error=str(exc),
                rendered=rendered,
                candidate_tg_id=candidate_id,
            )
            return

        await self._mark_sent(
            item,
            attempt,
            log_type,
            notification_type,
            rendered,
            candidate_id,
        )

    async def _process_intro_day_invitation(self, item: OutboxItem) -> None:
        """Process intro day invitation - immediate invitation with confirmation

        Uses city-specific template 'intro_day_invitation' which should contain
        personalized information like address, contact person, etc.
        """
        slot = await get_slot(item.booking_id) if item.booking_id is not None else None
        if not slot or slot.candidate_tg_id != item.candidate_tg_id:
            await self._mark_failed(
                item,
                item.attempts,
                "intro_day_invitation",
                "intro_day_invitation",
                "slot_mismatch",
                None,
                candidate_tg_id=item.candidate_tg_id,
            )
            return

        candidate_id = slot.candidate_tg_id
        log_type = "intro_day_invitation"
        notification_type = "intro_day_invitation"

        if await self._has_sent_log(log_type, slot.id, candidate_id):
            await update_outbox_entry(
                item.id,
                status="sent",
                attempts=item.attempts,
                next_retry_at=None,
                last_error=None,
            )
            return

        recruiter = await get_recruiter(slot.recruiter_id) if slot.recruiter_id else None
        tz = slot.candidate_tz or DEFAULT_TZ
        labels = slot_local_labels(slot.start_utc, tz)

        # Get city name for template context
        city_name = ""
        if slot.candidate_city_id:
            from backend.core.db import async_session
            from backend.domain.models import City
            async with async_session() as session:
                city = await session.get(City, slot.candidate_city_id)
                if city:
                    city_name = getattr(city, "name", "") or getattr(city, "name_plain", "") or ""

        context = {
            "candidate_name": slot.candidate_fio or str(candidate_id or ""),
            "candidate_fio": slot.candidate_fio or str(candidate_id or ""),
            "recruiter_name": recruiter.name if recruiter else "",
            "dt_local": TemplateProvider.format_local_dt(slot.start_utc, tz),
            "tz_name": tz,
            "city_name": city_name,
            "join_link": getattr(recruiter, "telemost_url", "") or "",
            **labels,
        }

        # Try to render from message templates (new system) first, then fallback to old system
        rendered = await self._template_provider.render("intro_day_invitation", context)

        if rendered is None:
            # Fallback to old template system (city-specific templates)
            fallback_text = await templates.tpl(
                slot.candidate_city_id,
                "intro_day_invitation",  # Key in old templates table
                candidate_fio=context["candidate_fio"],
                candidate_name=context["candidate_name"],
                recruiter_name=context["recruiter_name"],
                dt_local=context["dt_local"],
                city_name=city_name,
                **labels,
            )
            if fallback_text:
                from types import SimpleNamespace
                rendered = SimpleNamespace(
                    text=fallback_text,
                    key="intro_day_invitation",
                    version=None,
                )
            else:
                await self._mark_failed(
                    item,
                    item.attempts,
                    log_type,
                    notification_type,
                    "template_missing",
                    None,
                    candidate_tg_id=candidate_id,
                )
                return

        attempt = item.attempts + 1
        await self._ensure_log(
            log_type,
            item,
            attempt,
            rendered,
            candidate_id,
        )

        if self._is_circuit_open():
            await self._schedule_retry(
                item,
                attempt=attempt,
                log_type=log_type,
                notification_type=notification_type,
                error="circuit_open",
                rendered=rendered,
                retry_after=self._breaker_remaining(),
                candidate_tg_id=candidate_id,
                count_failure=False,
            )
            return

        await self._throttle()
        bot = get_bot()

        # Send with confirmation keyboard
        from backend.apps.bot.keyboards import kb_attendance_confirm

        try:
            await _send_with_retry(
                bot,
                SendMessage(
                    chat_id=candidate_id,
                    text=rendered.text,
                    reply_markup=kb_attendance_confirm(slot.id),
                ),
                correlation_id=f"outbox:{slot.id}:{uuid.uuid4().hex}",
            )
        except TelegramRetryAfter as exc:
            self._open_circuit()
            await self._schedule_retry(
                item,
                attempt=attempt,
                log_type=log_type,
                notification_type=notification_type,
                error=str(exc),
                rendered=rendered,
                retry_after=exc.retry_after,
                candidate_tg_id=candidate_id,
            )
            return
        except (TelegramServerError, asyncio.TimeoutError, ClientError) as exc:
            self._open_circuit()
            await self._schedule_retry(
                item,
                attempt=attempt,
                log_type=log_type,
                notification_type=notification_type,
                error=str(exc),
                rendered=rendered,
                candidate_tg_id=candidate_id,
            )
            return
        except TelegramBadRequest as exc:
            await self._mark_failed(
                item,
                attempt,
                log_type,
                notification_type,
                str(exc),
                rendered,
                candidate_tg_id=candidate_id,
            )
            return
        except Exception as exc:
            await self._schedule_retry(
                item,
                attempt=attempt,
                log_type=log_type,
                notification_type=notification_type,
                error=str(exc),
                rendered=rendered,
                candidate_tg_id=candidate_id,
            )
            return

        await self._mark_sent(
            item,
            attempt,
            log_type,
            notification_type,
            rendered,
            candidate_id,
        )

    async def _send_reschedule_message(self, snapshot: SlotSnapshot, text: str) -> bool:
        if snapshot.candidate_id is None:
            return False

        def _clear_slot(st: State) -> Tuple[State, None]:
            st["picked_slot_id"] = None
            return st, None

        await _update_candidate_state(snapshot.candidate_id, _clear_slot)

        try:
            await show_recruiter_menu(snapshot.candidate_id, notice=text)
            return True
        except RuntimeError:
            logger.warning("Bot is not configured; cannot show reschedule prompt")
        except Exception:
            logger.exception("Failed to send reschedule prompt to candidate %s", snapshot.candidate_id)
        return False

    async def _mark_candidate_rejected(self, candidate_id: Optional[int]) -> None:
        if candidate_id is None:
            return

        def _mark_rejected(st: State) -> Tuple[State, None]:
            st["flow"] = "rejected"
            st["picked_slot_id"] = None
            st["picked_recruiter_id"] = None
            return st, None

        await _update_candidate_state(candidate_id, _mark_rejected)


    @staticmethod
    def _rendered_components(rendered: Optional[object]) -> Tuple[str, Optional[str], Optional[int]]:
        if rendered is None:
            return "", None, None
        text = getattr(rendered, "text", None)
        key = getattr(rendered, "key", None)
        version = getattr(rendered, "version", None)
        if text is None:
            return str(rendered), None, None
        return str(text), key, version

    async def _ensure_log(
        self,
        log_type: str,
        item: OutboxItem,
        attempt: int,
        rendered: object,
        candidate_tg_id: Optional[int],
    ) -> None:
        rendered_text, template_key, template_version = self._rendered_components(rendered)
        try:
            await add_notification_log(
                log_type,
                item.booking_id or 0,
                candidate_tg_id=candidate_tg_id,
                payload=rendered_text,
                delivery_status="pending",
                attempts=attempt,
                last_error=None,
                overwrite=True,
                template_key=template_key,
                template_version=template_version,
            )
        except IntegrityError:
            logger.debug(
                "notification.log.duplicate",
                extra={"booking_id": item.booking_id, "log_type": log_type, "candidate_tg_id": candidate_tg_id},
            )
        except Exception:
            logger.exception(
                "notification.log.persist_failed",
                extra={"booking_id": item.booking_id, "log_type": log_type, "candidate_tg_id": candidate_tg_id},
            )

    async def _mark_sent(
        self,
        item: OutboxItem,
        attempt: int,
        log_type: str,
        notification_type: str,
        rendered: object,
        candidate_tg_id: Optional[int],
    ) -> None:
        rendered_text, template_key, template_version = self._rendered_components(rendered)
        await update_outbox_entry(
            item.id,
            status="sent",
            attempts=attempt,
            next_retry_at=None,
            last_error=None,
        )
        created = False
        try:
            created = await add_notification_log(
                log_type,
                item.booking_id or 0,
                candidate_tg_id=candidate_tg_id,
                payload=rendered_text,
                delivery_status="sent",
                attempts=attempt,
                last_error=None,
                next_retry_at=None,
                overwrite=True,
                template_key=template_key,
                template_version=template_version,
            )
        except IntegrityError:
            logger.debug(
                "notification.log.duplicate",
                extra={
                    "booking_id": item.booking_id,
                    "log_type": log_type,
                    "candidate_tg_id": candidate_tg_id,
                },
            )
        except Exception:
            logger.exception(
                "notification.log.persist_failed",
                extra={
                    "booking_id": item.booking_id,
                    "log_type": log_type,
                    "candidate_tg_id": candidate_tg_id,
                },
            )
        logger.info(
            "notification.worker.sent",
            extra={
                "outbox_id": item.id,
                "booking_id": item.booking_id,
                "candidate_tg_id": candidate_tg_id,
                "notification_type": notification_type,
                "log_type": log_type,
                "attempt": attempt,
                "log_created": created,
            },
        )
        await record_notification_sent(notification_type)

    async def _mark_failed(
        self,
        item: OutboxItem,
        attempt: int,
        log_type: str,
        notification_type: str,
        error: str,
        rendered: Optional[object],
        *,
        candidate_tg_id: Optional[int] = None,
    ) -> None:
        rendered_text, template_key, template_version = self._rendered_components(rendered)
        await update_outbox_entry(
            item.id,
            status="failed",
            attempts=max(attempt, item.attempts),
            next_retry_at=None,
            last_error=error,
        )
        created = False
        try:
            created = await add_notification_log(
                log_type,
                item.booking_id or 0,
                candidate_tg_id=candidate_tg_id,
                payload=rendered_text,
                delivery_status="failed",
                attempts=max(attempt, item.attempts),
                last_error=error,
                next_retry_at=None,
                overwrite=True,
                template_key=template_key,
                template_version=template_version,
            )
        except IntegrityError:
            logger.debug(
                "notification.log.duplicate",
                extra={
                    "booking_id": item.booking_id,
                    "log_type": log_type,
                    "candidate_tg_id": candidate_tg_id,
                },
            )
        except Exception:
            logger.exception(
                "notification.log.persist_failed",
                extra={
                    "booking_id": item.booking_id,
                    "log_type": log_type,
                    "candidate_tg_id": candidate_tg_id,
                },
            )
        logger.error(
            "notification.worker.failed",
            extra={
                "outbox_id": item.id,
                "booking_id": item.booking_id,
                "candidate_tg_id": candidate_tg_id,
                "notification_type": notification_type,
                "log_type": log_type,
                "attempt": attempt,
                "error": error,
                "log_created": created,
            },
        )
        await record_notification_failed(notification_type)
        if self._broker is not None and self._current_message is not None:
            try:
                await self._broker.to_dlq(self._current_message, reason=error)
            except Exception:
                logger.exception(
                    "notification.worker.dlq_error",
                    extra={"outbox_id": item.id, "message_id": self._current_message.id},
                )

    async def _schedule_retry(
        self,
        item: OutboxItem,
        *,
        attempt: int,
        log_type: str,
        notification_type: str,
        error: str,
        rendered: Optional[object],
        retry_after: Optional[float] = None,
        candidate_tg_id: Optional[int] = None,
        count_failure: bool = True,
    ) -> None:
        if attempt >= self._max_attempts:
            await self._mark_failed(
                item,
                attempt,
                log_type,
                notification_type,
                error,
                rendered,
                candidate_tg_id=candidate_tg_id,
            )
            return

        delay = self._compute_retry_delay(attempt)
        if retry_after is not None:
            delay = max(delay, float(retry_after))
        delay = self._apply_jitter(delay)
        next_retry_at = datetime.now(timezone.utc) + timedelta(seconds=delay)

        await update_outbox_entry(
            item.id,
            status="pending",
            attempts=max(attempt, item.attempts),
            next_retry_at=next_retry_at,
            last_error=error,
        )
        text, key, version = self._rendered_components(rendered)
        created = False
        try:
            created = await add_notification_log(
                log_type,
                item.booking_id or 0,
                candidate_tg_id=candidate_tg_id,
                payload=text,
                delivery_status="failed",
                attempts=max(attempt, item.attempts),
                last_error=error,
                next_retry_at=next_retry_at,
                overwrite=True,
                template_key=key,
                template_version=version,
            )
        except IntegrityError:
            logger.debug(
                "notification.log.duplicate",
                extra={
                    "booking_id": item.booking_id,
                    "log_type": log_type,
                    "candidate_tg_id": candidate_tg_id,
                },
            )
        except Exception:
            logger.exception(
                "notification.log.persist_failed",
                extra={
                    "booking_id": item.booking_id,
                    "log_type": log_type,
                    "candidate_tg_id": candidate_tg_id,
                },
            )
        logger.warning(
            "notification.worker.retry_scheduled",
            extra={
                "outbox_id": item.id,
                "booking_id": item.booking_id,
                "candidate_tg_id": candidate_tg_id,
                "notification_type": notification_type,
                "log_type": log_type,
                "attempt": attempt,
                "error": error,
                "delay_seconds": round(delay, 2),
                "next_retry_at": next_retry_at.isoformat() if next_retry_at else None,
                "log_created": created,
            },
        )
        await self._enqueue_outbox(item.id, attempt=max(attempt, item.attempts), delay=delay)
        if count_failure:
            await record_notification_failed(notification_type)
        await record_send_retry()

    def _compute_retry_delay(self, attempt: int) -> float:
        base = self._retry_base * (2 ** max(0, attempt - 1))
        return float(min(self._retry_max, base))

    def _apply_jitter(self, delay: float) -> float:
        return max(1.0, delay * random.uniform(0.85, 1.15))

    async def _throttle(self) -> None:
        if self._token_bucket is None:
            return
        await self._token_bucket.consume()

    def _is_circuit_open(self) -> bool:
        return time.monotonic() < self._breaker_open_until

    def _breaker_remaining(self) -> float:
        remaining = self._breaker_open_until - time.monotonic()
        return max(0.0, remaining)

    def _open_circuit(self) -> None:
        low, high = self._breaker_window
        duration = random.uniform(low, high)
        self._breaker_open_until = max(self._breaker_open_until, time.monotonic() + duration)
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(record_circuit_open())
        except RuntimeError:
            pass


class _TokenBucket:
    def __init__(self, rate_per_sec: float, capacity: int) -> None:
        self._rate = max(rate_per_sec, 0.1)
        self._capacity = float(max(1, capacity))
        self._tokens = self._capacity
        self._updated = time.monotonic()
        self._lock = asyncio.Lock()

    async def consume(self, tokens: float = 1.0) -> None:
        tokens = max(tokens, 0.0)
        while True:
            async with self._lock:
                now = time.monotonic()
                delta = now - self._updated
                if delta > 0:
                    self._tokens = min(self._capacity, self._tokens + delta * self._rate)
                    self._updated = now
                if self._tokens >= tokens:
                    self._tokens -= tokens
                    return
                deficit = tokens - self._tokens
                wait_time = deficit / self._rate if self._rate else 0.1
            await asyncio.sleep(max(wait_time, 0.05))


def configure_notification_service(service: NotificationService) -> None:
    global _notification_service
    _notification_service = service
    service.start()


def get_notification_service() -> NotificationService:
    if _notification_service is None:
        raise RuntimeError("Notification service is not configured")
    return _notification_service


@dataclass
class Test1AnswerResult:
    status: Literal["ok", "invalid", "reject"]
    message: Optional[str] = None
    hints: List[str] = field(default_factory=list)
    reason: Optional[str] = None
    template_key: Optional[str] = None
    template_context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SlotSnapshot:
    slot_id: int
    start_utc: datetime
    candidate_id: Optional[int]
    candidate_fio: str
    candidate_tz: str
    candidate_city_id: Optional[int]
    recruiter_id: Optional[int]
    recruiter_name: str
    recruiter_tz: str
    slot_tz: str = DEFAULT_TZ
    city_name: str = ""


class BookingNotificationStatus(str, Enum):
    APPROVED = "approved"
    RESCHEDULE_REQUESTED = "reschedule_requested"
    CANCELLED = "cancelled"


REJECTION_TEMPLATES: Dict[str, str] = {
    "format_not_ready": "t1_format_reject",
    "schedule_conflict": "t1_schedule_reject",
    "study_flex_declined": "t1_schedule_reject",
}


async def _resolve_candidate_city(answer: str, metadata: Dict[str, Any]) -> Optional[CityInfo]:
    meta_city_id = metadata.get("city_id") or metadata.get("value")
    if meta_city_id is not None:
        try:
            city = await find_candidate_city_by_id(int(meta_city_id))
            if city is not None:
                return city
        except (TypeError, ValueError):
            pass

    meta_label = metadata.get("name") or metadata.get("label")
    if isinstance(meta_label, str):
        city = await find_candidate_city_by_name(meta_label)
        if city is not None:
            return city

    if answer:
        city = await find_candidate_city_by_name(answer)
        if city is not None:
            return city

    return None


def _validation_feedback(qid: str, exc: ValidationError) -> Tuple[str, List[str]]:
    hints: List[str] = []
    if qid == "fio":
        return (
            "Укажите полные фамилию, имя и отчество кириллицей.",
            ["Иванов Иван Иванович", "Петрова Мария Сергеевна"],
        )
    if qid == "age":
        return (
            "Возраст должен быть от 18 до 60 лет. Укажите возраст цифрами.",
            ["Например: 23"],
        )
    if qid in {"status", "format", FOLLOWUP_STUDY_MODE["id"], FOLLOWUP_STUDY_SCHEDULE["id"], FOLLOWUP_STUDY_FLEX["id"]}:
        return ("Выберите один из вариантов в списке.", hints)

    errors = exc.errors()
    if errors:
        return (errors[0].get("msg", "Проверьте ответ."), hints)
    return ("Проверьте ответ.", hints)


def _should_insert_study_flex(validated: Test1Payload, schedule_answer: str) -> bool:
    study_mode = (validated.study_mode or "").lower()
    if "очно" not in study_mode:
        return False
    normalized = schedule_answer.strip()
    if normalized == "Нет, не смогу":
        return False
    return normalized in {
        "Да, смогу",
        "Смогу, но нужен запас по времени",
        "Будет сложно",
    }


def _determine_test1_branch(
    qid: str,
    answer: str,
    payload: Test1Payload,
) -> Optional[Test1AnswerResult]:
    if qid == "format" and answer.strip() == "Пока не готов":
        return Test1AnswerResult(
            status="reject",
            reason="format_not_ready",
            template_key=REJECTION_TEMPLATES["format_not_ready"],
        )

    if qid == "format" and answer.strip() == "Нужен гибкий график":
        return Test1AnswerResult(
            status="ok",
            template_key="t1_format_clarify",
        )

    if qid == FOLLOWUP_STUDY_SCHEDULE["id"]:
        normalized = answer.strip()
        normalized_lower = normalized.lower()
        if normalized in {"Нет, не смогу", "Будет сложно"} or normalized_lower in {
            "нет, не смогу",
            "будет сложно",
        }:
            return Test1AnswerResult(
                status="reject",
                reason="schedule_conflict",
                template_key=REJECTION_TEMPLATES["schedule_conflict"],
            )

    if qid == FOLLOWUP_STUDY_FLEX["id"]:
        if answer.strip().lower().startswith("нет"):
            return Test1AnswerResult(
                status="reject",
                reason="study_flex_declined",
                template_key=REJECTION_TEMPLATES["study_flex_declined"],
            )

    return None


def _format_validation_feedback(result: Test1AnswerResult) -> str:
    lines = [result.message or "Проверьте ответ."]
    if result.hints:
        lines.append("")
        lines.append("Примеры:")
        lines.extend(f"• {hint}" for hint in result.hints)
    return "\n".join(lines)


async def _handle_test1_rejection(user_id: int, result: Test1AnswerResult) -> None:
    state_manager = get_state_manager()
    state = await state_manager.get(user_id) or {}
    city_id = state.get("city_id")
    template_key = result.template_key or REJECTION_TEMPLATES.get(result.reason or "", "")
    context = dict(result.template_context)
    context.pop("city_id", None)
    context.setdefault("city_name", state.get("city_name") or "")
    message = await templates.tpl(city_id, template_key or "t1_schedule_reject", **context)
    if not message:
        message = (
            "Спасибо за ответы! На данном этапе мы не продолжаем процесс."
        )

    await get_bot().send_message(user_id, message)
    await record_test1_rejection(result.reason or "unknown")
    logger.info(
        "Test1 rejection emitted",
        extra={
            "user_id": user_id,
            "reason": result.reason,
            "city_id": city_id,
            "city_name": state.get("city_name"),
        },
    )
    await state_manager.delete(user_id)


async def _resolve_followup_message(
    result: Test1AnswerResult, state: State | Dict[str, Any]
) -> Optional[str]:
    if result.template_key is None and not result.message:
        return None

    template_context = dict(result.template_context)
    city_id = template_context.pop("city_id", None)
    if city_id is None and isinstance(state, dict):
        city_id = state.get("city_id")

    if result.template_key:
        text = await templates.tpl(city_id, result.template_key, **template_context)
        if text:
            return text

    return result.message


async def _notify_existing_reservation(callback: CallbackQuery, slot: Slot) -> None:
    user_id = callback.from_user.id
    state_manager = get_state_manager()
    state = await state_manager.get(user_id) or {}
    tz = state.get("candidate_tz") or slot.candidate_tz or DEFAULT_TZ
    labels = slot_local_labels(slot.start_utc, tz)
    message = await templates.tpl(
        getattr(slot, "candidate_city_id", None),
        "existing_reservation",
        recruiter_name=slot.recruiter.name if slot.recruiter else "",
        dt=labels["slot_datetime_local"],
    )
    await callback.answer("Бронь уже оформлена", show_alert=True)
    await get_bot().send_message(user_id, message)


def configure(
    bot: Optional[Bot],
    state_manager: StateManager,
    dispatcher: Optional["Dispatcher"] = None,
) -> None:
    global _bot, _state_manager
    _bot = bot
    _state_manager = state_manager
    if dispatcher is not None:
        logger.debug(
            "Dispatcher argument provided to configure(); interview events use internal handlers registry.",
            extra={"dispatcher": type(dispatcher).__name__},
        )


def get_bot() -> Bot:
    if _bot is None:
        raise RuntimeError("Bot is not configured")
    return _bot


def get_state_manager() -> StateManager:
    if _state_manager is None:
        raise RuntimeError("State manager is not configured")
    return _state_manager

async def set_pending_test2(candidate_id: int, context: Dict[str, object]) -> None:
    state_manager = get_state_manager()

    def _update(state: State) -> Tuple[State, None]:
        pending = dict(state.get("pending_test2") or {})
        pending.update(context)
        state["pending_test2"] = pending
        return state, None

    await state_manager.atomic_update(candidate_id, _update)


async def dispatch_interview_success(event: InterviewSuccessEvent) -> None:
    importlib.import_module("backend.apps.bot.handlers.interview")

    if not _interview_success_handlers:
        logger.warning("No interview success handlers registered; skipping dispatch.")
        return

    errors: List[BaseException] = []
    for handler in list(_interview_success_handlers):
        try:
            await handler(event)
        except Exception as exc:  # pragma: no cover - handler safety net
            logger.exception(
                "Interview success handler %r failed",
                handler,
                extra={"candidate_id": event.candidate_id},
            )
            errors.append(exc)

    if errors:
        raise errors[0]


async def _begin_test2_flow(
    candidate_id: int,
    candidate_tz: str,
    candidate_city_id: Optional[int],
    candidate_name: str,
    previous_state: Optional[Dict[str, object]] = None,
) -> None:
    state_manager = get_state_manager()
    base_state = previous_state or (await state_manager.get(candidate_id) or {})

    sequence = base_state.get("t1_sequence")
    if sequence:
        try:
            sequence = list(sequence)
        except TypeError:
            sequence = list(TEST1_QUESTIONS)
    else:
        sequence = list(TEST1_QUESTIONS)

    new_state: Dict[str, object] = {
        "flow": "intro",
        "t1_idx": None,
        "t1_current_idx": None,
        "test1_answers": base_state.get("test1_answers", {}),
        "t1_last_prompt_id": None,
        "t1_last_question_text": "",
        "t1_requires_free_text": False,
        "t1_sequence": sequence,
        "fio": base_state.get("fio", candidate_name or ""),
        "city_name": base_state.get("city_name", ""),
        "city_id": base_state.get("city_id", candidate_city_id),
        "candidate_tz": candidate_tz,
        "t2_attempts": {},
        "picked_recruiter_id": None,
        "picked_slot_id": None,
    }

    await state_manager.set(candidate_id, new_state)
    await start_test2(candidate_id)


async def launch_test2(candidate_id: int) -> None:
    state_manager = get_state_manager()
    previous_state = await state_manager.get(candidate_id) or {}
    pending: Dict[str, Any] = dict(previous_state.get("pending_test2") or {})

    if not pending and previous_state.get("flow") == "intro":
        return

    candidate_tz = pending.get("candidate_tz") or previous_state.get("candidate_tz") or DEFAULT_TZ
    candidate_city_id = pending.get("candidate_city_id") or previous_state.get("city_id")
    candidate_name = pending.get("candidate_name") or previous_state.get("fio") or ""

    def _clear(state: State) -> Tuple[State, None]:
        state.pop("pending_test2", None)
        return state, None

    await state_manager.atomic_update(candidate_id, _clear)
    await _begin_test2_flow(
        candidate_id,
        candidate_tz,
        candidate_city_id,
        candidate_name,
        previous_state=previous_state,
    )


def _safe_zone(tz: Optional[str]) -> ZoneInfo:
    try:
        return ZoneInfo(tz or DEFAULT_TZ)
    except Exception:
        return ZoneInfo(DEFAULT_TZ)


def fmt_dt_local(dt_utc: datetime, tz: str) -> str:
    return dt_utc.astimezone(_safe_zone(tz)).strftime(TIME_FMT)


def slot_local_labels(dt_utc: datetime, tz: str) -> Dict[str, str]:
    local_dt = dt_utc.astimezone(_safe_zone(tz))
    return {
        "slot_date_local": local_dt.strftime("%d.%m"),
        "slot_time_local": local_dt.strftime("%H:%M"),
        "slot_datetime_local": local_dt.strftime("%d.%m %H:%M"),
    }


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def create_progress_bar(current: int, total: int) -> str:
    filled = max(0, min(10, math.ceil((current / total) * 10)))
    return f"[{'🟩' * filled}{'⬜️' * (10 - filled)}]"


def calculate_score(attempts: Dict[int, Dict[str, Any]]) -> float:
    base_score = sum(1 for q in attempts if attempts[q]["is_correct"])
    penalty = sum(
        0.1 * (len(attempts[q]["answers"]) - 1)
        + (0.2 if any(a["overtime"] for a in attempts[q]["answers"]) else 0)
        for q in attempts
    )
    return max(0.0, round(base_score - penalty, 1))


async def safe_edit_text_or_caption(cb_msg, text: str) -> None:
    """Безопасно меняет текст сообщения или подпись медиа."""
    try:
        if (cb_msg.document is not None) or (cb_msg.photo is not None) or (
            cb_msg.video is not None
        ) or (cb_msg.animation is not None):
            await cb_msg.edit_caption(text)
        else:
            await cb_msg.edit_text(text)
    except TelegramBadRequest:
        pass


async def safe_remove_reply_markup(cb_msg) -> None:
    try:
        await cb_msg.edit_reply_markup(reply_markup=None)
    except TelegramBadRequest:
        pass


async def _cancel_reminders_for_slot(slot_id: int) -> None:
    try:
        reminder_service = get_reminder_service()
    except RuntimeError:
        reminder_service = None
    if reminder_service is not None:
        await reminder_service.cancel_for_slot(slot_id)


async def _build_slot_snapshot(slot: Slot) -> SlotSnapshot:
    recruiter = None
    if slot.recruiter_id is not None:
        recruiter = await get_recruiter(slot.recruiter_id)
    recruiter_name = recruiter.name if recruiter else ""
    recruiter_tz = (recruiter.tz if recruiter and recruiter.tz else DEFAULT_TZ)
    candidate_tz = slot.candidate_tz or DEFAULT_TZ
    candidate_id = int(slot.candidate_tg_id) if slot.candidate_tg_id is not None else None
    slot_tz = getattr(slot, "tz_name", None)
    city_name = ""
    if slot.city_id:
        try:
            city = await get_city(slot.city_id)
        except Exception:
            city = None
        if city is not None:
            city_name = getattr(city, "name_plain", None) or getattr(city, "name", "")
            city_tz = getattr(city, "tz", None)
            if not slot_tz and city_tz:
                slot_tz = city_tz
    if not slot_tz and recruiter_tz:
        slot_tz = recruiter_tz
    if not slot_tz:
        slot_tz = DEFAULT_TZ
    return SlotSnapshot(
        slot_id=slot.id,
        start_utc=slot.start_utc,
        candidate_id=candidate_id,
        candidate_fio=slot.candidate_fio or "",
        candidate_tz=candidate_tz,
        candidate_city_id=getattr(slot, "candidate_city_id", None),
        recruiter_id=slot.recruiter_id,
        recruiter_name=recruiter_name,
        recruiter_tz=recruiter_tz,
        slot_tz=slot_tz,
        city_name=city_name,
    )


def _snapshot_payload(snapshot: SlotSnapshot) -> Dict[str, Any]:
    return {
        "slot_id": snapshot.slot_id,
        "start_utc": snapshot.start_utc.isoformat(),
        "candidate_id": snapshot.candidate_id,
        "candidate_fio": snapshot.candidate_fio,
        "candidate_tz": snapshot.candidate_tz,
        "candidate_city_id": snapshot.candidate_city_id,
        "recruiter_id": snapshot.recruiter_id,
        "recruiter_name": snapshot.recruiter_name,
        "recruiter_tz": snapshot.recruiter_tz,
        "slot_tz": snapshot.slot_tz,
        "city_name": snapshot.city_name,
    }


def _snapshot_from_payload(payload: Optional[Dict[str, Any]]) -> Optional[SlotSnapshot]:
    if not payload:
        return None

    start_raw = payload.get("start_utc")
    try:
        start_utc = datetime.fromisoformat(start_raw) if isinstance(start_raw, str) else None
    except ValueError:
        start_utc = None

    if start_utc is None:
        return None

    candidate_tz = payload.get("candidate_tz") or DEFAULT_TZ
    slot_tz = payload.get("slot_tz") or candidate_tz or DEFAULT_TZ

    return SlotSnapshot(
        slot_id=int(payload.get("slot_id") or 0),
        start_utc=start_utc,
        candidate_id=payload.get("candidate_id"),
        candidate_fio=str(payload.get("candidate_fio") or ""),
        candidate_tz=str(candidate_tz),
        candidate_city_id=payload.get("candidate_city_id"),
        recruiter_id=payload.get("recruiter_id"),
        recruiter_name=str(payload.get("recruiter_name") or ""),
        recruiter_tz=str(payload.get("recruiter_tz") or DEFAULT_TZ),
        slot_tz=str(slot_tz),
        city_name=str(payload.get("city_name") or ""),
    )


async def _load_candidate_state(candidate_id: int) -> State:
    try:
        state_manager = get_state_manager()
    except RuntimeError:
        return {}
    return await state_manager.get(candidate_id) or {}


async def _update_candidate_state(candidate_id: int, updater) -> None:
    try:
        state_manager = get_state_manager()
    except RuntimeError:
        return
    await state_manager.atomic_update(candidate_id, updater)


async def _send_reschedule_prompt(snapshot: SlotSnapshot) -> bool:
    if snapshot.candidate_id is None:
        return False

    def _clear_slot(st: State) -> Tuple[State, None]:
        st["picked_slot_id"] = None
        return st, None

    await _update_candidate_state(snapshot.candidate_id, _clear_slot)

    notice = await templates.tpl(
        snapshot.candidate_city_id,
        "slot_reschedule",
        recruiter_name=snapshot.recruiter_name or "",
        dt=fmt_dt_local(snapshot.start_utc, snapshot.candidate_tz or DEFAULT_TZ),
    )

    try:
        await show_recruiter_menu(snapshot.candidate_id, notice=notice)
        return True
    except RuntimeError:
        logger.warning("Bot is not configured; cannot send reschedule prompt")
    except Exception:
        logger.exception("Failed to send reschedule prompt")
    return False


async def _send_final_rejection_notice(snapshot: SlotSnapshot) -> bool:
    if snapshot.candidate_id is None:
        return False

    state = await _load_candidate_state(snapshot.candidate_id)
    context = {
        "candidate_fio": snapshot.candidate_fio or state.get("fio", ""),
        "city_name": state.get("city_name") or "",
        "recruiter_name": snapshot.recruiter_name or "",
    }
    text = await templates.tpl(snapshot.candidate_city_id, "result_fail", **context)
    text = text.strip()
    if not text:
        logger.warning("Rejection template produced empty message for candidate %s", snapshot.candidate_id)
        return False

    try:
        await get_bot().send_message(snapshot.candidate_id, text)
        def _mark_rejected(st: State) -> Tuple[State, None]:
            st["flow"] = "rejected"
            st["picked_slot_id"] = None
            st["picked_recruiter_id"] = None
            return st, None

        await _update_candidate_state(snapshot.candidate_id, _mark_rejected)
        return True
    except RuntimeError:
        logger.warning("Bot is not configured; cannot send rejection message")
    except Exception:
        logger.exception("Failed to send rejection message")
    return False


async def capture_slot_snapshot(slot: Slot) -> SlotSnapshot:
    """Return a lightweight snapshot of slot and candidate data."""

    return await _build_slot_snapshot(slot)


async def cancel_slot_reminders(slot_id: int) -> None:
    """Cancel reminder jobs for the provided slot."""

    await _cancel_reminders_for_slot(slot_id)


async def notify_reschedule(snapshot: SlotSnapshot) -> bool:
    """Notify candidate about reschedule request."""

    return await _send_reschedule_prompt(snapshot)


async def notify_rejection(snapshot: SlotSnapshot) -> bool:
    """Notify candidate about rejection."""

    return await _send_final_rejection_notice(snapshot)


async def _share_test1_with_recruiters(user_id: int, state: State, form_path: Path) -> bool:
    city_id = state.get("city_id")
    try:
        recruiters = await get_active_recruiters_for_city(city_id) if city_id else []
    except Exception:
        recruiters = []

    recipients: List[Any] = []
    seen_chats: set[Any] = set()
    for rec in recruiters:
        chat_id = getattr(rec, "tg_chat_id", None)
        if not chat_id:
            continue
        if chat_id in seen_chats:
            continue
        recipients.append(rec)
        seen_chats.add(chat_id)
    if not recipients:
        return False

    bot = get_bot()
    candidate_name = state.get("fio") or str(user_id)
    city_name = state.get("city_name") or "—"
    caption = (
        "📋 <b>Кандидат прошел Тест 1, но не выбрал время собеседования</b>\n"
        f"👤 {candidate_name}\n"
        f"📍 {city_name}\n"
        f"TG: {user_id}\n\n"
        "⚠️ <b>Требуется связаться вручную</b> для назначения собеседования."
    )

    attachments = [
        form_path,
        REPORTS_DIR / f"report_{state.get('fio') or user_id}.txt",
    ]

    delivered = False
    for recruiter in recipients:
        sent = False
        for path in attachments:
            if not path.exists():
                continue
            try:
                await bot.send_document(
                    recruiter.tg_chat_id,
                    FSInputFile(str(path)),
                    caption=caption,
                )
                sent = True
                delivered = True
                break
            except Exception:
                logger.exception(
                    "Failed to deliver Test 1 attachment to recruiter %s", recruiter.id
                )
        if sent:
            continue
        try:
            await bot.send_message(recruiter.tg_chat_id, caption)
            delivered = True
        except Exception:
            logger.exception(
                "Failed to send Test 1 summary to recruiter %s", recruiter.id
            )
    return delivered


async def begin_interview(user_id: int, username: Optional[str] = None) -> None:
    state_manager = get_state_manager()
    bot = get_bot()
    await state_manager.set(
        user_id,
        State(
            flow="interview",
            t1_idx=0,
            test1_answers={},
            t1_last_prompt_id=None,
            t1_last_question_text="",
            t1_requires_free_text=True,
            t1_sequence=list(TEST1_QUESTIONS),
            fio="",
            city_name="",
            city_id=None,
            candidate_tz=DEFAULT_TZ,
            t2_attempts={},
            picked_recruiter_id=None,
            picked_slot_id=None,
            test1_payload={},
            username=username or "",  # Save username for later use
        ),
    )
    intro = await templates.tpl(None, "t1_intro")
    await bot.send_message(user_id, intro)
    await send_test1_question(user_id)


async def send_welcome(user_id: int) -> None:
    bot = get_bot()
    text = (
        "👋 Добро пожаловать!\n"
        "Нажмите «Начать», чтобы заполнить мини-анкету и выбрать время для интервью."
    )
    await bot.send_message(user_id, text, reply_markup=kb_start())


async def handle_recruiter_identity_command(message: Message) -> None:
    """Process the `/iam` command sent by a recruiter."""

    text = (message.text or "").strip()
    _, _, args = text.partition(" ")
    name_hint = args.strip()
    if not name_hint:
        await message.answer("Используйте команду в формате: /iam <Имя>")
        return

    updated = await set_recruiter_chat_id_by_command(name_hint, chat_id=message.chat.id)
    if not updated:
        await message.answer(
            "Рекрутер не найден. Убедитесь, что имя совпадает с записью в системе."
        )
        return

    await message.answer(
        "Готово! Уведомления о брони и подтверждениях будут приходить в этот чат."
    )


async def start_introday_flow(message: Message) -> None:
    state_manager = get_state_manager()
    user_id = message.from_user.id
    prev = await state_manager.get(user_id) or {}
    await state_manager.set(
        user_id,
        State(
            flow="intro",
            t1_idx=None,
            test1_answers=prev.get("test1_answers", {}),
            t1_last_prompt_id=None,
            t1_last_question_text="",
            t1_requires_free_text=False,
            t1_sequence=prev.get("t1_sequence", list(TEST1_QUESTIONS)),
            fio=prev.get("fio", ""),
            city_name=prev.get("city_name", ""),
            city_id=prev.get("city_id"),
            candidate_tz=prev.get("candidate_tz", DEFAULT_TZ),
            t2_attempts={},
            picked_recruiter_id=None,
            picked_slot_id=None,
            test1_payload=prev.get("test1_payload", {}),
            format_choice=prev.get("format_choice"),
            study_mode=prev.get("study_mode"),
            study_schedule=prev.get("study_schedule"),
            study_flex=prev.get("study_flex"),
        ),
    )
    await start_test2(user_id)


def _format_prompt(prompt: Any) -> str:
    if isinstance(prompt, (list, tuple)):
        return "\n".join(str(p) for p in prompt)
    return str(prompt)


async def send_test1_question(user_id: int) -> None:
    bot = get_bot()
    state_manager = get_state_manager()
    def _prepare(state: State) -> Tuple[State, Dict[str, Any]]:
        working = state
        sequence = list(working.get("t1_sequence") or TEST1_QUESTIONS)
        working["t1_sequence"] = sequence
        idx = int(working.get("t1_idx") or 0)
        total = len(sequence)
        if idx >= total:
            return working, {"done": True}
        question = dict(sequence[idx])
        sequence[idx] = question
        return working, {
            "done": False,
            "idx": idx,
            "total": total,
            "question": question,
            "city_id": working.get("city_id"),
        }

    ctx = await state_manager.atomic_update(user_id, _prepare)
    if ctx.get("done"):
        await finalize_test1(user_id)
        return

    idx = ctx["idx"]
    total = ctx["total"]
    question: Dict[str, Any] = ctx["question"]
    city_id = ctx.get("city_id")

    progress = await templates.tpl(city_id, "t1_progress", n=idx + 1, total=total)
    progress_bar = create_progress_bar(idx, total)
    helper = question.get("helper")
    base_text = f"{progress}\n{progress_bar}\n\n{_format_prompt(question['prompt'])}"
    if helper:
        base_text += f"\n\n<i>{helper}</i>"

    resolved_options = await _resolve_test1_options(question)
    if resolved_options is not None:
        question["options"] = resolved_options

        def _attach_options(state: State) -> Tuple[State, None]:
            sequence = list(state.get("t1_sequence") or [])
            if idx < len(sequence):
                stored = dict(sequence[idx])
                stored["options"] = resolved_options
                sequence[idx] = stored
                state["t1_sequence"] = sequence
            return state, None

        await state_manager.atomic_update(user_id, _attach_options)

    options = question.get("options") or []
    if options:
        markup = _build_test1_options_markup(idx, options)
        sent = await bot.send_message(user_id, base_text, reply_markup=markup)
        requires_free_text = False
    else:
        placeholder = question.get("placeholder", "Введите ответ…")[:64]
        sent = await bot.send_message(
            user_id,
            base_text,
            reply_markup=ForceReply(selective=True, input_field_placeholder=placeholder),
        )
        requires_free_text = True

    def _store_prompt(state: State) -> Tuple[State, None]:
        state["t1_last_prompt_id"] = sent.message_id
        state["t1_last_question_text"] = base_text
        state["t1_current_idx"] = idx
        state["t1_requires_free_text"] = requires_free_text
        return state, None

    await state_manager.atomic_update(user_id, _store_prompt)


def _build_test1_options_markup(question_idx: int, options: List[Any]) -> Optional[Any]:
    if not options:
        return None
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

    buttons = []
    for opt_idx, option in enumerate(options):
        buttons.append(
            [
                InlineKeyboardButton(
                    text=_extract_option_label(option),
                    callback_data=f"t1opt:{question_idx}:{opt_idx}",
                )
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def _extract_option_label(option: Any) -> str:
    if isinstance(option, dict):
        return str(option.get("label") or option.get("text") or option.get("value"))
    if isinstance(option, (tuple, list)) and option:
        return str(option[0])
    return str(option)


def _extract_option_value(option: Any) -> str:
    if isinstance(option, dict):
        return str(option.get("value") or option.get("label") or option.get("text"))
    if isinstance(option, (tuple, list)):
        return str(option[1] if len(option) > 1 else option[0])
    return str(option)


async def _resolve_test1_options(question: Dict[str, Any]) -> Optional[List[Any]]:
    qid = question.get("id")
    if qid == "city":
        cities = await list_candidate_cities()
        return [
            {
                "label": city.display_name or city.name_plain,
                "value": city.name_plain,
                "city_id": city.id,
                "tz": city.tz,
                "name": city.name_plain,
            }
            for city in cities
        ]
    return None


def _shorten_answer(text: str, limit: int = 80) -> str:
    clean = text.strip()
    if len(clean) <= limit:
        return clean
    return clean[: limit - 1] + "…"


async def _mark_test1_question_answered(user_id: int, summary: str) -> None:
    bot = get_bot()
    state_manager = get_state_manager()
    state = await state_manager.get(user_id)
    if not state:
        return
    prompt_id = state.get("t1_last_prompt_id")
    if not prompt_id:
        return
    base_text = state.get("t1_last_question_text") or ""
    updated = f"{base_text}\n\n✅ <i>{html.escape(summary)}</i>"
    try:
        await bot.edit_message_text(updated, chat_id=user_id, message_id=prompt_id)
    except TelegramBadRequest:
        pass

    def _cleanup(st: State) -> Tuple[State, None]:
        st["t1_last_prompt_id"] = None
        st["t1_last_question_text"] = ""
        st["t1_requires_free_text"] = False
        return st, None

    await state_manager.atomic_update(user_id, _cleanup)


def _recruiter_header(name: str, tz_label: str) -> str:
    return (
        f"👤 <b>{name}</b>\n"
        f"🕒 Время отображается в вашем поясе: <b>{tz_label}</b>.\n"
        "Выберите удобное окно:"
    )


async def save_test1_answer(
    user_id: int,
    question: Dict[str, Any],
    answer: str,
    *,
    metadata: Optional[Dict[str, Any]] = None,
) -> Test1AnswerResult:
    state_manager = get_state_manager()
    state = await state_manager.get(user_id) or {}
    qid = str(question.get("id") or "")
    meta = metadata or {}
    payload_data: Dict[str, Any] = dict(state.get("test1_payload") or {})
    answer_clean = answer.strip()

    city_info = None
    should_insert_flex = False

    if qid == "fio":
        payload_data["fio"] = answer_clean
    elif qid == "city":
        city_info = await _resolve_candidate_city(answer_clean, meta)
        if city_info is None:
            city_names = [city.name for city in await list_candidate_cities()][:5]
            return Test1AnswerResult(
                status="invalid",
                message="Пока работаем в указанных городах. Выберите подходящий вариант из списка.",
                hints=city_names,
            )
        payload_data["city_id"] = city_info.id
        payload_data["city_name"] = city_info.name
    elif qid == "age":
        try:
            payload_data["age"] = convert_age(answer_clean)
        except ValueError as exc:
            return Test1AnswerResult(
                status="invalid",
                message=str(exc),
                hints=["Например: 23", "Возраст указываем цифрами"],
            )
    elif qid == "status":
        payload_data["status"] = answer
    elif qid == "format":
        payload_data["format_choice"] = answer
    elif qid == FOLLOWUP_STUDY_MODE["id"]:
        payload_data["study_mode"] = answer
    elif qid == FOLLOWUP_STUDY_SCHEDULE["id"]:
        payload_data["study_schedule"] = answer
    elif qid == FOLLOWUP_STUDY_FLEX["id"]:
        payload_data["study_flex"] = answer

    try:
        validated_model = apply_partial_validation(payload_data)
    except ValidationError as exc:
        message, hints = _validation_feedback(qid, exc)
        return Test1AnswerResult(status="invalid", message=message, hints=hints)

    if qid == FOLLOWUP_STUDY_SCHEDULE["id"]:
        should_insert_flex = _should_insert_study_flex(validated_model, answer)

    current_idx = int(state.get("t1_current_idx", state.get("t1_idx", 0)) or 0)

    def _apply(state: State) -> Tuple[State, Dict[str, Any]]:
        working = state
        answers = working.setdefault("test1_answers", {})
        sequence = list(working.get("t1_sequence") or TEST1_QUESTIONS)
        working["t1_sequence"] = sequence

        if qid == "fio":
            working["fio"] = validated_model.fio or answer
        elif qid == "city" and city_info is not None:
            working["city_name"] = city_info.name
            working["city_id"] = city_info.id
            working["candidate_tz"] = city_info.tz or DEFAULT_TZ
            answers[qid] = city_info.name
        elif qid == "age":
            answers[qid] = str(payload_data.get("age", answer))
        elif qid == "status":
            answers[qid] = answer
            insert_pos = current_idx + 1
            existing_ids = {item.get("id") for item in sequence}

            lowered = answer.lower()
            if "работ" in lowered:
                if FOLLOWUP_NOTICE_PERIOD["id"] not in existing_ids:
                    sequence.insert(insert_pos, FOLLOWUP_NOTICE_PERIOD.copy())
                    existing_ids.add(FOLLOWUP_NOTICE_PERIOD["id"])
                    insert_pos += 1
            elif "уч" in lowered:
                if FOLLOWUP_STUDY_MODE["id"] not in existing_ids:
                    sequence.insert(insert_pos, FOLLOWUP_STUDY_MODE.copy())
                    existing_ids.add(FOLLOWUP_STUDY_MODE["id"])
                    insert_pos += 1
                if FOLLOWUP_STUDY_SCHEDULE["id"] not in existing_ids:
                    sequence.insert(insert_pos, FOLLOWUP_STUDY_SCHEDULE.copy())
                    existing_ids.add(FOLLOWUP_STUDY_SCHEDULE["id"])
        else:
            if qid:
                answers[qid] = answer

        if qid == FOLLOWUP_STUDY_MODE["id"]:
            answers[qid] = answer
        if qid == FOLLOWUP_STUDY_SCHEDULE["id"]:
            answers[qid] = answer
            if should_insert_flex:
                existing_ids = {item.get("id") for item in sequence}
                if FOLLOWUP_STUDY_FLEX["id"] not in existing_ids:
                    sequence.insert(current_idx + 1, FOLLOWUP_STUDY_FLEX.copy())
        if qid == FOLLOWUP_STUDY_FLEX["id"]:
            answers[qid] = answer

        working["test1_answers"] = answers
        working["test1_payload"] = validated_model.model_dump(exclude_none=True)

        if qid == "city" and city_info is not None:
            working.setdefault("candidate_tz", city_info.tz or DEFAULT_TZ)

        if validated_model.format_choice is not None:
            working["format_choice"] = validated_model.format_choice
        if validated_model.study_mode is not None:
            working["study_mode"] = validated_model.study_mode
        if validated_model.study_schedule is not None:
            working["study_schedule"] = validated_model.study_schedule
        if validated_model.study_flex is not None:
            working["study_flex"] = validated_model.study_flex

        return working, {
            "city_id": working.get("city_id"),
            "city_name": working.get("city_name"),
        }

    update_info = await state_manager.atomic_update(user_id, _apply)

    branch = _determine_test1_branch(qid, answer, validated_model)
    if branch is not None:
        if not branch.template_key:
            branch.template_key = REJECTION_TEMPLATES.get(branch.reason or "", "")
        if "city_name" not in branch.template_context and update_info.get("city_name"):
            branch.template_context["city_name"] = update_info.get("city_name")
        if validated_model.fio and "fio" not in branch.template_context:
            branch.template_context["fio"] = validated_model.fio
        if update_info.get("city_id") is not None:
            branch.template_context.setdefault("city_id", update_info.get("city_id"))
        return branch

    return Test1AnswerResult(status="ok")


async def handle_test1_answer(message: Message) -> None:
    user_id = message.from_user.id
    state_manager = get_state_manager()
    state = await state_manager.get(user_id)
    if not state or state.get("flow") != "interview":
        return

    # Update username if available (for existing users)
    username = getattr(message.from_user, "username", None)
    if username and state.get("username") != username:
        def _update_username(st: State) -> Tuple[State, None]:
            st["username"] = username
            return st, None
        await state_manager.atomic_update(user_id, _update_username)

    idx = state.get("t1_current_idx", state.get("t1_idx", 0))
    sequence = state.get("t1_sequence") or list(TEST1_QUESTIONS)
    total = len(sequence)
    if idx >= total:
        return

    question = sequence[idx]
    if not state.get("t1_requires_free_text", True):
        await message.reply(
            "Пожалуйста, выберите вариант ответа с помощью кнопок под вопросом."
        )
        return

    prompt_id = state.get("t1_last_prompt_id")
    if prompt_id:
        reply = message.reply_to_message
        if not reply or reply.message_id != prompt_id:
            await message.reply(
                "Нажмите «Ответить» на сообщение с вопросом, чтобы зафиксировать ответ."
            )
            return

    answer_text = (message.text or "").strip()
    if not answer_text:
        await message.reply("Ответ не распознан. Напишите текст или выберите вариант.")
        return

    result = await save_test1_answer(user_id, question, answer_text)

    if result.status == "invalid":
        feedback = _format_validation_feedback(result)
        await message.reply(feedback)
        return

    updated_state = await state_manager.get(user_id) or {}

    if result.status == "reject":
        await _handle_test1_rejection(user_id, result)
        return

    followup_text = await _resolve_followup_message(result, updated_state)
    if followup_text:
        await message.answer(followup_text)

    await _mark_test1_question_answered(user_id, _shorten_answer(answer_text))

    def _advance(st: State) -> Tuple[State, Dict[str, int]]:
        working = st
        sequence_local = list(working.get("t1_sequence") or TEST1_QUESTIONS)
        working["t1_sequence"] = sequence_local
        current = int(working.get("t1_current_idx", working.get("t1_idx", 0)) or 0)
        if current != idx:
            return working, {"advanced": 0, "total": len(sequence_local)}
        next_idx = idx + 1
        working["t1_idx"] = next_idx
        return working, {"advanced": 1, "total": len(sequence_local), "next_idx": next_idx}

    advance_info = await state_manager.atomic_update(user_id, _advance)
    if not advance_info.get("advanced"):
        return

    next_idx = advance_info.get("next_idx", idx + 1)
    total = advance_info.get("total", len(sequence))
    if next_idx >= total:
        await finalize_test1(user_id)
    else:
        await send_test1_question(user_id)


async def handle_test1_option(callback: CallbackQuery) -> None:
    user_id = callback.from_user.id
    state_manager = get_state_manager()
    state = await state_manager.get(user_id)
    if not state or state.get("flow") != "interview":
        await callback.answer("Сценарий неактивен", show_alert=True)
        return

    parts = callback.data.split(":")
    if len(parts) != 3:
        await callback.answer()
        return
    _, idx_s, opt_idx_s = parts
    try:
        idx = int(idx_s)
        opt_idx = int(opt_idx_s)
    except ValueError:
        await callback.answer()
        return

    current_idx = state.get("t1_current_idx", state.get("t1_idx", 0))
    if idx != current_idx:
        await callback.answer("Вопрос уже пройден", show_alert=True)
        return

    sequence = state.get("t1_sequence") or list(TEST1_QUESTIONS)
    if idx >= len(sequence):
        await callback.answer("Вопрос недоступен", show_alert=True)
        return

    question = sequence[idx]
    options = question.get("options") or []
    if opt_idx < 0 or opt_idx >= len(options):
        await callback.answer("Вариант недоступен", show_alert=True)
        return

    option_meta = options[opt_idx]
    label = _extract_option_label(option_meta)
    value = _extract_option_value(option_meta)

    metadata = option_meta if isinstance(option_meta, dict) else None

    result = await save_test1_answer(user_id, question, value, metadata=metadata)

    if result.status == "invalid":
        short_msg = result.message or "Проверьте ответ"
        await callback.answer(short_msg[:150], show_alert=True)
        feedback = _format_validation_feedback(result)
        await callback.message.answer(feedback)
        return

    updated_state = await state_manager.get(user_id) or {}

    if result.status == "reject":
        await _handle_test1_rejection(user_id, result)
        return

    followup_text = await _resolve_followup_message(result, updated_state)
    if followup_text:
        await callback.message.answer(followup_text)

    await _mark_test1_question_answered(user_id, label)

    def _advance(st: State) -> Tuple[State, Dict[str, int]]:
        working = st
        sequence_local = list(working.get("t1_sequence") or TEST1_QUESTIONS)
        working["t1_sequence"] = sequence_local
        current = int(working.get("t1_current_idx", working.get("t1_idx", 0)) or 0)
        if current != idx:
            return working, {"advanced": 0, "total": len(sequence_local)}
        next_idx = idx + 1
        working["t1_idx"] = next_idx
        return working, {"advanced": 1, "total": len(sequence_local), "next_idx": next_idx}

    advance_info = await state_manager.atomic_update(user_id, _advance)

    await callback.answer(f"Выбрано: {label}")

    if not advance_info.get("advanced"):
        return

    next_idx = advance_info.get("next_idx", idx + 1)
    total = advance_info.get("total", len(sequence))
    if next_idx >= total:
        await finalize_test1(user_id)
    else:
        await send_test1_question(user_id)


async def finalize_test1(user_id: int) -> None:
    bot = get_bot()
    state_manager = get_state_manager()
    state = await state_manager.get(user_id) or {}
    sequence = state.get("t1_sequence", list(TEST1_QUESTIONS))
    answers = state.get("test1_answers") or {}
    lines = [
        "📋 Анкета кандидата (Тест 1)",
        "━━━━━━━━━━━━━━━━━━━━",
        f"Дата: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"TG ID: {user_id}",
        f"ФИО: {state.get('fio') or '—'}",
        f"Город: {state.get('city_name') or '—'}",
        "",
        "Ответы:",
    ]
    for q in sequence:
        qid = q["id"]
        lines.append(f"- {q['prompt']}\n  {answers.get(qid, '—')}")

    report_content = "\n".join(lines)
    fname = TEST1_DIR / f"test1_{(state.get('fio') or user_id)}.txt"
    try:
        with open(fname, "w", encoding="utf-8") as f:
            f.write(report_content)
    except Exception:
        pass

    if not state.get("t1_notified"):
        shared = await _share_test1_with_recruiters(user_id, state, fname)

        if shared:
            def _mark_shared(st: State) -> Tuple[State, None]:
                st["t1_notified"] = True
                return st, None

            await state_manager.atomic_update(user_id, _mark_shared)

    done_text = await templates.tpl(state.get("city_id"), "t1_done")
    if done_text:
        await bot.send_message(user_id, done_text)

    try:
        await show_recruiter_menu(user_id)
    except Exception:
        logger.exception("Failed to present recruiter menu after Test 1 completion")

    try:
        fio = state.get("fio") or f"TG {user_id}"
        city_name = state.get("city_name") or ""
        username = state.get("username") or None
        candidate = await candidate_services.create_or_update_user(
            telegram_id=user_id,
            fio=fio,
            city=city_name,
            username=username,
        )

        answers = state.get("test1_answers") or {}
        question_data = []
        for idx, question in enumerate(sequence, start=1):
            prompt = question.get("prompt", "")
            qid = question.get("id")
            answer = answers.get(qid, "")
            question_data.append(
                {
                    "question_index": idx,
                    "question_text": prompt,
                    "correct_answer": None,
                    "user_answer": answer,
                    "attempts_count": 1 if answer else 0,
                    "time_spent": 0,
                    "is_correct": True,
                    "overtime": False,
                }
            )

        await candidate_services.save_test_result(
            user_id=candidate.id,
            raw_score=len(question_data),
            final_score=float(len(question_data)),
            rating="TEST1",
            total_time=int(state.get("test1_duration") or 0),
            question_data=question_data,
        )

        try:
            report_dir = REPORTS_DIR / str(candidate.id)
            report_dir.mkdir(parents=True, exist_ok=True)
            report_path = report_dir / "test1.txt"
            with open(report_path, "w", encoding="utf-8") as handle:
                handle.write(report_content)
            rel_path = str(Path("reports") / str(candidate.id) / "test1.txt")
            await candidate_services.update_candidate_reports(candidate.id, test1_path=rel_path)
        except Exception:
            logger.exception("Failed to persist Test 1 report for candidate %s", candidate.id)
    except Exception:  # pragma: no cover - auxiliary sync must not break flow
        logger.exception("Failed to persist candidate profile for Test1")

    await record_test1_completion()

    def _reset(st: State) -> Tuple[State, None]:
        st["t1_idx"] = None
        st["t1_last_prompt_id"] = None
        st["t1_last_question_text"] = ""
        st["t1_requires_free_text"] = False
        return st, None

    await state_manager.atomic_update(user_id, _reset)


async def start_test2(user_id: int) -> None:
    bot = get_bot()
    state_manager = get_state_manager()

    def _init_attempts(state: State) -> Tuple[State, Dict[str, Optional[int]]]:
        state["t2_attempts"] = {
            q_index: {"answers": [], "is_correct": False, "start_time": None}
            for q_index in range(len(TEST2_QUESTIONS))
        }
        return state, {"city_id": state.get("city_id")}

    ctx = await state_manager.atomic_update(user_id, _init_attempts)
    intro = await templates.tpl(
        ctx.get("city_id"),
        "t2_intro",
        qcount=len(TEST2_QUESTIONS),
        timelimit=TIME_LIMIT // 60,
        attempts=MAX_ATTEMPTS,
    )
    await bot.send_message(user_id, intro)
    await send_test2_question(user_id, 0)


async def send_test2_question(user_id: int, q_index: int) -> None:
    bot = get_bot()
    state_manager = get_state_manager()

    def _mark_start(state: State) -> Tuple[State, None]:
        attempts = state.setdefault("t2_attempts", {})
        attempt = attempts.setdefault(
            q_index, {"answers": [], "is_correct": False, "start_time": None}
        )
        attempt["start_time"] = datetime.now()
        return state, None

    await state_manager.atomic_update(user_id, _mark_start)
    question = TEST2_QUESTIONS[q_index]
    txt = (
        f"🔹 <b>Вопрос {q_index + 1}/{len(TEST2_QUESTIONS)}</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"{question['text']}"
    )
    await bot.send_message(
        user_id, txt, reply_markup=create_keyboard(question["options"], q_index)
    )


async def handle_test2_answer(callback: CallbackQuery) -> None:
    user_id = callback.from_user.id
    state_manager = get_state_manager()
    state = await state_manager.get(user_id)
    if not state or "t2_attempts" not in state or state.get("flow") != "intro":
        await callback.answer()
        return

    try:
        _, qidx_s, ans_s = callback.data.split("_")
        q_index = int(qidx_s)
        answer_index = int(ans_s)
    except ValueError:
        await callback.answer()
        return

    question = TEST2_QUESTIONS[q_index]

    now = datetime.now()
    correct_answer = question.get("correct")

    def _apply(state: State) -> Tuple[State, Dict[str, Any]]:
        attempts = state.get("t2_attempts")
        if not isinstance(attempts, dict):
            return state, {"skip": True}
        attempt = attempts.get(q_index)
        if attempt is None:
            attempt = {"answers": [], "is_correct": False, "start_time": None}
            attempts[q_index] = attempt

        answers = attempt.setdefault("answers", [])
        start_time = attempt.get("start_time")
        time_spent = (now - start_time).seconds if isinstance(start_time, datetime) else 0
        overtime = time_spent > TIME_LIMIT

        answers.append(
            {"answer": answer_index, "time": now.isoformat(), "overtime": overtime}
        )
        is_correct = answer_index == correct_answer
        attempt["is_correct"] = is_correct

        attempts_left = MAX_ATTEMPTS - len(answers)
        if attempts_left < 0:
            attempts_left = 0

        return state, {
            "skip": False,
            "is_correct": is_correct,
            "answers_count": len(answers),
            "attempts_left": attempts_left,
            "overtime": overtime,
        }

    result = await state_manager.atomic_update(user_id, _apply)
    if result.get("skip"):
        await callback.answer()
        return

    is_correct = bool(result.get("is_correct"))
    attempts_left = int(result.get("attempts_left", 0))
    overtime = bool(result.get("overtime"))
    answers_count = int(result.get("answers_count", 0))

    feedback = question.get("feedback")
    if isinstance(feedback, list):
        feedback_message = feedback[answer_index]
    else:
        feedback_message = feedback if is_correct else "❌ <i>Неверно.</i>"

    if is_correct:
        final_feedback = f"{feedback_message}"
        if overtime:
            final_feedback += "\n⏰ <i>Превышено время</i>"
        if answers_count > 1:
            penalty = 10 * (answers_count - 1)
            final_feedback += f"\n⚠️ <i>Попыток: {answers_count} (-{penalty}%)</i>"
        await callback.message.edit_text(final_feedback)

        if q_index < len(TEST2_QUESTIONS) - 1:
            await send_test2_question(user_id, q_index + 1)
        else:
            await finalize_test2(user_id)
    else:
        final_feedback = f"{feedback_message}"
        if attempts_left > 0:
            final_feedback += f"\nОсталось попыток: {attempts_left}"
            await callback.message.edit_text(
                final_feedback,
                reply_markup=create_keyboard(question["options"], q_index),
            )
        else:
            final_feedback += "\n🚫 <i>Лимит попыток исчерпан</i>"
            await callback.message.edit_text(final_feedback)
            if q_index < len(TEST2_QUESTIONS) - 1:
                await send_test2_question(user_id, q_index + 1)
            else:
                await finalize_test2(user_id)


async def finalize_test2(user_id: int) -> None:
    bot = get_bot()
    state_manager = get_state_manager()
    state = await state_manager.get(user_id) or {}
    attempts = state.get("t2_attempts", {})
    correct_answers = sum(1 for attempt in attempts.values() if attempt["is_correct"])
    score = calculate_score(attempts)
    rating = get_rating(score)

    fio = state.get("fio") or f"TG {user_id}"
    city_name = state.get("city_name") or ""
    username = state.get("username") or None

    candidate = None
    try:
        existing = await candidate_services.get_user_by_telegram_id(user_id)
        if existing is None:
            candidate = await candidate_services.create_or_update_user(
                telegram_id=user_id,
                fio=fio,
                city=city_name,
                username=username,
            )
        else:
            candidate = await candidate_services.create_or_update_user(
                telegram_id=user_id,
                fio=fio,
                city=city_name,
                username=username,
            )
    except Exception:
        logger.exception("Failed to ensure candidate profile before Test 2 report")
        candidate = None

    question_data: List[dict] = []
    report_lines = [
        "📋 Отчёт по Тесту 2",
        "━━━━━━━━━━━━━━━━━━━━",
        f"Дата: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"TG ID: {user_id}",
        f"ФИО: {fio}",
        f"Город: {city_name or '—'}",
        f"Баллы: {score} ({correct_answers}/{len(TEST2_QUESTIONS)} верных)",
        f"Рейтинг: {rating}",
        "",
        "Вопросы:",
    ]

    for idx, question in enumerate(TEST2_QUESTIONS, start=1):
        options = question.get("options") or []
        attempt = attempts.get(idx - 1, {})
        answers_seq = attempt.get("answers", [])
        attempts_count = len(answers_seq)
        user_answer_idx = answers_seq[-1].get("answer") if answers_seq else None
        if isinstance(user_answer_idx, int) and 0 <= user_answer_idx < len(options):
            user_answer_text = options[user_answer_idx]
        else:
            user_answer_text = "—"
        correct_idx = question.get("correct")
        if isinstance(correct_idx, int) and 0 <= correct_idx < len(options):
            correct_text = options[correct_idx]
        else:
            correct_text = "—"
        overtime = any(entry.get("overtime") for entry in answers_seq)
        question_data.append(
            {
                "question_index": idx,
                "question_text": question.get("text", ""),
                "correct_answer": correct_text,
                "user_answer": user_answer_text,
                "attempts_count": attempts_count,
                "time_spent": 0,
                "is_correct": bool(attempt.get("is_correct")),
                "overtime": overtime,
            }
        )
        report_lines.append(f"{idx}. {question.get('text', '')}")
        report_lines.append(f"   Ответ кандидата: {user_answer_text}")
        report_lines.append(
            f"   Правильный ответ: {correct_text} {'✅' if attempt.get('is_correct') else '❌'}"
        )
        report_lines.append(
            f"   Попыток: {attempts_count} · Просрочено: {'да' if overtime else 'нет'}"
        )
        report_lines.append("")

    report_content = "\n".join(report_lines)

    if candidate is not None:
        try:
            await candidate_services.save_test_result(
                user_id=candidate.id,
                raw_score=correct_answers,
                final_score=score,
                rating="TEST2",
                total_time=int(state.get("test2_duration") or 0),
                question_data=question_data,
            )
        except Exception:
            logger.exception("Failed to persist Test 2 result for candidate %s", candidate.id)

        try:
            report_dir = REPORTS_DIR / str(candidate.id)
            report_dir.mkdir(parents=True, exist_ok=True)
            report_path = report_dir / "test2.txt"
            with open(report_path, "w", encoding="utf-8") as handle:
                handle.write(report_content)
            rel_path = str(Path("reports") / str(candidate.id) / "test2.txt")
            await candidate_services.update_candidate_reports(
                candidate.id,
                test2_path=rel_path,
            )
        except Exception:
            logger.exception("Failed to persist Test 2 report for candidate %s", candidate.id)

    result_text = await templates.tpl(
        state.get("city_id"),
        "t2_result",
        correct=correct_answers,
        score=score,
        rating=rating,
    )
    await bot.send_message(user_id, result_text)
    pct = correct_answers / max(1, len(TEST2_QUESTIONS))
    if pct < PASS_THRESHOLD:
        fail_text = await templates.tpl(state.get("city_id"), "result_fail")
        await bot.send_message(user_id, fail_text)
        await state_manager.delete(user_id)
        return

    final_notice = await templates.tpl(state.get("city_id"), "slot_sent")
    if not final_notice:
        final_notice = "Заявка отправлена. Ожидайте подтверждения."
    await bot.send_message(user_id, final_notice)


async def show_recruiter_menu(user_id: int, *, notice: Optional[str] = None) -> None:
    bot = get_bot()
    state_manager = get_state_manager()
    state = await state_manager.get(user_id) or {}
    tz_label = state.get("candidate_tz", DEFAULT_TZ)
    kb = await kb_recruiters(tz_label, city_id=state.get("city_id"))
    text = await templates.tpl(state.get("city_id"), "choose_recruiter")
    if notice:
        text = f"{notice}\n\n{text}"
    await bot.send_message(user_id, text, reply_markup=kb)


async def handle_home_start(callback: CallbackQuery) -> None:
    await callback.answer()
    await begin_interview(callback.from_user.id)


async def send_manual_scheduling_prompt(user_id: int) -> bool:
    """Prompt the candidate to reach out when no automatic slots are available.

    Returns ``True`` when a new prompt was sent and ``False`` when the candidate
    has already received the manual contact instructions earlier.
    """

    bot = get_bot()
    state_manager = get_state_manager()
    try:
        state = await state_manager.get(user_id)
    except Exception:
        state = None

    city_id: Optional[int] = None
    manual_prompt_sent = False
    if isinstance(state, dict):
        city_id = state.get("city_id")
        manual_prompt_sent = bool(state.get("manual_contact_prompt_sent"))

    if manual_prompt_sent:
        return False

    message = await templates.tpl(city_id, "manual_schedule_prompt")
    if not message:
        message = (
            "Свободных слотов сейчас нет. Напишите, пожалуйста, когда вам удобно, "
            "и мы подберём время вручную."
        )

    reply_markup: Optional[InlineKeyboardMarkup] = None
    recruiter_label: Optional[str] = None

    if city_id is not None:
        try:
            city = await get_city(city_id)
        except Exception:
            city = None

        recruiter = None
        if city is not None:
            recruiters = list(getattr(city, "recruiters", []) or [])
            for candidate in recruiters:
                if candidate is None:
                    continue
                if getattr(candidate, "active", True):
                    recruiter = candidate
                    break

        if recruiter and recruiter.tg_chat_id and recruiter.tg_chat_id > 0:
            recruiter_label = recruiter.name.strip() or "рекрутёром"
            button = InlineKeyboardButton(
                text=f"Написать {recruiter_label}",
                url=f"tg://user?id={int(recruiter.tg_chat_id)}",
            )
            reply_markup = InlineKeyboardMarkup(inline_keyboard=[[button]])

    if recruiter_label:
        safe_label = html.escape(recruiter_label)
        message = (
            f"{message}\n\nНажмите кнопку ниже, чтобы написать {safe_label}."
        )

    await bot.send_message(user_id, message, reply_markup=reply_markup)

    def _mark_prompt_sent(st: State) -> Tuple[State, None]:
        st["manual_contact_prompt_sent"] = True
        return st, None

    await state_manager.atomic_update(user_id, _mark_prompt_sent)

    return True


async def handle_pick_recruiter(callback: CallbackQuery) -> None:
    user_id = callback.from_user.id
    rid_s = callback.data.split(":", 1)[1]

    state_manager = get_state_manager()
    state = await state_manager.get(user_id)

    if rid_s == "__again__":
        tz_label = (state or {}).get("candidate_tz", DEFAULT_TZ)
        kb = await kb_recruiters(tz_label, city_id=(state or {}).get("city_id"))
        text = await templates.tpl(state.get("city_id") if state else None, "choose_recruiter")
        if state is not None:
            def _clear_pick(st: State) -> Tuple[State, None]:
                st["picked_recruiter_id"] = None
                return st, None

            await state_manager.atomic_update(user_id, _clear_pick)
        try:
            await callback.message.edit_text(text, reply_markup=kb)
        except TelegramBadRequest:
            await callback.message.edit_text(text)
            await callback.message.edit_reply_markup(reply_markup=kb)
        await callback.answer()
        return

    try:
        rid = int(rid_s)
    except ValueError:
        await callback.answer("Некорректный рекрутёр", show_alert=True)
        return

    rec = await get_recruiter(rid)
    if not rec or not getattr(rec, "active", True):
        await callback.answer("Рекрутёр не найден/не активен", show_alert=True)
        return

    if not state:
        await callback.answer("Сессия истекла. Введите /start", show_alert=True)
        return

    city_id = state.get("city_id")
    if city_id:
        allowed = await get_active_recruiters_for_city(city_id)
        if rid not in {r.id for r in allowed}:
            await callback.answer("Этот рекрутёр не работает с вашим городом", show_alert=True)
            await show_recruiter_menu(user_id)
            return

    def _pick(st: State) -> Tuple[State, None]:
        st["picked_recruiter_id"] = rid
        return st, None

    await state_manager.atomic_update(user_id, _pick)
    tz_label = state.get("candidate_tz", DEFAULT_TZ)
    slots_list = await get_free_slots_by_recruiter(rid, city_id=city_id)
    kb = await kb_slots_for_recruiter(rid, tz_label, slots=slots_list, city_id=city_id)
    text = _recruiter_header(rec.name, tz_label)
    if not slots_list:
        text = f"{text}\n\n{await templates.tpl(state.get('city_id'), 'no_slots')}"
    try:
        await callback.message.edit_text(text, reply_markup=kb)
    except TelegramBadRequest:
        await callback.message.edit_text(text)
        await callback.message.edit_reply_markup(reply_markup=kb)
    await callback.answer()


async def handle_refresh_slots(callback: CallbackQuery) -> None:
    user_id = callback.from_user.id
    _, rid_s = callback.data.split(":", 1)
    try:
        rid = int(rid_s)
    except ValueError:
        await callback.answer("Рекрутёр не найден", show_alert=True)
        return

    state = await get_state_manager().get(user_id)
    if not state:
        await callback.answer("Сессия истекла. Введите /start", show_alert=True)
        return

    tz_label = state.get("candidate_tz", DEFAULT_TZ)
    city_id = state.get("city_id")
    slots_list = await get_free_slots_by_recruiter(rid, city_id=city_id)
    kb = await kb_slots_for_recruiter(rid, tz_label, slots=slots_list, city_id=city_id)
    rec = await get_recruiter(rid)
    text = _recruiter_header(rec.name if rec else str(rid), tz_label)
    if not slots_list:
        text = f"{text}\n\n{await templates.tpl(state.get('city_id'), 'no_slots')}"
    try:
        await callback.message.edit_text(text, reply_markup=kb)
    except TelegramBadRequest:
        await callback.message.edit_text(text)
        await callback.message.edit_reply_markup(reply_markup=kb)
    await callback.answer("Обновлено")


async def handle_pick_slot(callback: CallbackQuery) -> None:
    user_id = callback.from_user.id
    _, rid_s, slot_id_s = callback.data.split(":", 2)

    try:
        recruiter_id = int(rid_s)
    except ValueError:
        await callback.answer("Рекрутёр не найден", show_alert=True)
        return

    try:
        slot_id = int(slot_id_s)
    except ValueError:
        await callback.answer("Слот не найден", show_alert=True)
        return

    state_manager = get_state_manager()
    state = await state_manager.get(user_id)
    if not state:
        await callback.answer("Сессия истекла. Введите /start", show_alert=True)
        return

    # Update username if available (for existing users)
    username = getattr(callback.from_user, "username", None)
    if username and state.get("username") != username:
        def _update_username(st: State) -> Tuple[State, None]:
            st["username"] = username
            return st, None
        await state_manager.atomic_update(user_id, _update_username)
        state["username"] = username  # Update local state copy

    is_intro = state.get("flow") == "intro"
    city_id = state.get("city_id")
    reservation = await reserve_slot(
        slot_id,
        candidate_tg_id=user_id,
        candidate_fio=state.get("fio", str(user_id)),
        candidate_tz=state.get("candidate_tz", DEFAULT_TZ),
        candidate_city_id=state.get("city_id"),
        candidate_username=state.get("username"),  # Pass username to reserve_slot
        purpose="intro_day" if is_intro else "interview",
        expected_recruiter_id=recruiter_id,
        expected_city_id=city_id,
    )

    if reservation.status == "slot_taken":
        text = await templates.tpl(state.get("city_id"), "slot_taken")
        if is_intro:
            try:
                await callback.message.edit_text(text)
                await callback.message.edit_reply_markup(reply_markup=None)
            except TelegramBadRequest:
                pass
            await show_recruiter_menu(user_id, notice=text)
        else:
            kb = await kb_slots_for_recruiter(
                recruiter_id,
                state.get("candidate_tz", DEFAULT_TZ),
                city_id=city_id,
            )
            try:
                await callback.message.edit_text(text, reply_markup=kb)
            except TelegramBadRequest:
                await callback.message.edit_text(text)
                await callback.message.edit_reply_markup(reply_markup=kb)

        await callback.answer("Слот уже занят.")
        return

    slot = reservation.slot
    if slot is None:
        await callback.answer("Ошибка бронирования.", show_alert=True)
        return

    if reservation.status in {"duplicate_candidate", "already_reserved"}:
        await _notify_existing_reservation(callback, slot)
        return

    rec = await get_recruiter(slot.recruiter_id)
    purpose = "ознакомительный день" if is_intro else "видео-интервью"
    bot = get_bot()
    caption = (
        f"📥 <b>Новый кандидат на {purpose}</b>\n"
        f"👤 {slot.candidate_fio or user_id}\n"
        f"📍 {state.get('city_name','—')}\n"
        f"🗓 {fmt_dt_local(slot.start_utc, (rec.tz if rec else DEFAULT_TZ) or DEFAULT_TZ)}\n"
    )

    attached = False
    for path in [
        TEST1_DIR / f"test1_{state.get('fio') or user_id}.txt",
        REPORTS_DIR / f"report_{state.get('fio') or user_id}.txt",
    ]:
        if path.exists():
            try:
                if rec and rec.tg_chat_id:
                    await bot.send_document(
                        rec.tg_chat_id,
                        FSInputFile(str(path)),
                        caption=caption,
                        reply_markup=kb_approve(slot.id),
                    )
                    attached = True

                    # Mark that test1 form has been shared to prevent duplicate sending
                    def _mark_test1_shared(st: State) -> Tuple[State, None]:
                        st["t1_notified"] = True
                        return st, None
                    await state_manager.atomic_update(user_id, _mark_test1_shared)
            except Exception:
                pass
            break

    if rec and rec.tg_chat_id and not attached:
        try:
            await bot.send_message(
                rec.tg_chat_id, caption, reply_markup=kb_approve(slot.id)
            )
        except Exception:
            pass
    elif not rec or not rec.tg_chat_id:
        await bot.send_message(
            user_id,
            "ℹ️ Рекрутёр ещё не активировал DM с ботом (/iam_mih) или не указан tg_chat_id.\n"
            "Заявка создана, но уведомление не отправлено.",
        )

    await callback.message.edit_text(
        await templates.tpl(state.get("city_id"), "slot_sent")
    )
    try:
        city_name = state.get("city_name")
        slot_tz = getattr(slot, "tz_name", None)
        if not city_name and city_id:
            city_obj = await get_city(city_id)
            if city_obj is not None:
                city_name = getattr(city_obj, "name_plain", None) or getattr(city_obj, "name", "")
                slot_tz = slot_tz or getattr(city_obj, "tz", None)
        slot_tz = slot_tz or (rec.tz if rec and rec.tz else DEFAULT_TZ)
        candidate_tz = state.get("candidate_tz", DEFAULT_TZ)
        candidate_labels = slot_local_labels(slot.start_utc, candidate_tz)
        city_labels = slot_local_labels(slot.start_utc, slot_tz)
        candidate_time = candidate_labels.get("slot_time_local") or fmt_dt_local(slot.start_utc, candidate_tz)
        city_time = city_labels.get("slot_time_local") or fmt_dt_local(slot.start_utc, slot_tz)
        summary = f"Ваше время: {candidate_time}"
        if city_name:
            if city_time == candidate_time:
                summary += f" (по местному времени города {city_name})"
            else:
                summary += f" (по местному времени города {city_name} — {city_time})"
        else:
            if city_time == candidate_time:
                summary += f" (по часовому поясу {slot_tz})"
            else:
                summary += f" (по часовому поясу {slot_tz} — {city_time})"
        await bot.send_message(user_id, summary)
    except Exception:
        logger.exception("Failed to send slot time summary", exc_info=True)
    await callback.answer()


async def _resolve_candidate_state_for_slot(slot: Slot) -> Dict[str, Any]:
    if slot.candidate_tg_id is None:
        return {}
    try:
        state_manager = get_state_manager()
    except RuntimeError:
        return {}
    try:
        return await state_manager.get(slot.candidate_tg_id) or {}
    except Exception:
        return {}


async def _render_candidate_notification(slot: Slot) -> Tuple[str, str, str, str, Optional[int]]:
    tz = slot.candidate_tz or DEFAULT_TZ
    labels = slot_local_labels(slot.start_utc, tz)
    state = await _resolve_candidate_state_for_slot(slot)
    candidate_name = slot.candidate_fio or ""
    city_name = state.get("city_name") or ""
    context = {
        "candidate_name": candidate_name,
        "candidate_fio": candidate_name,
        "candidate_city": city_name,
        "city_name": city_name,
        "dt_local": fmt_dt_local(slot.start_utc, tz),
        "tz_name": tz,
        "slot_date_local": labels.get("slot_date_local", ""),
        "slot_time_local": labels.get("slot_time_local", ""),
        "slot_datetime_local": labels.get("slot_datetime_local", ""),
        "slot_day_name_local": labels.get("slot_day_name_local", ""),
        "recruiter_name": "",
        "join_link": "",
    }
    provider = get_template_provider()
    rendered = await provider.render(
        "interview_confirmed_candidate",
        context,
        locale="ru",
        channel="tg",
    )
    if rendered is not None:
        return rendered.text, tz, city_name, rendered.key, rendered.version

    template_key = (
        "stage3_intro_invite"
        if getattr(slot, "purpose", "interview") == "intro_day"
        else "approved_msg"
    )
    fallback_text = await templates.tpl(
        getattr(slot, "candidate_city_id", None),
        template_key,
        candidate_fio=candidate_name,
        city_name=city_name,
        dt=context["dt_local"],
        **labels,
    )
    return fallback_text, tz, city_name, "interview_confirmed_candidate", None


async def handle_approve_slot(callback: CallbackQuery) -> None:
    slot_id = int(callback.data.split(":", 1)[1])
    slot = await get_slot(slot_id)
    if not slot:
        await callback.answer("Заявка уже обработана.", show_alert=True)
        await safe_remove_reply_markup(callback.message)
        return

    status_value = (slot.status or "").lower()

    if status_value in {SlotStatus.BOOKED, SlotStatus.CONFIRMED_BY_CANDIDATE}:
        await callback.answer("Уже согласовано ✔️")
        await safe_remove_reply_markup(callback.message)
        return

    if status_value == SlotStatus.FREE:
        await callback.answer("Слот уже освобождён.", show_alert=True)
        await safe_remove_reply_markup(callback.message)
        return

    if slot.candidate_tg_id is None:
        await callback.answer("Кандидат не найден.", show_alert=True)
        await safe_remove_reply_markup(callback.message)
        return

    slot = await approve_slot(slot_id)
    if not slot:
        await callback.answer("Не удалось согласовать.", show_alert=True)
        return

    already_sent = await notification_log_exists(
        "candidate_interview_confirmed",
        slot.id,
        candidate_tg_id=slot.candidate_tg_id,
    )

    message_text, candidate_tz, candidate_city, template_key, template_version = await _render_candidate_notification(
        slot
    )
    bot = get_bot()

    try:
        reminder_service = get_reminder_service()
    except RuntimeError:
        reminder_service = None

    if not already_sent:
        try:
            await _send_with_retry(
                bot,
                SendMessage(chat_id=slot.candidate_tg_id, text=message_text),
                correlation_id=f"approve:{slot.id}:{uuid.uuid4().hex}",
            )
        except Exception:
            logger.exception("Failed to send approval message to candidate")
            candidate_label = (
                slot.candidate_fio
                or (str(slot.candidate_tg_id) if slot.candidate_tg_id is not None else "—")
            )
            failure_parts = [
                "⚠️ Слот подтверждён, но отправить сообщение кандидату не удалось.",
                f"👤 {html.escape(candidate_label)}",
                f"🕒 {fmt_dt_local(slot.start_utc, candidate_tz)} ({candidate_tz})",
            ]
            if candidate_city:
                failure_parts.append(f"📍 {html.escape(candidate_city)}")
            failure_parts.extend(
                [
                    "",
                    "<b>Текст сообщения:</b>",
                    f"<blockquote>{message_text}</blockquote>",
                    "Свяжитесь с кандидатом вручную.",
                ]
            )
            failure_text = "\n".join(failure_parts)

            await safe_edit_text_or_caption(callback.message, failure_text)
            await safe_remove_reply_markup(callback.message)
            await callback.answer("Не удалось отправить сообщение кандидату.", show_alert=True)
            return

        logged = await add_notification_log(
            "candidate_interview_confirmed",
            slot.id,
            candidate_tg_id=slot.candidate_tg_id,
            payload=message_text,
            template_key=template_key,
            template_version=template_version,
        )
        if not logged:
            logger.warning("Notification log already exists for slot %s", slot.id)

        await mark_outbox_notification_sent(
            "interview_confirmed_candidate",
            slot.id,
            candidate_tg_id=slot.candidate_tg_id,
        )

        if reminder_service is not None:
            await reminder_service.schedule_for_slot(slot.id)

        candidate_label = (
            slot.candidate_fio
            or (str(slot.candidate_tg_id) if slot.candidate_tg_id is not None else "—")
        )

        summary_parts = [
            "✅ Слот подтверждён. Сообщение отправлено кандидату автоматически.",
            f"👤 {html.escape(candidate_label)}",
            f"🕒 {fmt_dt_local(slot.start_utc, candidate_tz)} ({candidate_tz})",
        ]
        if candidate_city:
            summary_parts.append(f"📍 {html.escape(candidate_city)}")
        summary_parts.extend(
            [
                "",
                "<b>Текст сообщения:</b>",
                f"<blockquote>{message_text}</blockquote>",
            ]
        )
        summary_text = "\n".join(summary_parts)

        await safe_edit_text_or_caption(callback.message, summary_text)
        await safe_remove_reply_markup(callback.message)
        await callback.answer("Сообщение отправлено кандидату.")
        return

    if reminder_service is not None:
        await reminder_service.schedule_for_slot(slot.id)

    await callback.answer("Уже согласовано ✔️")
    await safe_remove_reply_markup(callback.message)
    return


async def handle_send_slot_message(callback: CallbackQuery) -> None:
    slot_id = int(callback.data.split(":", 1)[1])
    slot = await get_slot(slot_id)
    if not slot:
        await callback.answer("Заявка уже обработана.", show_alert=True)
        await safe_remove_reply_markup(callback.message)
        return

    if slot.candidate_tg_id is None:
        await callback.answer("Кандидат не найден.", show_alert=True)
        await safe_remove_reply_markup(callback.message)
        return

    status_value = (slot.status or "").lower()
    if status_value not in {SlotStatus.BOOKED, SlotStatus.CONFIRMED_BY_CANDIDATE}:
        await callback.answer("Слот ещё не подтверждён.", show_alert=True)
        await safe_remove_reply_markup(callback.message)
        return

    message_text, candidate_tz, candidate_city, _, _ = await _render_candidate_notification(slot)
    bot = get_bot()
    try:
        await bot.send_message(slot.candidate_tg_id, message_text)
    except Exception:
        logger.exception("Failed to send approval message to candidate")
        await callback.answer("Не удалось отправить сообщение кандидату.", show_alert=True)
        return

    try:
        reminder_service = get_reminder_service()
    except RuntimeError:
        reminder_service = None
    if reminder_service is not None:
        await reminder_service.schedule_for_slot(slot.id)

    candidate_label = (
        slot.candidate_fio
        or (str(slot.candidate_tg_id) if slot.candidate_tg_id is not None else "—")
    )
    summary_parts = [
        "✅ Сообщение отправлено кандидату.",
        f"👤 {html.escape(candidate_label)}",
        f"🕒 {fmt_dt_local(slot.start_utc, candidate_tz)} ({candidate_tz})",
    ]
    if candidate_city:
        summary_parts.append(f"📍 {html.escape(candidate_city)}")
    summary_parts.extend(
        [
            "",
            "<b>Текст сообщения:</b>",
            f"<blockquote>{message_text}</blockquote>",
        ]
    )
    summary_text = "\n".join(summary_parts)

    await safe_edit_text_or_caption(callback.message, summary_text)
    await safe_remove_reply_markup(callback.message)
    await callback.answer("Сообщение отправлено.")


async def handle_reject_slot(callback: CallbackQuery) -> None:
    slot_id = int(callback.data.split(":", 1)[1])
    slot = await get_slot(slot_id)
    if not slot:
        await callback.answer("Заявка уже обработана.")
        await safe_remove_reply_markup(callback.message)
        return

    status_value = (slot.status or "").lower()
    if status_value == SlotStatus.FREE or slot.candidate_tg_id is None:
        await callback.answer("Слот уже освобождён.", show_alert=True)
        await safe_remove_reply_markup(callback.message)
        return

    snapshot = await _build_slot_snapshot(slot)
    await reject_slot(slot_id)
    await _cancel_reminders_for_slot(slot_id)

    sent = await _send_final_rejection_notice(snapshot)
    status_text = (
        "⛔️ Отказано. Кандидат уведомлён."
        if sent
        else "⛔️ Отказано. Сообщите кандидату вручную — бот недоступен."
    )

    await safe_edit_text_or_caption(callback.message, status_text)
    await safe_remove_reply_markup(callback.message)
    await callback.answer(
        "Отказано" if sent else "Бот недоступен — свяжитесь с кандидатом.",
        show_alert=not sent,
    )


async def handle_reschedule_slot(callback: CallbackQuery) -> None:
    slot_id = int(callback.data.split(":", 1)[1])
    slot = await get_slot(slot_id)
    if not slot:
        await callback.answer("Заявка уже обработана.")
        await safe_remove_reply_markup(callback.message)
        return

    if slot.candidate_tg_id is None:
        await callback.answer("Кандидат не найден.", show_alert=True)
        await safe_remove_reply_markup(callback.message)
        return

    snapshot = await _build_slot_snapshot(slot)
    await reject_slot(slot_id)
    await _cancel_reminders_for_slot(slot_id)

    sent = await _send_reschedule_prompt(snapshot)
    status_text = (
        "🔁 Перенос: кандидат подберёт новое время."
        if sent
        else "🔁 Слот освобождён. Бот недоступен — свяжитесь с кандидатом."
    )

    await safe_edit_text_or_caption(callback.message, status_text)
    await safe_remove_reply_markup(callback.message)
    await callback.answer(
        "Перенос оформлен." if sent else "Слот освобождён, бот недоступен.",
        show_alert=not sent,
    )


async def handle_attendance_yes(callback: CallbackQuery) -> None:
    slot_id = int(callback.data.split(":", 1)[1])

    if not await register_callback(callback.id):
        await callback.answer("Уже подтверждено")
        await safe_remove_reply_markup(callback.message)
        return

    result = await confirm_slot_by_candidate(slot_id)
    slot = result.slot
    if slot is None:
        await callback.answer(
            "Заявка не найдена или ещё не подтверждена рекрутёром.",
            show_alert=True,
        )
        await safe_remove_reply_markup(callback.message)
        return

    if result.status == "invalid_status":
        await callback.answer(
            "Заявка не найдена или ещё не подтверждена рекрутёром.",
            show_alert=True,
        )
        return

    rec = await get_recruiter(slot.recruiter_id)
    link = (
        rec.telemost_url if rec and rec.telemost_url else "https://telemost.yandex.ru/j/REPLACE_ME"
    )
    tz = slot.candidate_tz or DEFAULT_TZ
    dt_local = fmt_dt_local(slot.start_utc, tz)
    city_id = getattr(slot, "candidate_city_id", None)
    labels = slot_local_labels(slot.start_utc, tz)
    link_text = await templates.tpl(
        city_id,
        "att_confirmed_link",
        link=link,
        dt=dt_local,
        **labels,
    )
    bot = get_bot()

    if result.status == "confirmed":
        try:
            await _send_with_retry(
                bot,
                SendMessage(chat_id=slot.candidate_tg_id, text=link_text),
                correlation_id=f"attendance:{slot.id}:{uuid.uuid4().hex}",
            )
        except Exception:
            logger.exception("Failed to send attendance confirmation to candidate")
            await callback.answer("Не удалось отправить ссылку.", show_alert=True)
            return

        try:
            reminder_service = get_reminder_service()
        except RuntimeError:
            reminder_service = None
        if reminder_service is not None:
            await reminder_service.cancel_for_slot(slot_id)
            await reminder_service.schedule_for_slot(
                slot_id, skip_confirmation_prompts=True
            )

        ack_text = await templates.tpl(
            city_id,
            "att_confirmed_ack",
            dt=dt_local,
            **labels,
        )
        if ack_text:
            try:
                await callback.message.edit_text(ack_text)
            except TelegramBadRequest:
                pass
        await safe_remove_reply_markup(callback.message)
        await callback.answer("Подтверждено")
        return

    await safe_remove_reply_markup(callback.message)
    await callback.answer("Уже подтверждено")


async def handle_attendance_no(callback: CallbackQuery) -> None:
    slot_id = int(callback.data.split(":", 1)[1])
    slot = await get_slot(slot_id)
    if not slot:
        await callback.answer("Заявка уже обработана.")
        await safe_remove_reply_markup(callback.message)
        return

    await reject_slot(slot_id)

    try:
        reminder_service = get_reminder_service()
    except RuntimeError:
        reminder_service = None
    if reminder_service is not None:
        await reminder_service.cancel_for_slot(slot_id)

    rec = await get_recruiter(slot.recruiter_id)
    bot = get_bot()
    if rec and rec.tg_chat_id:
        try:
            await bot.send_message(
                rec.tg_chat_id,
                f"❌ Кандидат {slot.candidate_fio or slot.candidate_tg_id} отказался от слота "
                f"{fmt_dt_local(slot.start_utc, rec.tz or DEFAULT_TZ)}. Слот освобождён.",
            )
        except Exception:
            pass

    st = await get_state_manager().get(callback.from_user.id) or {}
    await bot.send_message(
        callback.from_user.id,
        await templates.tpl(getattr(slot, "candidate_city_id", None), "att_declined"),
    )
    if st.get("flow") == "intro":
        await show_recruiter_menu(callback.from_user.id)
    else:
        kb = await kb_recruiters(st.get("candidate_tz", DEFAULT_TZ))
        await bot.send_message(
            callback.from_user.id,
            await templates.tpl(getattr(slot, "candidate_city_id", None), "choose_recruiter"),
            reply_markup=kb,
        )

    try:
        await callback.message.edit_text("Вы отказались от участия. Слот освобождён.")
    except TelegramBadRequest:
        pass
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except TelegramBadRequest:
        pass

    await callback.answer("Отменено")


def get_rating(score: float) -> str:
    if score >= 6.5:
        return "⭐⭐⭐⭐⭐ "
    if score >= 5:
        return "⭐⭐⭐⭐ "
    if score >= 3.5:
        return "⭐⭐⭐ "
    if score >= 2:
        return "⭐⭐ "
    return "⭐ (Не рекомендован)"


__all__ = [
    "StateManager",
    "BookingNotificationStatus",
    "NotificationService",
    "configure_notification_service",
    "get_notification_service",
    "calculate_score",
    "configure",
    "finalize_test1",
    "finalize_test2",
    "fmt_dt_local",
    "handle_attendance_no",
    "handle_attendance_yes",
    "handle_home_start",
    "handle_pick_recruiter",
    "handle_pick_slot",
    "handle_refresh_slots",
    "handle_test1_answer",
    "handle_test1_option",
    "handle_test2_answer",
    "handle_send_slot_message",
    "get_bot",
    "get_rating",
    "get_state_manager",
    "now_utc",
    "save_test1_answer",
    "send_test1_question",
    "send_test2_question",
    "send_manual_scheduling_prompt",
    "show_recruiter_menu",
    "slot_local_labels",
    "start_introday_flow",
    "start_test2",
    "begin_interview",
    "send_welcome",
    "safe_edit_text_or_caption",
    "safe_remove_reply_markup",
    "handle_approve_slot",
    "handle_reschedule_slot",
    "handle_reject_slot",
    "capture_slot_snapshot",
    "cancel_slot_reminders",
    "notify_reschedule",
    "notify_rejection",
    "SlotSnapshot",
    "set_pending_test2",
    "dispatch_interview_success",
    "register_interview_success_handler",
    "launch_test2",
    "_extract_option_label",
    "_extract_option_value",
    "_mark_test1_question_answered",
    "_shorten_answer",
]
