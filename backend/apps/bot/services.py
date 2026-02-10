"""Supporting services and helpers for the Telegram bot."""

from __future__ import annotations

import asyncio
import builtins
import html
import importlib
import logging
import os
import re
import math
import random
import time
import uuid
from types import SimpleNamespace
from datetime import date, datetime, timedelta, timezone, time as datetime_time
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
    TelegramUnauthorizedError,
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
from backend.domain import analytics
from backend.domain.candidates import services as candidate_services
from backend.domain.candidates.status import CandidateStatus
from backend.domain.candidates.status_service import (
    set_status_waiting_slot,
    set_status_interview_scheduled,
)
from backend.domain.models import Recruiter, Slot, SlotStatus
from backend.apps.bot.events import InterviewSuccessEvent
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.schedulers.base import SchedulerAlreadyRunningError

from backend.apps.bot.broker import BrokerMessage, NotificationBrokerProtocol
from backend.domain.repositories import (
    ReservationResult,
    OutboxItem,
    add_notification_log,
    add_message_log,
    add_outbox_notification,
    claim_outbox_batch,
    get_active_recruiters_for_city,
    get_city,
    get_notification_log,
    get_outbox_item,
    get_outbox_queue_depth,
    get_recruiter,
    get_recruiter_by_chat_id,
    get_recruiter_agenda_by_chat_id,
    find_city_by_plain_name,
    notification_log_exists,
    register_callback,
    mark_outbox_notification_sent,
    reset_outbox_entry,
    set_recruiter_chat_id_by_command,
    update_notification_log_fields,
    update_outbox_entry,
)
from backend.domain.slot_service import (
    reserve_slot,
    approve_slot,
    reject_slot,
    confirm_slot_by_candidate,
    get_slot,
    get_free_slots_by_recruiter,
    city_has_available_slots,
)
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy import select, case, func

from backend.apps.bot.utils.text import escape_html

if TYPE_CHECKING:
    from aiogram import Dispatcher


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
    refresh_questions_bank,
)
from .keyboards import (
    create_keyboard,
    kb_approve,
    kb_attendance_confirm,
    kb_recruiters,
    kb_slots_for_recruiter,
    kb_slot_assignment_offer,
    kb_start,
)
from .city_registry import (
    CityInfo,
    find_candidate_city_by_id,
    find_candidate_city_by_name,
    list_candidate_cities,
)
from .metrics import (
    NotificationMetricsSnapshot,
    get_notification_metrics_snapshot,
    record_circuit_open,
    record_notification_failed,
    record_notification_sent,
    record_candidate_confirmed_notice,
    record_notification_poll_cycle,
    record_notification_poll_skipped,
    record_notification_poll_backoff,
    record_notification_poll_staleness,
    record_rate_limit_wait,
    record_send_retry,
    record_test1_completion,
    record_test1_rejection,
    set_outbox_queue_depth,
)
from .security import verify_callback_data
from .state_store import StateManager
from .test1_validation import Test1Payload, apply_partial_validation, convert_age
from .reminders import ReminderKind, get_reminder_service
from .template_provider import TemplateProvider, RenderedTemplate


logger = logging.getLogger(__name__)

def _sanitize_text(value: Optional[str]) -> str:
    return escape_html(value)


def _strip_markup(value: Optional[str]) -> str:
    if not value:
        return ""
    text = re.sub(r"<[^>]+>", "", str(value))
    return html.unescape(text)


def _format_recruiter_slot_caption(
    *,
    candidate_label: str,
    city_label: str,
    dt_label: str,
    purpose: str,
) -> str:
    return (
        f"📥 <b>Новый кандидат на {escape_html(purpose)}</b>\n"
        f"👤 {escape_html(candidate_label)}\n"
        f"📍 {escape_html(city_label)}\n"
        f"🗓 {dt_label}\n"
    )


def _intro_detail(
    value: Optional[str],
    fallback: Optional[str] = None,
    default: str = "",
) -> Tuple[str, str]:
    raw = (value or "").strip()
    if not raw and fallback:
        raw = str(fallback).strip()
    if not raw:
        raw = default
    return _sanitize_text(raw), raw


async def _resolve_intro_day_template_key(city_id: Optional[int]) -> str:
    _ = city_id
    return "intro_day_invitation"


async def _send_with_retry(bot: Bot, method: SendMessage, correlation_id: str) -> Any:
    attempt = 0
    delay = 1.0
    send_method = method
    fallback_plain_used = False
    while True:
        attempt += 1
        try:
            prepared_method = send_method.as_(bot)
            session = bot.session
            client = await session.create_session()
            url = session.api.api_url(token=bot.token, method=prepared_method.__api_method__)
            form = session.build_form_data(bot=bot, method=prepared_method)
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
                method=prepared_method,
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
        except TelegramBadRequest as exc:
            message = str(exc).lower()
            if (
                not fallback_plain_used
                and "can't parse entities" in message
                and isinstance(send_method, SendMessage)
            ):
                fallback_plain_used = True
                safe_text = _strip_markup(send_method.text)
                logger.warning(
                    "telegram.send.fallback_plain",
                    extra={"correlation_id": correlation_id},
                )
                send_method = SendMessage(
                    chat_id=send_method.chat_id,
                    text=safe_text,
                    reply_markup=send_method.reply_markup,
                    parse_mode=None,
                )
                continue
            raise
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


def _normalize_format_context(fmt: Dict[str, Any]) -> Dict[str, Any]:
    data = dict(fmt)
    if "candidate_name" not in data and "candidate_fio" in data:
        data["candidate_name"] = data["candidate_fio"]
    if "candidate_fio" not in data and "candidate_name" in data:
        data["candidate_fio"] = data["candidate_name"]
    if "dt_local" not in data and "slot_datetime_local" in data:
        data["dt_local"] = data["slot_datetime_local"]
    if "slot_datetime_local" not in data and "dt_local" in data:
        data["slot_datetime_local"] = data["dt_local"]
    if "dt" not in data and "dt_local" in data:
        data["dt"] = data["dt_local"]
    if "dt_local" not in data and "dt" in data:
        data["dt_local"] = data["dt"]
    if "interview_dt_hint" not in data:
        data["interview_dt_hint"] = data.get("dt_local") or data.get("slot_datetime_local") or ""
    return data


class _TemplatesProxy:
    async def tpl(
        self,
        key: str,
        *,
        city_id: Optional[int] = None,
        locale: str = "ru",
        channel: str = "tg",
        strict: bool = False,
        **fmt: Any,
    ) -> str:
        provider = get_template_provider()
        context = _normalize_format_context(fmt)
        res = await provider.render(
            key,
            context,
            locale=locale,
            channel=channel,
            city_id=city_id,
            strict=strict,
        )
        return res.text if res else ""

    def clear_cache(self) -> None:
        reset_template_provider()


templates = _TemplatesProxy()
if not hasattr(builtins, "templates"):
    builtins.templates = templates
if not hasattr(builtins, "StateManager"):
    builtins.StateManager = StateManager


async def _render_tpl(city_id: Optional[int], key: str, **fmt: Any) -> str:
    return await templates.tpl(key, city_id=city_id, **fmt)


def reset_template_provider() -> None:
    global _template_provider
    _template_provider = None


def register_interview_success_handler(
    handler: Callable[[InterviewSuccessEvent], Awaitable[None]]
) -> Callable[[InterviewSuccessEvent], Awaitable[None]]:
    if handler not in _interview_success_handlers:
        _interview_success_handlers.append(handler)
    return handler


class NotificationNotConfigured(RuntimeError):
    """Raised when notification infrastructure is unavailable."""


@dataclass
class NotificationResult:
    status: Literal["queued", "sent", "skipped", "scheduled_retry", "failed"]
    reason: Optional[str] = None
    payload: Optional[str] = None


@dataclass
class SlotApprovalResult:
    status: str
    message: str
    slot: Optional[Slot] = None
    summary_html: Optional[str] = None


DIRECT_NO_BROKER_REASON = "direct:no-broker"
BROKER_UNAVAILABLE_REASON = "broker_unavailable"
INTRO_ADDRESS_FALLBACK = "Адрес уточняется — рекрутёр подтвердит детали перед встречей"
INTRO_CONTACT_FALLBACK = "Руководитель свяжется с вами для подтверждения деталей"


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
        rate_limit_per_sec: float = 10.0,
        max_attempts: int = 8,
        retry_base_delay: int = 30,
        retry_max_delay: int = 3600,
        circuit_break_window: tuple[int, int] = (30, 60),
        worker_concurrency: int = 1,
    ) -> None:
        self._scheduler = scheduler
        if template_provider is None:
            self._template_provider = get_template_provider()
        else:
            self._template_provider = template_provider
            global _template_provider
            _template_provider = template_provider
        self._base_poll_interval = max(poll_interval, 0.5)
        self._current_poll_interval = self._base_poll_interval
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
        self._worker_concurrency = max(1, worker_concurrency)
        self._poll_gate = asyncio.Semaphore(self._worker_concurrency)
        self._task: Optional[asyncio.Task] = None
        self._poll_tasks: set[asyncio.Task] = set()
        self._scheduler_jobs: set[asyncio.Task] = set()
        self._claim_idle_ms = 60000
        self._current_message: Optional[BrokerMessage] = None
        self._skipped_runs: int = 0
        self._started: bool = False
        self._shutting_down: bool = False
        self._loop_enabled: bool = False
        self._watchdog_task: Optional[asyncio.Task] = None
        self._watchdog_interval = max(self._current_poll_interval * 2, 10.0)
        self._watchdog_alert_threshold = max(self._current_poll_interval * 6, 15.0)
        self._last_poll_ts: float = 0.0
        self._idle_backoff_steps = self._build_idle_backoff_steps()
        self._idle_backoff_index = 0
        self._last_idle_log_ts: float = 0.0
        self._idle_log_interval = 60.0
        self._last_db_error_ts: float = 0.0
        self._db_error_log_interval = 300.0
        self._fatal_error_code: Optional[str] = None
        self._fatal_error_at: Optional[datetime] = None
        self._last_delivery_error: Optional[str] = None

    def start(self, *, allow_poll_loop: bool = False) -> None:
        self._shutting_down = False
        if self._started:
            return

        scheduler_started = False
        scheduler_failed = False

        if self._scheduler is not None:
            try:
                self._ensure_scheduler_job()
                scheduler_started = True
            except Exception:
                scheduler_failed = True
                logger.exception("notification.worker.scheduler_start_failed")

        if scheduler_started:
            self._started = True
            self._ensure_watchdog()
            return

        if scheduler_failed:
            logger.warning("notification.worker.scheduler_fallback_loop")
            self._enable_poll_loop()
            self._started = True
            self._ensure_watchdog()
            return

        if not allow_poll_loop:
            return

        self._enable_poll_loop()
        self._started = True
        self._ensure_watchdog()

    def _enable_poll_loop(self) -> None:
        if self._shutting_down:
            return
        self._loop_enabled = True
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            logger.warning("notification.worker.poll_loop_start_failed", extra={"reason": "no_loop"})
            return
        if self._task is None or self._task.done():
            self._task = loop.create_task(self._poll_loop())

    def _ensure_watchdog(self) -> None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        if self._watchdog_task is None or self._watchdog_task.done():
            self._watchdog_task = loop.create_task(self._watchdog_loop())

    def _build_idle_backoff_steps(self) -> list[float]:
        steps = [self._base_poll_interval, 10.0, 30.0, 60.0]
        normalized: list[float] = []
        for step in steps:
            if step < self._base_poll_interval:
                continue
            if step not in normalized:
                normalized.append(step)
        return normalized

    def _apply_poll_interval(self, interval: float, *, reason: str) -> None:
        if interval == self._current_poll_interval:
            return
        self._current_poll_interval = interval
        self._watchdog_interval = max(self._current_poll_interval * 2, 10.0)
        self._watchdog_alert_threshold = max(self._current_poll_interval * 6, 15.0)
        if self._scheduler is not None:
            job = self._scheduler.get_job(self._job_id)
            if job is not None:
                job.reschedule("interval", seconds=self._current_poll_interval)
        logger.info(
            "notification.worker.poll_interval_updated",
            extra={"interval": round(self._current_poll_interval, 2), "reason": reason},
        )

    def _reset_idle_backoff(self) -> None:
        if self._idle_backoff_index != 0:
            self._idle_backoff_index = 0
            self._apply_poll_interval(self._idle_backoff_steps[0], reason="work_found")

    def _advance_idle_backoff(self, reason: str) -> None:
        if self._idle_backoff_index < len(self._idle_backoff_steps) - 1:
            self._idle_backoff_index += 1
        next_interval = self._idle_backoff_steps[self._idle_backoff_index]
        self._apply_poll_interval(next_interval, reason=reason)

    def _record_db_unavailable(self, exc: Exception, *, context: str) -> None:
        now = time.monotonic()
        if now - self._last_db_error_ts < self._db_error_log_interval:
            return
        self._last_db_error_ts = now
        logger.warning(
            "notification.worker.db_unavailable",
            extra={"context": context, "error": str(exc)},
        )

    async def _stop_watchdog(self) -> None:
        if self._watchdog_task is None:
            return
        self._watchdog_task.cancel()
        try:
            await self._watchdog_task
        except asyncio.CancelledError:
            pass
        self._watchdog_task = None

    async def _await_scheduler_jobs(self) -> None:
        if not self._scheduler_jobs:
            return
        await asyncio.gather(*list(self._scheduler_jobs), return_exceptions=True)
        self._scheduler_jobs.clear()

    async def _watchdog_loop(self) -> None:
        try:
            while True:
                await asyncio.sleep(self._watchdog_interval)
                if not self._started or self._shutting_down:
                    return
                if self._scheduler is not None:
                    job = self._scheduler.get_job(self._job_id)
                    if job is None:
                        logger.warning("notification.worker.watchdog_job_missing")
                        try:
                            self._ensure_scheduler_job()
                        except Exception:
                            logger.exception("notification.worker.watchdog_job_restart_failed")
                            if not self._loop_enabled:
                                self._enable_poll_loop()
                    elif not self._scheduler.running:
                        try:
                            self._scheduler.start()
                        except SchedulerAlreadyRunningError:
                            pass
                        except Exception:
                            logger.exception("notification.worker.watchdog_scheduler_start_failed")
                elif self._loop_enabled:
                    if self._task is None or self._task.done():
                        logger.warning("notification.worker.watchdog_restart_loop")
                        self._enable_poll_loop()
                seconds_since_poll = None
                if self._last_poll_ts:
                    seconds_since_poll = max(0.0, time.monotonic() - self._last_poll_ts)
                    await record_notification_poll_staleness(seconds_since_poll)
                    if seconds_since_poll > self._watchdog_alert_threshold:
                        logger.warning(
                            "notification.worker.poll_stalled",
                            extra={"seconds_since_poll": round(seconds_since_poll, 2)},
                        )
                else:
                    await record_notification_poll_staleness(0.0)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("notification.worker.watchdog_failed")

    async def shutdown(self) -> None:
        self._shutting_down = True
        self._started = False
        self._loop_enabled = False
        await self._stop_watchdog()
        if self._scheduler is not None:
            try:
                self._scheduler.remove_job(self._job_id)
            except Exception:
                pass
        await self._await_scheduler_jobs()
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        for task in list(self._poll_tasks):
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._poll_tasks.clear()
        if self._broker is not None:
            try:
                await self._broker.close()
            except Exception:
                logger.exception("Failed to close notification broker")
        self._skipped_runs = 0
        self._last_poll_ts = 0.0
        self._shutting_down = False

    def _ensure_scheduler_job(self) -> None:
        if self._scheduler is None:
            return

        job = self._scheduler.get_job(self._job_id)
        misfire = max(int(self._current_poll_interval * 2), 1)
        if job is None:
            self._scheduler.add_job(
                run_scheduled_poll,
                "interval",
                seconds=self._current_poll_interval,
                id=self._job_id,
                replace_existing=True,
                coalesce=True,
                max_instances=1,
                misfire_grace_time=misfire,
                next_run_time=datetime.now(timezone.utc),
            )
        else:
            job.modify(max_instances=1, coalesce=True, misfire_grace_time=misfire)
            job.reschedule("interval", seconds=self._current_poll_interval)

        if not self._scheduler.running:
            try:
                self._scheduler.start()
            except SchedulerAlreadyRunningError:
                pass

    async def health_snapshot(self) -> Dict[str, Any]:
        broker_backend = "missing"
        broker_kind = None
        if self._broker is not None:
            broker_kind = self._broker.__class__.__name__
            broker_backend = "redis" if hasattr(self._broker, "_redis") else "memory"
        job_exists = bool(self._scheduler and self._scheduler.get_job(self._job_id))
        watchdog_running = self._watchdog_task is not None and not self._watchdog_task.done()
        seconds_since_poll = None
        if self._last_poll_ts:
            seconds_since_poll = max(0.0, time.monotonic() - self._last_poll_ts)
        rate_limit = None
        rate_capacity = None
        if self._token_bucket is not None:
            rate_limit = self._token_bucket.rate
            rate_capacity = self._token_bucket.capacity
        metrics = await get_notification_metrics_snapshot()
        return {
            "started": self._started,
            "loop_enabled": self._loop_enabled,
            "broker_backend": broker_backend,
            "broker_kind": broker_kind,
            "scheduler_job": job_exists,
            "watchdog_running": watchdog_running,
            "circuit_open": self._is_circuit_open(),
            "seconds_since_poll": seconds_since_poll,
            "rate_limit_per_sec": rate_limit,
            "rate_limit_capacity": rate_capacity,
            "worker_concurrency": self._worker_concurrency,
            "fatal_error_code": self._fatal_error_code,
            "fatal_error_at": (
                self._fatal_error_at.isoformat() if self._fatal_error_at is not None else None
            ),
            "last_delivery_error": self._last_delivery_error,
            "metrics": {
                "outbox_queue_depth": metrics.outbox_queue_depth,
                "poll_skipped_total": metrics.poll_skipped_total,
                "poll_skipped_reasons": metrics.poll_skipped_reasons,
                "poll_backoff_total": metrics.poll_backoff_total,
                "poll_backoff_reasons": metrics.poll_backoff_reasons,
                "poll_staleness_seconds": metrics.poll_staleness_seconds,
                "rate_limit_wait_total": metrics.rate_limit_wait_total,
                "rate_limit_wait_seconds": metrics.rate_limit_wait_seconds,
                "notifications_sent_total": metrics.notifications_sent_total,
                "notifications_failed_total": metrics.notifications_failed_total,
            },
        }

    async def metrics_snapshot(self) -> NotificationMetricsSnapshot:
        return await get_notification_metrics_snapshot()

    async def broker_ping(self) -> Optional[bool]:
        if self._broker is None:
            return None
        redis_client = getattr(self._broker, "_redis", None)
        if redis_client is None:
            return True
        try:
            result = await redis_client.ping()
            return bool(result)
        except Exception:
            logger.exception("notification.worker.broker_ping_failed")
            return False

    async def attach_broker(self, broker: NotificationBrokerProtocol) -> None:
        """Attach (or replace) the notification broker at runtime."""
        if broker is None:
            raise ValueError("broker must not be None")
        try:
            await broker.start()
        except Exception:
            logger.exception("notification.worker.broker_start_failed")
            raise
        if self._broker is not None and self._broker is not broker:
            try:
                await self._broker.close()
            except Exception:
                logger.exception("notification.worker.broker_close_failed")
        self._broker = broker
        self._last_poll_ts = 0.0

    async def detach_broker(self) -> None:
        """Detach current broker (used when Redis becomes unavailable)."""
        if self._broker is None:
            return
        try:
            await self._broker.close()
        except Exception:
            logger.exception("notification.worker.broker_close_failed")
        finally:
            self._broker = None


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
            return await self._queue_with_direct_fallback(
                notification_type="candidate_reschedule_prompt",
                booking_id=booking_id,
                candidate_id=candidate_id,
                payload=payload,
                snapshot=snapshot,
                status_value=status_value,
                queued_reason="reschedule_prompt_queued",
            )

        if status_value is BookingNotificationStatus.APPROVED:
            return await self._queue_with_direct_fallback(
                notification_type="interview_confirmed_candidate",
                booking_id=booking_id,
                candidate_id=candidate_id,
                payload=payload,
                snapshot=snapshot,
                status_value=status_value,
                queued_reason="interview_confirmed_queued",
            )

        if status_value is BookingNotificationStatus.CANCELLED:
            return await self._queue_with_direct_fallback(
                notification_type="candidate_rejection",
                booking_id=booking_id,
                candidate_id=candidate_id,
                payload=payload,
                snapshot=snapshot,
                status_value=status_value,
                queued_reason="rejection_queued",
            )

        return NotificationResult(status="skipped", reason=status_value.value)

    async def _queue_with_direct_fallback(
        self,
        *,
        notification_type: str,
        booking_id: Optional[int],
        candidate_id: int,
        payload: Dict[str, Any],
        snapshot: SlotSnapshot,
        status_value: BookingNotificationStatus,
        queued_reason: str,
    ) -> NotificationResult:
        outbox = await add_outbox_notification(
            notification_type=notification_type,
            booking_id=booking_id,
            candidate_tg_id=candidate_id,
            payload=payload,
        )
        enqueued = await self._enqueue_outbox(outbox.id, attempt=outbox.attempts)
        if enqueued:
            return NotificationResult(status="queued", reason=queued_reason)
        return await self._direct_or_fail(
            notification_type=notification_type,
            status_value=status_value,
            snapshot=snapshot,
            outbox_id=outbox.id,
            outbox_attempts=outbox.attempts,
            booking_id=booking_id or snapshot.slot_id,
            candidate_id=candidate_id,
        )

    async def _direct_or_fail(
        self,
        *,
        notification_type: str,
        status_value: BookingNotificationStatus,
        snapshot: SlotSnapshot,
        outbox_id: int,
        outbox_attempts: int,
        booking_id: Optional[int],
        candidate_id: Optional[int],
    ) -> NotificationResult:
        sent = await self._attempt_direct_delivery(status_value, snapshot)
        if sent:
            await self._finalize_direct_success(
                outbox_id,
                attempts=outbox_attempts,
                booking_id=booking_id,
                notification_type=notification_type,
                candidate_id=candidate_id,
            )
            logger.warning(
                "notification.direct_delivery",
                extra={
                    "notification_type": notification_type,
                    "booking_id": booking_id,
                    "candidate_tg_id": candidate_id,
                },
            )
            return NotificationResult(status="sent", reason=DIRECT_NO_BROKER_REASON)

        await update_outbox_entry(
            outbox_id,
            status="failed",
            attempts=outbox_attempts,
            next_retry_at=None,
            last_error=BROKER_UNAVAILABLE_REASON,
        )
        await record_notification_failed(notification_type)
        logger.error(
            "notification.direct_delivery_failed",
            extra={
                "notification_type": notification_type,
                "booking_id": booking_id,
                "candidate_tg_id": candidate_id,
            },
        )
        return NotificationResult(status="failed", reason=BROKER_UNAVAILABLE_REASON)

    async def _attempt_direct_delivery(
        self,
        status_value: BookingNotificationStatus,
        snapshot: SlotSnapshot,
    ) -> bool:
        await self._throttle()
        if status_value is BookingNotificationStatus.RESCHEDULE_REQUESTED:
            return await notify_reschedule(snapshot)
        if status_value is BookingNotificationStatus.APPROVED:
            slot = await get_slot(snapshot.slot_id)
            if not slot or not slot.candidate_tg_id:
                return False
            rendered_text, _candidate_tz, _candidate_city, _template_key, _template_version = await _render_candidate_notification(
                slot
            )
            try:
                await _send_with_retry(
                    get_bot(),
                    SendMessage(chat_id=slot.candidate_tg_id, text=rendered_text),
                    correlation_id=f"direct-approve:{slot.id}:{uuid.uuid4().hex}",
                )
            except Exception:
                logger.exception("Failed direct delivery for approved booking", extra={"slot_id": slot.id})
                return False
            try:
                reminder_service = get_reminder_service()
            except RuntimeError:
                reminder_service = None
            if reminder_service is not None:
                await reminder_service.schedule_for_slot(slot.id)
            return True
        if status_value is BookingNotificationStatus.CANCELLED:
            return await notify_rejection(snapshot)
        return False

    async def _finalize_direct_success(
        self,
        outbox_id: int,
        *,
        attempts: int,
        booking_id: Optional[int],
        notification_type: str,
        candidate_id: Optional[int],
    ) -> None:
        final_attempts = max(1, attempts + 1)
        await update_outbox_entry(
            outbox_id,
            status="sent",
            attempts=final_attempts,
            next_retry_at=None,
            last_error=None,
        )
        log_type = (
            "candidate_interview_confirmed"
            if notification_type == "interview_confirmed_candidate"
            else notification_type
        )
        if booking_id:
            try:
                await add_notification_log(
                    log_type,
                    booking_id,
                    candidate_tg_id=candidate_id,
                    payload=DIRECT_NO_BROKER_REASON,
                    delivery_status="sent",
                    attempts=final_attempts,
                    last_error=None,
                    overwrite=True,
                )
            except IntegrityError:
                logger.debug(
                    "notification.direct.log_duplicate",
                    extra={"booking_id": booking_id, "notification_type": notification_type},
                )
            except Exception:
                logger.exception(
                    "notification.direct.log_failed",
                    extra={"booking_id": booking_id, "notification_type": notification_type},
                )
        await record_notification_sent(notification_type)

    async def retry_notification(self, outbox_id: int) -> "NotificationResult":
        await reset_outbox_entry(outbox_id)
        success = await self._enqueue_outbox(outbox_id, attempt=0)
        if not success:
            return NotificationResult(status="failed", reason=BROKER_UNAVAILABLE_REASON)
        return NotificationResult(status="queued")

    async def _poll_loop(self) -> None:
        delay = self._current_poll_interval
        try:
            while True:
                try:
                    await self._poll_once()
                    delay = self._current_poll_interval
                except asyncio.CancelledError:
                    raise
                except asyncio.TimeoutError:
                    delay = self._compute_poll_backoff(delay, reason="transient")
                    await record_notification_poll_backoff("transient_error", delay)
                    logger.warning(
                        "notification.worker.loop_iteration_retry",
                        extra={"reason": "timeout", "delay": round(delay, 2)},
                    )
                except Exception:
                    delay = self._compute_poll_backoff(delay, reason="fatal")
                    await record_notification_poll_backoff("fatal_error", delay)
                    logger.exception("notification.worker.loop_iteration_failed")
                    self._open_circuit()
                await asyncio.sleep(delay)
        except asyncio.CancelledError:
            raise

    async def _scheduled_poll(self) -> None:
        current_task = asyncio.current_task()
        if current_task is not None:
            self._scheduler_jobs.add(current_task)
        self._poll_tasks = {task for task in self._poll_tasks if not task.done()}
        try:
            if not self._started or self._shutting_down:
                return
            if len(self._poll_tasks) >= self._worker_concurrency:
                await self._handle_poll_skipped(reason="lock_busy")
                return
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                logger.warning("notification.worker.loop_unavailable")
                await self._handle_poll_skipped(reason="no_loop")
                return

            if self._shutting_down:
                return
            task = loop.create_task(self._poll_once())
            self._poll_tasks.add(task)
            task.add_done_callback(self._on_poll_task_done)
        finally:
            if current_task is not None:
                self._scheduler_jobs.discard(current_task)

    def _on_poll_task_done(self, task: asyncio.Task) -> None:
        self._poll_tasks.discard(task)
        if task.cancelled():
            return
        exc = task.exception()
        if exc is not None:
            logger.exception("notification.worker.poll_failed", exc_info=exc)

    async def _handle_poll_skipped(self, *, reason: str) -> None:
        self._skipped_runs += 1
        duration_ms = None
        if self._last_poll_ts:
            duration_ms = int(max(0.0, time.monotonic() - self._last_poll_ts) * 1000)
        logger.info(
            "notification.worker.poll_skipped",
            extra={
                "reason": reason,
                "skipped_total": self._skipped_runs,
                "duration_ms": duration_ms,
            },
        )
        await record_notification_poll_skipped(reason=reason, skipped_total=self._skipped_runs)

    async def _poll_once(self) -> None:
        start = time.perf_counter()
        processed = 0
        source = "idle"
        started_at = datetime.now(timezone.utc).isoformat()
        broker_available = self._broker is not None

        logger.info(
            "notification.worker.poll_start",
            extra={"started_at": started_at, "skipped_total": self._skipped_runs},
        )

        previous_poll_ts = self._last_poll_ts
        try:
            async with self._poll_gate:
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
            now_ts = time.monotonic()
            seconds_since_prev = 0.0
            if previous_poll_ts:
                seconds_since_prev = max(0.0, now_ts - previous_poll_ts)
            self._last_poll_ts = now_ts
            if processed == 0 and source in {"broker_idle", "outbox_idle", "db_unavailable"}:
                now = time.monotonic()
                if now - self._last_idle_log_ts >= self._idle_log_interval:
                    self._last_idle_log_ts = now
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
                    if source == "db_unavailable":
                        idle_reason = "db_unavailable"
                    else:
                        idle_reason = "broker_unavailable" if not broker_available else "no_work"
                    logger.info(
                        "notification.worker.poll_skipped",
                        extra={
                            "reason": idle_reason,
                            "skipped_total": self._skipped_runs,
                            "duration_ms": int(duration * 1000),
                        },
                    )
            else:
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
            if processed > 0:
                self._reset_idle_backoff()
            elif source == "broker_idle":
                self._advance_idle_backoff(reason="broker_idle")
            elif source == "db_unavailable":
                self._advance_idle_backoff(reason="db_unavailable")
            await record_notification_poll_cycle(
                duration=duration,
                processed=processed,
                source=source,
                skipped_total=self._skipped_runs,
                seconds_since_poll=seconds_since_prev,
            )
            await record_notification_poll_staleness(0.0)

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
            logger.error(
                "notification.worker.enqueue_missing_broker",
                extra={"outbox_id": outbox_id, "attempt": attempt},
            )
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

        block_ms = int(self._current_poll_interval * 1000)
        messages = await self._broker.read(count=self._batch_size, block_ms=block_ms)
        source = "broker"

        if not messages:
            source = "broker_idle"
            messages = await self._broker.claim_stale(
                min_idle_ms=self._claim_idle_ms,
                count=self._batch_size,
            )

        if not messages:
            try:
                enqueued = await self._enqueue_due_outbox_batch()
            except (OperationalError, ConnectionRefusedError, OSError) as exc:
                self._record_db_unavailable(exc, context="enqueue_due_outbox_batch")
                return 0, "db_unavailable"
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

        try:
            items = await claim_outbox_batch(batch_size=self._batch_size)
        except (OperationalError, ConnectionRefusedError, OSError) as exc:
            self._record_db_unavailable(exc, context="claim_outbox_batch")
            await set_outbox_queue_depth(0)
            return 0, "db_unavailable"
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
        try:
            items = await claim_outbox_batch(batch_size=self._batch_size)
        except (OperationalError, ConnectionRefusedError, OSError) as exc:
            self._record_db_unavailable(exc, context="claim_outbox_batch")
            await set_outbox_queue_depth(0)
            return 0, "db_unavailable"
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
            "test2_completed": self._process_test2_completed,
            "slot_proposal": self._process_slot_proposal,
            "slot_confirmed_recruiter": self._process_slot_confirmed_recruiter,
            "reschedule_requested_recruiter": self._process_reschedule_requested_recruiter,
            "reschedule_approved_candidate": self._process_reschedule_approved_candidate,
            "reschedule_declined_candidate": self._process_reschedule_declined_candidate,
            "slot_assignment_offer": self._process_slot_assignment_offer,
            "slot_assignment_reschedule_approved": self._process_slot_assignment_reschedule_approved,
            "slot_assignment_reschedule_declined": self._process_slot_assignment_reschedule_declined,
            "slot_assignment_reschedule_requested": self._process_slot_assignment_reschedule_requested,
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
        except TelegramUnauthorizedError:
            await self._mark_failed(
                item,
                max(1, item.attempts + 1),
                item.type,
                item.type,
                "telegram_unauthorized",
                None,
                candidate_tg_id=item.candidate_tg_id,
            )
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

    async def _process_slot_proposal(self, item: OutboxItem) -> None:
        """Processes a slot proposal notification to a candidate."""
        payload = dict(item.payload or {})
        candidate_id = item.candidate_tg_id
        if not candidate_id:
            await self._mark_failed(item, item.attempts, "slot_proposal", "slot_proposal", "candidate_missing", None, candidate_tg_id=None)
            return

        assignment_id = payload.get("assignment_id")
        start_utc_str = payload.get("start_utc")
        
        if not assignment_id or not start_utc_str:
            await self._mark_failed(item, item.attempts, "slot_proposal", "slot_proposal", "payload_incomplete", None, candidate_tg_id=candidate_id)
            return
            
        start_utc = datetime.fromisoformat(start_utc_str)

        context = {"dt_local": fmt_dt_local(start_utc, "Europe/Moscow")} # Assume Moscow, should be candidate's TZ
        rendered = await self._template_provider.render("slot_proposal_candidate", context)

        if rendered is None:
            await self._mark_failed(item, item.attempts, "slot_proposal", "slot_proposal", "template_missing", None, candidate_tg_id=candidate_id)
            return

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"confirm_assignment:{assignment_id}")],
            [InlineKeyboardButton(text="🗓️ Другое время", callback_data=f"reschedule_assignment:{assignment_id}")]
        ])

        attempt = item.attempts + 1
        try:
            await get_bot().send_message(candidate_id, rendered.text, reply_markup=keyboard)
        except Exception as exc:
            await self._schedule_retry(item, attempt=attempt, log_type="slot_proposal", notification_type="slot_proposal", error=str(exc), rendered=rendered, candidate_tg_id=candidate_id)
            return

        await self._mark_sent(item, attempt, "slot_proposal", "slot_proposal", rendered, candidate_id)

    async def _process_slot_confirmed_recruiter(self, item: OutboxItem) -> None:
        """Notifies a recruiter that a candidate has confirmed a slot."""
        recruiter_chat_id = item.recruiter_tg_id
        if not recruiter_chat_id:
            await self._mark_failed(
                item,
                item.attempts,
                "slot_confirmed_recruiter",
                "slot_confirmed_recruiter",
                "recruiter_missing",
                None,
            )
            return

        payload = dict(item.payload or {})
        slot_id = payload.get("slot_id") or item.booking_id
        slot = await get_slot(int(slot_id)) if slot_id else None
        candidate_name = "Кандидат"
        dt_local = None
        if slot is not None:
            candidate_name = slot.candidate_fio or slot.candidate_id or candidate_name
            dt_local = fmt_dt_local(slot.start_utc, slot.candidate_tz or DEFAULT_TZ)

        context = {
            "candidate_name": escape_html(str(candidate_name)),
            "dt_local": dt_local or "",
        }
        rendered = await self._template_provider.render("slot_confirmed_recruiter", context)
        text = rendered.text if rendered is not None else "Кандидат подтвердил слот."

        attempt = item.attempts + 1
        await self._throttle()
        try:
            await _send_with_retry(
                get_bot(),
                SendMessage(chat_id=recruiter_chat_id, text=text),
                correlation_id=f"outbox:{item.type}:{item.id}:{uuid.uuid4().hex}",
            )
        except Exception as exc:
            await self._schedule_retry(
                item,
                attempt=attempt,
                log_type="slot_confirmed_recruiter",
                notification_type="slot_confirmed_recruiter",
                error=str(exc),
                rendered=rendered,
                candidate_tg_id=item.candidate_tg_id,
            )
            return

        self._last_delivery_error = None
        await update_outbox_entry(
            item.id,
            status="sent",
            attempts=attempt,
            next_retry_at=None,
            last_error=None,
        )
        await record_notification_sent("slot_confirmed_recruiter")

    async def _process_reschedule_requested_recruiter(self, item: OutboxItem) -> None:
        """Notifies a recruiter that a candidate has requested a reschedule."""
        recruiter_chat_id = item.recruiter_tg_id
        if not recruiter_chat_id:
            await self._mark_failed(
                item,
                item.attempts,
                "reschedule_requested_recruiter",
                "reschedule_requested_recruiter",
                "recruiter_missing",
                None,
            )
            return

        payload = dict(item.payload or {})
        assignment_id_raw = payload.get("slot_assignment_id") or payload.get("assignment_id")
        assignment_id = None
        try:
            assignment_id = int(assignment_id_raw) if assignment_id_raw is not None else None
        except (TypeError, ValueError):
            assignment_id = None

        if assignment_id is None and item.booking_id is None and payload.get("slot_id") is None:
            await self._mark_failed(
                item,
                max(1, item.attempts + 1),
                "reschedule_requested_recruiter",
                "reschedule_requested_recruiter",
                "context_missing",
                None,
                candidate_tg_id=item.candidate_tg_id,
            )
            return

        assignment = None
        # Legacy outbox entries may outlive their originating assignment; don't spam recruiters in that case.
        if assignment_id is not None:
            from backend.domain.models import SlotAssignment
            from backend.core.db import async_session

            async with async_session() as session:
                assignment = await session.get(SlotAssignment, assignment_id)
            if assignment is None:
                await self._mark_failed(
                    item,
                    max(1, item.attempts + 1),
                    "reschedule_requested_recruiter",
                    "reschedule_requested_recruiter",
                    "assignment_missing",
                    None,
                    candidate_tg_id=item.candidate_tg_id,
                )
                return
        candidate_tg_id = item.candidate_tg_id or getattr(assignment, "candidate_tg_id", None)

        requested_raw = (
            payload.get("requested_start_utc")
            or payload.get("requested_time_utc")
            or payload.get("requested_time")
        )
        requested_utc = None
        if requested_raw:
            try:
                requested_utc = datetime.fromisoformat(str(requested_raw))
                if requested_utc.tzinfo is None:
                    requested_utc = requested_utc.replace(tzinfo=timezone.utc)
                else:
                    requested_utc = requested_utc.astimezone(timezone.utc)
            except Exception:
                requested_utc = None

        recruiter = await get_recruiter_by_chat_id(recruiter_chat_id)
        tz_label = (getattr(recruiter, "tz", None) or DEFAULT_TZ) if recruiter else DEFAULT_TZ
        requested_time_local = (
            fmt_dt_local(requested_utc, tz_label) if requested_utc is not None else ""
        )
        candidate_name = payload.get("candidate_name") or payload.get("candidate_fio")
        if not candidate_name:
            slot_id_raw = payload.get("slot_id") or item.booking_id or getattr(assignment, "slot_id", None)
            try:
                slot_id = int(slot_id_raw) if slot_id_raw is not None else None
            except (TypeError, ValueError):
                slot_id = None

            if slot_id is not None:
                from backend.domain.models import Slot
                from backend.core.db import async_session

                async with async_session() as session:
                    slot = await session.get(Slot, slot_id)
                if slot is not None and getattr(slot, "candidate_fio", None):
                    candidate_name = slot.candidate_fio
                if candidate_tg_id is None:
                    candidate_tg_id = getattr(slot, "candidate_tg_id", None)

        if not candidate_name:
            candidate_name = getattr(assignment, "candidate_id", None) or (
                str(candidate_tg_id) if candidate_tg_id is not None else None
            )

        if not candidate_name:
            await self._mark_failed(
                item,
                max(1, item.attempts + 1),
                "reschedule_requested_recruiter",
                "reschedule_requested_recruiter",
                "candidate_missing",
                None,
                candidate_tg_id=candidate_tg_id,
            )
            return

        context = {
            "candidate_name": escape_html(str(candidate_name)),
            "requested_time_local": requested_time_local,
        }
        rendered = await self._template_provider.render("reschedule_requested_recruiter", context)
        if rendered is not None and rendered.text:
            text = rendered.text
        else:
            details = []
            if candidate_name:
                details.append(f"👤 {escape_html(str(candidate_name))}")
            if requested_time_local:
                details.append(f"🗓 {escape_html(str(requested_time_local))}")
            if details:
                text = "🔁 Кандидат запросил другое время\n" + "\n".join(details)
            else:
                text = "Кандидат запросил другое время."

        attempt = item.attempts + 1
        await self._throttle()
        try:
            await _send_with_retry(
                get_bot(),
                SendMessage(chat_id=recruiter_chat_id, text=text),
                correlation_id=f"outbox:{item.type}:{item.id}:{uuid.uuid4().hex}",
            )
        except Exception as exc:
            await self._schedule_retry(
                item,
                attempt=attempt,
                log_type="reschedule_requested_recruiter",
                notification_type="reschedule_requested_recruiter",
                error=str(exc),
                rendered=rendered,
                candidate_tg_id=candidate_tg_id,
            )
            return

        self._last_delivery_error = None
        await update_outbox_entry(
            item.id,
            status="sent",
            attempts=attempt,
            next_retry_at=None,
            last_error=None,
        )
        await record_notification_sent("reschedule_requested_recruiter")
        
    async def _process_reschedule_approved_candidate(self, item: OutboxItem) -> None:
        """Notifies a candidate their reschedule request was approved."""
        candidate_id = item.candidate_tg_id
        if not candidate_id:
            await self._mark_failed(
                item,
                item.attempts,
                "reschedule_approved_candidate",
                "reschedule_approved_candidate",
                "candidate_missing",
                None,
                candidate_tg_id=None,
            )
            return

        payload = dict(item.payload or {})
        new_time_raw = payload.get("new_time_utc") or payload.get("new_start_utc")
        new_time_utc = None
        if new_time_raw:
            try:
                new_time_utc = datetime.fromisoformat(str(new_time_raw))
                if new_time_utc.tzinfo is None:
                    new_time_utc = new_time_utc.replace(tzinfo=timezone.utc)
                else:
                    new_time_utc = new_time_utc.astimezone(timezone.utc)
            except Exception:
                new_time_utc = None

        tz_label = payload.get("candidate_tz") or DEFAULT_TZ
        new_time_local = fmt_dt_local(new_time_utc, tz_label) if new_time_utc else ""
        context = {"new_time_local": new_time_local}
        rendered = await self._template_provider.render("reschedule_approved_candidate", context)
        text = rendered.text if rendered is not None else "Ваш запрос на перенос одобрен."

        attempt = item.attempts + 1
        await self._throttle()
        try:
            await _send_with_retry(
                get_bot(),
                SendMessage(chat_id=candidate_id, text=text),
                correlation_id=f"outbox:{item.type}:{item.id}:{uuid.uuid4().hex}",
            )
        except Exception as exc:
            await self._schedule_retry(
                item,
                attempt=attempt,
                log_type="reschedule_approved_candidate",
                notification_type="reschedule_approved_candidate",
                error=str(exc),
                rendered=rendered,
                candidate_tg_id=candidate_id,
            )
            return

        self._last_delivery_error = None
        await update_outbox_entry(
            item.id,
            status="sent",
            attempts=attempt,
            next_retry_at=None,
            last_error=None,
        )
        await record_notification_sent("reschedule_approved_candidate")

    async def _process_reschedule_declined_candidate(self, item: OutboxItem) -> None:
        """Notifies a candidate their reschedule request was declined."""
        candidate_id = item.candidate_tg_id
        if not candidate_id:
            await self._mark_failed(
                item,
                item.attempts,
                "reschedule_declined_candidate",
                "reschedule_declined_candidate",
                "candidate_missing",
                None,
                candidate_tg_id=None,
            )
            return

        payload = dict(item.payload or {})
        recruiter_comment = payload.get("recruiter_comment") or ""
        context = {"recruiter_comment": escape_html(str(recruiter_comment))}
        rendered = await self._template_provider.render("reschedule_declined_candidate", context)
        text = rendered.text if rendered is not None else "Ваш запрос на перенос отклонен."

        attempt = item.attempts + 1
        await self._throttle()
        try:
            await _send_with_retry(
                get_bot(),
                SendMessage(chat_id=candidate_id, text=text),
                correlation_id=f"outbox:{item.type}:{item.id}:{uuid.uuid4().hex}",
            )
        except Exception as exc:
            await self._schedule_retry(
                item,
                attempt=attempt,
                log_type="reschedule_declined_candidate",
                notification_type="reschedule_declined_candidate",
                error=str(exc),
                rendered=rendered,
                candidate_tg_id=candidate_id,
            )
            return

        self._last_delivery_error = None
        await update_outbox_entry(
            item.id,
            status="sent",
            attempts=attempt,
            next_retry_at=None,
            last_error=None,
        )
        await record_notification_sent("reschedule_declined_candidate")

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

    async def _process_test2_completed(self, item: OutboxItem) -> None:
        await update_outbox_entry(
            item.id,
            status="sent",
            attempts=item.attempts,
            next_retry_at=None,
            last_error=None,
        )

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
            "candidate_reschedule_prompt",
            context,
            city_id=snapshot.candidate_city_id,
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
            "candidate_rejection",
            context,
            city_id=snapshot.candidate_city_id,
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
            "recruiter_candidate_confirmed_notice",
            context,
            city_id=getattr(slot, "city_id", None),
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
            reminder_kind = ReminderKind.CONFIRM_2H

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
        intro_address_safe, _ = _intro_detail(
            getattr(slot, "intro_address", None),
            fallback=None,
            default=INTRO_ADDRESS_FALLBACK,
        )
        recruiter_contact_fallback = recruiter.name if recruiter else None
        intro_contact_safe, _ = _intro_detail(
            getattr(slot, "intro_contact", None),
            fallback=recruiter_contact_fallback,
            default=INTRO_CONTACT_FALLBACK,
        )
        context.update(
            {
                "intro_address": intro_address_safe,
                "intro_contact": intro_contact_safe,
            }
        )
        if (
            reminder_kind is ReminderKind.INTRO_REMIND_3H
            or (slot.purpose or "").lower() == "intro_day"
        ):
            context.update(
                {
                    "address": intro_address_safe,
                    "city_address": intro_address_safe,
                    "recruiter_contact": intro_contact_safe,
                }
            )

        confirm_map = {
            ReminderKind.CONFIRM_6H: "confirm_6h",
            ReminderKind.CONFIRM_3H: "confirm_3h",
            ReminderKind.CONFIRM_2H: "confirm_2h",
            ReminderKind.REMIND_2H: "confirm_2h",
        }

        if reminder_kind is ReminderKind.INTRO_REMIND_3H:
            template_key = "intro_day_reminder"
            reply_markup = kb_attendance_confirm(slot.id)
        elif reminder_kind in confirm_map:
            template_key = confirm_map[reminder_kind]
            reply_markup = kb_attendance_confirm(slot.id)
        elif reminder_kind is ReminderKind.REMIND_24H:
            await self._mark_sent(
                item,
                item.attempts + 1,
                log_type,
                notification_type,
                None,
                candidate_id,
            )
            return
        else:
            await self._mark_sent(
                item,
                item.attempts + 1,
                log_type,
                notification_type,
                None,
                candidate_id,
            )
            return

        rendered = await self._template_provider.render(
            template_key, context, city_id=getattr(slot, "candidate_city_id", None)
        )
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

    async def _process_slot_assignment_offer(self, item: OutboxItem) -> None:
        payload = dict(item.payload or {})
        candidate_id = item.candidate_tg_id or payload.get("candidate_tg_id")
        if not candidate_id:
            await self._mark_failed(
                item,
                item.attempts,
                "slot_assignment_offer",
                "slot_assignment_offer",
                "candidate_missing",
                None,
                candidate_tg_id=None,
            )
            return

        assignment_id = payload.get("slot_assignment_id")
        tokens = (payload.get("action_tokens") or {})
        confirm_token = tokens.get("confirm")
        reschedule_token = tokens.get("reschedule")
        decline_token = tokens.get("decline")
        if not assignment_id or not confirm_token or not reschedule_token:
            await self._mark_failed(
                item,
                item.attempts,
                "slot_assignment_offer",
                "slot_assignment_offer",
                "payload_incomplete",
                None,
                candidate_tg_id=candidate_id,
            )
            return

        start_raw = payload.get("start_utc")
        try:
            start_utc = datetime.fromisoformat(start_raw) if start_raw else None
        except Exception:
            start_utc = None
        if start_utc is None:
            await self._mark_failed(
                item,
                item.attempts,
                "slot_assignment_offer",
                "slot_assignment_offer",
                "start_missing",
                None,
                candidate_tg_id=candidate_id,
            )
            return

        candidate_tz = payload.get("candidate_tz") or DEFAULT_TZ
        dt_label = fmt_dt_local(start_utc, candidate_tz)
        recruiter_name = payload.get("recruiter_name") or ""
        city_name = payload.get("city_name") or ""
        comment = payload.get("comment")
        is_alternative = bool(payload.get("is_alternative"))

        title = "🔁 Предлагаем другое время" if is_alternative else "📅 Предлагаем время собеседования"
        text = f"{title}\n🗓 {dt_label}"
        if recruiter_name:
            text += f"\n👤 {escape_html(recruiter_name)}"
        if city_name:
            text += f"\n📍 {escape_html(city_name)}"
        if comment:
            text += f"\n\nКомментарий: {escape_html(str(comment))}"
        if decline_token:
            text += "\n\nПодтвердите, выберите другое время или откажитесь."
        else:
            text += "\n\nПодтвердите или выберите другое время."

        keyboard = kb_slot_assignment_offer(
            int(assignment_id),
            confirm_token=str(confirm_token),
            reschedule_token=str(reschedule_token),
            decline_token=str(decline_token) if decline_token else None,
        )

        attempt = item.attempts + 1
        await self._throttle()
        try:
            await get_bot().send_message(candidate_id, text, reply_markup=keyboard)
        except Exception as exc:
            await self._schedule_retry(
                item,
                attempt=attempt,
                log_type="slot_assignment_offer",
                notification_type="slot_assignment_offer",
                error=str(exc),
                rendered=None,
                candidate_tg_id=candidate_id,
            )
            return

        await update_outbox_entry(
            item.id,
            status="sent",
            attempts=attempt,
            next_retry_at=None,
            last_error=None,
        )

        try:
            await add_message_log(
                "slot_assignment_offer",
                recipient_type="candidate",
                recipient_id=candidate_id,
                slot_assignment_id=int(assignment_id),
                payload={"slot_id": payload.get("slot_id"), "text": text},
            )
        except Exception:
            logger.exception("Failed to persist message log for slot assignment offer")

        # Update state so free-text handler can capture reschedule input.
        try:
            state_manager = get_state_manager()
            await state_manager.update(
                candidate_id,
                {
                    "slot_assignment_state": "waiting_candidate",
                    "slot_assignment_id": int(assignment_id),
                    "slot_assignment_candidate_tz": candidate_tz,
                },
            )
        except Exception:
            logger.exception("Failed to update candidate state for slot assignment offer")

    async def _process_slot_assignment_reschedule_approved(self, item: OutboxItem) -> None:
        payload = dict(item.payload or {})
        candidate_id = item.candidate_tg_id
        if not candidate_id:
            await self._mark_failed(
                item,
                item.attempts,
                "slot_assignment_reschedule_approved",
                "slot_assignment_reschedule_approved",
                "candidate_missing",
                None,
                candidate_tg_id=None,
            )
            return

        start_raw = payload.get("start_utc")
        try:
            start_utc = datetime.fromisoformat(start_raw) if start_raw else None
        except Exception:
            start_utc = None
        if start_utc is None:
            await self._mark_failed(
                item,
                item.attempts,
                "slot_assignment_reschedule_approved",
                "slot_assignment_reschedule_approved",
                "start_missing",
                None,
                candidate_tg_id=candidate_id,
            )
            return

        candidate_tz = payload.get("candidate_tz") or DEFAULT_TZ
        dt_label = fmt_dt_local(start_utc, candidate_tz)
        comment = payload.get("comment")

        text = f"✅ Перенос подтверждён.\n🗓 Новое время: {dt_label}"
        if comment:
            text += f"\n\nКомментарий: {escape_html(str(comment))}"

        attempt = item.attempts + 1
        await self._throttle()
        try:
            await get_bot().send_message(candidate_id, text)
        except Exception as exc:
            await self._schedule_retry(
                item,
                attempt=attempt,
                log_type="slot_assignment_reschedule_approved",
                notification_type="slot_assignment_reschedule_approved",
                error=str(exc),
                rendered=None,
                candidate_tg_id=candidate_id,
            )
            return

        await update_outbox_entry(
            item.id,
            status="sent",
            attempts=attempt,
            next_retry_at=None,
            last_error=None,
        )

        try:
            await add_message_log(
                "slot_assignment_reschedule_approved",
                recipient_type="candidate",
                recipient_id=candidate_id,
                slot_assignment_id=payload.get("slot_assignment_id"),
                payload={"slot_id": payload.get("slot_id"), "text": text},
            )
        except Exception:
            logger.exception("Failed to persist message log for reschedule approved")

    async def _process_slot_assignment_reschedule_declined(self, item: OutboxItem) -> None:
        payload = dict(item.payload or {})
        candidate_id = item.candidate_tg_id
        if not candidate_id:
            await self._mark_failed(
                item,
                item.attempts,
                "slot_assignment_reschedule_declined",
                "slot_assignment_reschedule_declined",
                "candidate_missing",
                None,
                candidate_tg_id=None,
            )
            return

        comment = payload.get("comment")
        text = "⛔️ Запрос на перенос отклонён."
        if comment:
            text += f"\n\nКомментарий: {escape_html(str(comment))}"
        text += "\nЕсли время всё ещё подходит, подтвердите его в предыдущем сообщении."

        attempt = item.attempts + 1
        await self._throttle()
        try:
            await get_bot().send_message(candidate_id, text)
        except Exception as exc:
            await self._schedule_retry(
                item,
                attempt=attempt,
                log_type="slot_assignment_reschedule_declined",
                notification_type="slot_assignment_reschedule_declined",
                error=str(exc),
                rendered=None,
                candidate_tg_id=candidate_id,
            )
            return

        await update_outbox_entry(
            item.id,
            status="sent",
            attempts=attempt,
            next_retry_at=None,
            last_error=None,
        )

        try:
            await add_message_log(
                "slot_assignment_reschedule_declined",
                recipient_type="candidate",
                recipient_id=candidate_id,
                slot_assignment_id=payload.get("slot_assignment_id"),
                payload={"slot_id": payload.get("slot_id"), "text": text},
            )
        except Exception:
            logger.exception("Failed to persist message log for reschedule declined")

    async def _process_slot_assignment_reschedule_requested(self, item: OutboxItem) -> None:
        payload = dict(item.payload or {})
        recruiter_id = payload.get("recruiter_id")
        recruiter = await get_recruiter(recruiter_id) if recruiter_id else None
        if recruiter is None or recruiter.tg_chat_id is None:
            await self._mark_failed(
                item,
                item.attempts,
                "slot_assignment_reschedule_requested",
                "slot_assignment_reschedule_requested",
                "recruiter_chat_missing",
                None,
                candidate_tg_id=item.candidate_tg_id,
            )
            return

        requested_raw = payload.get("requested_start_utc")
        try:
            requested_utc = datetime.fromisoformat(requested_raw) if requested_raw else None
        except Exception:
            requested_utc = None
        if requested_utc is None:
            await self._mark_failed(
                item,
                item.attempts,
                "slot_assignment_reschedule_requested",
                "slot_assignment_reschedule_requested",
                "start_missing",
                None,
                candidate_tg_id=item.candidate_tg_id,
            )
            return

        candidate_name = payload.get("candidate_name") or payload.get("candidate_id") or "Кандидат"
        candidate_tz = payload.get("candidate_tz") or recruiter.tz or DEFAULT_TZ
        dt_label = fmt_dt_local(requested_utc, recruiter.tz or candidate_tz or DEFAULT_TZ)
        comment = payload.get("comment")

        text = (
            "🔁 Кандидат запросил другое время\n"
            f"👤 {escape_html(str(candidate_name))}\n"
            f"🗓 {dt_label}\n"
            "Откройте CRM, чтобы подтвердить, предложить другое время или отклонить."
        )
        if comment:
            text += f"\nКомментарий: {escape_html(str(comment))}"

        attempt = item.attempts + 1
        await self._throttle()
        try:
            await get_bot().send_message(recruiter.tg_chat_id, text)
        except Exception as exc:
            await self._schedule_retry(
                item,
                attempt=attempt,
                log_type="slot_assignment_reschedule_requested",
                notification_type="slot_assignment_reschedule_requested",
                error=str(exc),
                rendered=None,
                candidate_tg_id=item.candidate_tg_id,
            )
            return

        await update_outbox_entry(
            item.id,
            status="sent",
            attempts=attempt,
            next_retry_at=None,
            last_error=None,
        )

        try:
            await add_message_log(
                "slot_assignment_reschedule_requested",
                recipient_type="recruiter",
                recipient_id=recruiter.tg_chat_id,
                slot_assignment_id=payload.get("slot_assignment_id"),
                payload={"slot_id": payload.get("slot_id"), "text": text},
            )
        except Exception:
            logger.exception("Failed to persist message log for reschedule requested")

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
        city_intro_address = getattr(city, "intro_address", None) if city else None
        city_contact_name = getattr(city, "contact_name", None) if city else None
        city_contact_phone = getattr(city, "contact_phone", None) if city else None

        recruiter_contact_fallback = recruiter.name if recruiter else None
        # Build city-level contact fallback from contact_name + contact_phone
        city_contact_fallback = None
        if city_contact_name and city_contact_phone:
            city_contact_fallback = f"{city_contact_name}, {city_contact_phone}"
        elif city_contact_name:
            city_contact_fallback = city_contact_name
        elif city_contact_phone:
            city_contact_fallback = city_contact_phone

        intro_address_safe, _ = _intro_detail(
            getattr(slot, "intro_address", None),
            fallback=city_intro_address or city_name,
            default=INTRO_ADDRESS_FALLBACK,
        )
        intro_contact_safe, _ = _intro_detail(
            getattr(slot, "intro_contact", None),
            fallback=city_contact_fallback or recruiter_contact_fallback,
            default=INTRO_CONTACT_FALLBACK,
        )
        context.update(
            {
                "intro_address": intro_address_safe,
                "intro_contact": intro_contact_safe,
                "address": intro_address_safe,
                "city_address": intro_address_safe,
                "recruiter_contact": intro_contact_safe,
                "contact_name": city_contact_name or (recruiter.name if recruiter else ""),
                "contact_phone": city_contact_phone or "",
            }
        )

        # Use custom_message from admin UI when provided (preview = actual text)
        custom_message = (item.payload or {}).get("custom_message")
        if custom_message and str(custom_message).strip():
            from types import SimpleNamespace
            rendered = SimpleNamespace(
                text=str(custom_message).strip(),
                key="intro_day_invitation_custom",
                version=None,
            )
        else:
            # Try to render a city-specific template only when it actually exists to avoid
            # silently downgrading to the generic status message.
            template_key = "intro_day_invitation"
            rendered = await self._template_provider.render(
                template_key, context, city_id=slot.candidate_city_id
            )

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

        # Update candidate status to INTRO_DAY_SCHEDULED after successful send
        try:
            from backend.domain.candidates.status_service import set_status_intro_day_scheduled
            await set_status_intro_day_scheduled(candidate_id, force=True)
        except Exception:
            logger.exception("Failed to update candidate status to INTRO_DAY_SCHEDULED for candidate %s", candidate_id)

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
        self._last_delivery_error = None
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
        self._last_delivery_error = error
        if error == "telegram_unauthorized":
            self._fatal_error_code = error
            self._fatal_error_at = datetime.now(timezone.utc)
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

    @staticmethod
    def _fatal_error_code_for_retry(error: str) -> Optional[str]:
        normalized = (error or "").strip().lower()
        if "unauthorized" in normalized:
            return "telegram_unauthorized"
        return None

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
        self._last_delivery_error = error
        fatal_error_code = self._fatal_error_code_for_retry(error)
        if fatal_error_code is not None:
            await self._mark_failed(
                item,
                attempt,
                log_type,
                notification_type,
                fatal_error_code,
                rendered,
                candidate_tg_id=candidate_tg_id,
            )
            return

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
        requeued = await self._enqueue_outbox(
            item.id,
            attempt=max(attempt, item.attempts),
            delay=delay,
        )
        if not requeued:
            await self._mark_failed(
                item,
                attempt,
                log_type,
                notification_type,
                BROKER_UNAVAILABLE_REASON,
                rendered,
                candidate_tg_id=candidate_tg_id,
            )
            if count_failure:
                await record_notification_failed(notification_type)
            return
        if count_failure:
            await record_notification_failed(notification_type)
        await record_send_retry()

    def _compute_retry_delay(self, attempt: int) -> float:
        base = self._retry_base * (2 ** max(0, attempt - 1))
        return float(min(self._retry_max, base))

    def _apply_jitter(self, delay: float) -> float:
        return max(1.0, delay * random.uniform(0.85, 1.15))

    def _compute_poll_backoff(self, previous: float, *, reason: str) -> float:
        min_delay = max(1.0, self._base_poll_interval)
        max_delay = max(min_delay, 5.0)
        base = max(previous, min_delay)
        if reason == "transient":
            return min_delay
        next_delay = base * 1.5
        return min(max(next_delay, min_delay), max_delay)

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
            wait_time = 0.0
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
            if wait_time > 0:
                await record_rate_limit_wait(wait_time)
                logger.info(
                    "notification.worker.rate_limit_wait",
                    extra={
                        "wait_seconds": round(wait_time, 4),
                        "rate_per_sec": round(self._rate, 4),
                        "capacity": round(self._capacity, 2),
                    },
                )
            await asyncio.sleep(max(wait_time, 0.05))

    @property
    def rate(self) -> float:
        return self._rate

    @property
    def capacity(self) -> float:
        return self._capacity


def configure_notification_service(service: NotificationService) -> None:
    global _notification_service
    _notification_service = service
    service.start()


def get_notification_service() -> NotificationService:
    if _notification_service is None:
        raise NotificationNotConfigured("Notification service is not configured")
    return _notification_service


def reset_notification_service() -> None:
    """Forget the cached notification service (used between app restarts)."""
    global _notification_service
    _notification_service = None


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
    message = await _render_tpl(city_id, template_key or "t1_schedule_reject", **context)
    if not message:
        message = (
            "Спасибо за ответы! На данном этапе мы не продолжаем процесс."
        )

    await get_bot().send_message(user_id, message)
    await record_test1_rejection(result.reason or "unknown")
    try:
        candidate = await candidate_services.get_user_by_telegram_id(user_id)
        await analytics.log_funnel_event(
            analytics.FunnelEvent.TEST1_COMPLETED,
            user_id=user_id,
            candidate_id=candidate.id if candidate else None,
            metadata={"result": "failed", "reason": result.reason or "unknown"},
        )
    except Exception:
        logger.exception("Failed to log TEST1_COMPLETED (failed) for user %s", user_id)
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
        text = await _render_tpl(city_id, result.template_key, **template_context)
        if text:
            return text

    return result.message


async def _notify_existing_reservation(callback: CallbackQuery, slot: Slot) -> None:
    user_id = callback.from_user.id
    state_manager = get_state_manager()
    state = await state_manager.get(user_id) or {}
    tz = state.get("candidate_tz") or slot.candidate_tz or DEFAULT_TZ
    labels = slot_local_labels(slot.start_utc, tz)
    message = await _render_tpl(
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


if not hasattr(builtins, "configure_bot_services"):
    builtins.configure_bot_services = configure


def get_bot() -> Bot:
    if _bot is None:
        raise RuntimeError("Bot is not configured")
    return _bot


def get_state_manager() -> StateManager:
    if _state_manager is None:
        raise RuntimeError("State manager is not configured")
    return _state_manager


async def clear_candidate_chat_state(user_id: int) -> None:
    """Clear transient chat state once interview is scheduled to avoid stale prompts."""
    state_manager = get_state_manager()

    def _clear_state(st: State) -> Tuple[State, None]:
        if not isinstance(st, dict):
            return st, None
        st["manual_availability_expected"] = False
        st["manual_contact_prompt_sent"] = False
        st["slot_assignment_state"] = None
        st["slot_assignment_action_token"] = None
        st["slot_assignment_id"] = None
        st["awaiting_intro_decline_reason"] = False
        st["flow"] = "scheduled"
        return st, None

    await state_manager.atomic_update(user_id, _clear_state)

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


_DAY_NAMES_RU = (
    "понедельник",
    "вторник",
    "среда",
    "четверг",
    "пятница",
    "суббота",
    "воскресенье",
)


def slot_local_labels(dt_utc: datetime, tz: str) -> Dict[str, str]:
    local_dt = dt_utc.astimezone(_safe_zone(tz))
    slot_datetime = local_dt.strftime("%d.%m %H:%M")
    return {
        "slot_date_local": local_dt.strftime("%d.%m"),
        "slot_time_local": local_dt.strftime("%H:%M"),
        "slot_datetime_local": slot_datetime,
        "slot_day_name_local": _DAY_NAMES_RU[local_dt.weekday()],
        "dt_local": slot_datetime,
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

    notice = await _render_tpl(
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
        "candidate_name": snapshot.candidate_fio or state.get("fio", "") or str(snapshot.candidate_id),
        "candidate_fio": snapshot.candidate_fio or state.get("fio", ""),
        "city_name": state.get("city_name") or "",
        "recruiter_name": snapshot.recruiter_name or "",
    }
    
    provider = get_template_provider()
    rendered = await provider.render(
        "candidate_rejection",
        context,
        city_id=snapshot.candidate_city_id,
        channel="tg",
        locale="ru",
    )
    if not rendered or not rendered.text.strip():
        logger.warning("Rejection template produced empty message for candidate %s", snapshot.candidate_id)
        return False
        
    text = rendered.text.strip()

    bot = get_bot()
    if not hasattr(bot, "send_message"):
        logger.warning("Bot instance missing send_message; cannot send rejection message")
        return False

    try:
        await bot.send_message(snapshot.candidate_id, text)
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
    candidate_name = escape_html(state.get("fio") or str(user_id))
    city_name = escape_html(state.get("city_name") or "—")
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


async def notify_recruiters_waiting_slot(user_id: int, candidate_name: str, city_name: str, city_id: Optional[int]) -> bool:
    """Notify recruiters when a candidate is waiting for a manual slot assignment.

    Args:
        user_id: Telegram ID of the candidate
        candidate_name: Full name of the candidate
        city_name: Name of the city
        city_id: ID of the city (for finding responsible recruiters)

    Returns:
        True if at least one recruiter was notified
    """
    try:
        recruiters = await get_active_recruiters_for_city(city_id) if city_id else []
    except Exception:
        logger.exception("Failed to get active recruiters for city %s", city_id)
        recruiters = []

    if not recruiters:
        logger.warning("No active recruiters found for city %s (candidate %s waiting)", city_id, user_id)
        return False

    # Deduplicate recruiters by chat_id
    recipients: List[Any] = []
    seen_chats: set[Any] = set()
    for rec in recruiters:
        chat_id = getattr(rec, "tg_chat_id", None)
        if not chat_id or chat_id in seen_chats:
            continue
        recipients.append(rec)
        seen_chats.add(chat_id)

    if not recipients:
        logger.warning("No recruiters with chat_id found for city %s", city_id)
        return False

    bot = get_bot()
    message = (
        "⏳ <b>Кандидат ждёт назначения слота</b>\n\n"
        f"👤 {escape_html(candidate_name)}\n"
        f"📍 {escape_html(city_name)}\n"
        f"TG: <code>{user_id}</code>\n\n"
        "⚠️ <b>Нет доступных автоматических слотов</b>\n"
        "Требуется ручное назначение времени собеседования через админ-панель."
    )

    delivered = False
    for recruiter in recipients:
        try:
            await bot.send_message(recruiter.tg_chat_id, message, parse_mode="HTML")
            delivered = True
            logger.info(
                "Sent waiting_slot notification to recruiter %s (chat_id=%s) for candidate %s",
                recruiter.id,
                recruiter.tg_chat_id,
                user_id,
            )
        except Exception:
            logger.exception(
                "Failed to send waiting_slot notification to recruiter %s", recruiter.id
            )

    return delivered


async def begin_interview(user_id: int, username: Optional[str] = None) -> None:
    # Ensure we use the freshest question set after admin edits.
    refresh_questions_bank()

    state_manager = get_state_manager()
    bot = get_bot()

    # If this chat belongs to a recruiter, switch to recruiter-facing mode
    try:
        recruiter = await get_recruiter_by_chat_id(user_id)
    except Exception:
        recruiter = None

    if recruiter is not None:
        await state_manager.set(
            user_id,
            State(
                flow="recruiter",
                t1_idx=None,
                test1_answers={},
                t1_last_prompt_id=None,
                t1_last_question_text="",
                t1_requires_free_text=False,
                t1_sequence=list(TEST1_QUESTIONS),
                fio=recruiter.name or "",
                city_name="",
                city_id=None,
                candidate_tz=recruiter.tz or DEFAULT_TZ,
                t2_attempts={},
                picked_recruiter_id=None,
                picked_slot_id=None,
                test1_payload={},
                username=username or "",
                t1_last_hint_sent=False,
            ),
        )
        await show_recruiter_dashboard(user_id, recruiter=recruiter)
        return

    try:
        await candidate_services.set_conversation_mode(user_id, "flow")
    except Exception:  # pragma: no cover - best effort
        logger.debug("Failed to reset conversation mode for %s", user_id, exc_info=True)
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
            t1_last_hint_sent=False,
        ),
    )
    try:
        candidate = await candidate_services.get_user_by_telegram_id(user_id)
        await analytics.log_funnel_event(
            analytics.FunnelEvent.TEST1_STARTED,
            user_id=user_id,
            candidate_id=candidate.id if candidate else None,
            metadata={"channel": "telegram"},
        )
    except Exception:
        logger.exception("Failed to log TEST1_STARTED for user %s", user_id)
    intro = await _render_tpl(None, "t1_intro")
    if not (intro or "").strip():
        from backend.apps.bot.defaults import DEFAULT_TEMPLATES
        intro = DEFAULT_TEMPLATES.get("t1_intro", "").strip() or "Начнём анкету."
    await bot.send_message(user_id, intro)
    await send_test1_question(user_id)


async def show_recruiter_dashboard(user_id: int, recruiter: Optional[Recruiter] = None, horizon_hours: int = 48) -> None:
    """Send recruiter a compact dashboard of upcoming slots."""
    bot = get_bot()
    if recruiter is None:
        recruiter = await get_recruiter_by_chat_id(user_id)
    if recruiter is None:
        await bot.send_message(
            user_id,
            "Ваш чат не привязан к рекрутёру. Используйте /iam <Имя из админки>, затем /start.",
        )
        return

    now = datetime.now(timezone.utc)
    end = now + timedelta(hours=horizon_hours)
    try:
        slots = await get_recruiter_agenda_by_chat_id(
            user_id, start_utc=now, end_utc=end, limit=30
        )
    except Exception:
        logger.exception("Failed to load recruiter agenda", extra={"chat_id": user_id})
        await bot.send_message(user_id, "Не удалось загрузить расписание. Попробуйте позже.")
        return

    if not slots:
        await bot.send_message(
            user_id,
            f"Ближайшие {horizon_hours} часов у вас нет встреч.\n"
            "Уведомления о бронированиях и подтверждениях будут приходить сюда. "
            "Подробные действия — в админке.",
        )
        return

    lines: List[str] = []
    for slot in slots:
        status = (slot.status or "").lower()
        purpose = "Ознакомительный день" if (slot.purpose or "").lower() == "intro_day" else "Собеседование"
        candidate = slot.candidate_fio or ("Свободно" if status == SlotStatus.FREE else "—")
        tz = slot.tz_name or recruiter.tz or DEFAULT_TZ
        dt_local = fmt_dt_local(slot.start_utc, tz)
        lines.append(f"• {dt_local} ({tz}) · {purpose} · {candidate} · {status}")

    header = f"Ваши ближайшие встречи (до {horizon_hours}ч):"
    await bot.send_message(user_id, "\n".join([header, *lines]))


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


def _ensure_question_id(question: Dict[str, Any], idx: int) -> str:
    """
    Guarantee that a question dict has an 'id' field.
    If absent, derive a stable fallback based on position.
    """

    qid = question.get("id")
    if not qid:
        qid = question.get("question_id") or f"q{idx + 1}"
        question["id"] = qid
    return str(qid)


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
        _ensure_question_id(question, idx)
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

    progress = await _render_tpl(city_id, "t1_progress", n=idx + 1, total=total)
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
        state["t1_last_hint_sent"] = False
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
    current_idx = int(state.get("t1_current_idx", state.get("t1_idx", 0)) or 0)
    qid = _ensure_question_id(question, current_idx)
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

    def _apply(state: State) -> Tuple[State, Dict[str, Any]]:
        working = state
        answers = working.setdefault("test1_answers", {})
        sequence = list(working.get("t1_sequence") or TEST1_QUESTIONS)
        working["t1_sequence"] = sequence
        _ensure_question_id(question, current_idx)

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

    try:
        if await candidate_services.is_chat_mode_active(user_id):
            logger.info(
                "Chat mode active; skipping questionnaire response",
                extra={"user_id": user_id},
            )
            return
    except Exception:  # pragma: no cover - conversation mode failures shouldn't break flow
        logger.debug("Failed to check conversation mode for %s", user_id, exc_info=True)

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
    _ensure_question_id(question, idx)
    if not state.get("t1_requires_free_text", True):
        # Разрешаем текстовый ответ даже если ранее ожидались кнопки
        def _allow_text(st: State) -> Tuple[State, None]:
            st["t1_requires_free_text"] = True
            return st, None
        await state_manager.atomic_update(user_id, _allow_text)

    answer_text = (message.text or message.caption or "").strip()
    if not answer_text:
        if not state.get("t1_last_hint_sent"):
            await message.reply(
                "Нажмите «Ответить» на сообщение с вопросом или напишите текст, чтобы зафиксировать ответ."
            )

            def _mark_hint_sent(st: State) -> Tuple[State, None]:
                st["t1_last_hint_sent"] = True
                return st, None

            await state_manager.atomic_update(user_id, _mark_hint_sent)
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
        f"Дата: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}",
        f"TG ID: {user_id}",
        f"ФИО: {state.get('fio') or '—'}",
        f"Город: {state.get('city_name') or '—'}",
        "",
        "Ответы:",
    ]
    for idx, q in enumerate(sequence):
        qid = _ensure_question_id(q, idx)
        lines.append(f"- {q.get('prompt')}\n  {answers.get(qid, '—')}")

    report_content = "\n".join(lines)
    fname = TEST1_DIR / f"test1_{(state.get('fio') or user_id)}.txt"
    try:
        with open(fname, "w", encoding="utf-8") as f:
            f.write(report_content)
    except Exception:
        logger.warning(
            "test1.report_write_failed",
            extra={"user_id": user_id, "filename": str(fname)},
            exc_info=True,
        )

    if not state.get("t1_notified"):
        shared = await _share_test1_with_recruiters(user_id, state, fname)

        if shared:
            def _mark_shared(st: State) -> Tuple[State, None]:
                st["t1_notified"] = True
                return st, None

            await state_manager.atomic_update(user_id, _mark_shared)

    done_text = await _render_tpl(state.get("city_id"), "t1_done")
    if done_text:
        await bot.send_message(user_id, done_text)

    try:
        await show_recruiter_menu(user_id)
    except Exception:
        logger.exception("Failed to present recruiter menu after Test 1 completion")

    candidate = None
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
            source="bot",
        )

        # Update candidate status to TEST1_COMPLETED (and mark waiting if no slots)
        try:
            from backend.domain.candidates.status_service import (
                set_status_test1_completed,
                set_status_waiting_slot,
            )

            await set_status_test1_completed(candidate.telegram_id)

            # В любом случае после теста фиксируем статус ожидания слота,
            # чтобы кандидат попал во «Входящие». Дополнительно, если слотов нет —
            # шлём уведомление рекрутёрам.
            status_updated = await set_status_waiting_slot(candidate.telegram_id)

            if candidate.city:
                city_record = await find_city_by_plain_name(candidate.city)
                if city_record and not await city_has_available_slots(city_record.id):
                    if status_updated:
                        try:
                            candidate_name = state.get("fio") or f"User {candidate.telegram_id}"
                            city_name = state.get("city_name") or candidate.city
                            await notify_recruiters_waiting_slot(
                                user_id=candidate.telegram_id,
                                candidate_name=candidate_name,
                                city_name=city_name,
                                city_id=city_record.id,
                            )
                        except Exception:
                            logger.exception(
                                "Failed to notify recruiters about waiting_slot for candidate %s",
                                candidate.telegram_id
                            )
                        try:
                            await send_manual_scheduling_prompt(candidate.telegram_id)
                        except Exception:
                            logger.exception(
                                "Failed to prompt candidate %s for manual schedule window",
                                candidate.telegram_id,
                            )
        except Exception:
            logger.exception("Failed to update candidate Test1/slot status for user %s", candidate.telegram_id)

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
    try:
        candidate_for_event = candidate
        if candidate_for_event is None:
            candidate_for_event = await candidate_services.get_user_by_telegram_id(user_id)
        await analytics.log_funnel_event(
            analytics.FunnelEvent.TEST1_COMPLETED,
            user_id=user_id,
            candidate_id=candidate_for_event.id if candidate_for_event else None,
            metadata={"result": "passed"},
        )
    except Exception:
        logger.exception("Failed to log TEST1_COMPLETED for user %s", user_id)

    def _reset(st: State) -> Tuple[State, None]:
        st["t1_idx"] = None
        st["t1_last_prompt_id"] = None
        st["t1_last_question_text"] = ""
        st["t1_requires_free_text"] = False
        return st, None

    await state_manager.atomic_update(user_id, _reset)


async def start_test2(user_id: int) -> None:
    # Refresh questions so admin changes are reflected without restart.
    refresh_questions_bank()

    bot = get_bot()
    state_manager = get_state_manager()

    def _init_attempts(state: State) -> Tuple[State, Dict[str, Optional[int]]]:
        state["t2_attempts"] = {
            q_index: {"answers": [], "is_correct": False, "start_time": None}
            for q_index in range(len(TEST2_QUESTIONS))
        }
        return state, {"city_id": state.get("city_id")}

    ctx = await state_manager.atomic_update(user_id, _init_attempts)
    try:
        candidate = await candidate_services.get_user_by_telegram_id(user_id)
        await analytics.log_funnel_event(
            analytics.FunnelEvent.TEST2_STARTED,
            user_id=user_id,
            candidate_id=candidate.id if candidate else None,
            metadata={"channel": "telegram"},
        )
    except Exception:
        logger.exception("Failed to log TEST2_STARTED for user %s", user_id)
    intro = await _render_tpl(
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
        attempt["start_time"] = datetime.now(timezone.utc)
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

    now = datetime.now(timezone.utc)
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
        f"Дата: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}",
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
                source="bot",
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

    result_text = await _render_tpl(
        state.get("city_id"),
        "t2_result",
        correct=correct_answers,
        score=score,
        rating=rating,
    )
    await bot.send_message(user_id, result_text)
    pct = correct_answers / max(1, len(TEST2_QUESTIONS))
    try:
        result_flag = "failed" if pct < PASS_THRESHOLD else "passed"
        await analytics.log_funnel_event(
            analytics.FunnelEvent.TEST2_COMPLETED,
            user_id=user_id,
            candidate_id=candidate.id if candidate else None,
            metadata={
                "result": result_flag,
                "score": score,
                "correct": correct_answers,
                "total": len(TEST2_QUESTIONS),
            },
        )
    except Exception:
        logger.exception("Failed to log TEST2_COMPLETED for user %s", user_id)
    if pct < PASS_THRESHOLD:
        provider = get_template_provider()
        candidate_name = (candidate.fio if candidate else "") or str(user_id)
        ctx = {"candidate_name": candidate_name, "candidate_fio": candidate_name}
        rendered = await provider.render(
            "candidate_rejection", 
            ctx, 
            city_id=state.get("city_id")
        )
        if rendered:
            await bot.send_message(user_id, rendered.text)

        # Update candidate status to TEST2_FAILED
        try:
            from backend.domain.candidates.status_service import set_status_test2_failed
            await set_status_test2_failed(user_id)
        except Exception:
            logger.exception("Failed to update candidate status to TEST2_FAILED for user %s", user_id)

        await state_manager.delete(user_id)
        return

    final_notice = await _render_tpl(state.get("city_id"), "slot_sent")
    if not final_notice:
        final_notice = "Заявка отправлена. Ожидайте подтверждения."
    await bot.send_message(user_id, final_notice)

    # Update candidate status to TEST2_COMPLETED
    try:
        from backend.domain.candidates.status_service import set_status_test2_completed
        await set_status_test2_completed(user_id, force=True)
    except Exception:
        logger.exception("Failed to update candidate status to TEST2_COMPLETED for user %s", user_id)


async def show_recruiter_menu(user_id: int, *, notice: Optional[str] = None) -> None:
    bot = get_bot()
    state_manager = get_state_manager()
    state = await state_manager.get(user_id) or {}
    tz_label = state.get("candidate_tz", DEFAULT_TZ)
    kb = await kb_recruiters(tz_label, city_id=state.get("city_id"))
    text = await _render_tpl(state.get("city_id"), "choose_recruiter")
    if notice:
        text = f"{notice}\n\n{text}"
    await bot.send_message(user_id, text, reply_markup=kb)


async def handle_home_start(callback: CallbackQuery) -> None:
    await callback.answer()
    await begin_interview(callback.from_user.id)


_AVAILABILITY_RANGE_RE = re.compile(
    r"(?P<from_h>\d{1,2})(?:[:.](?P<from_m>\d{2}))?\s*[-–—]\s*(?P<to_h>\d{1,2})(?:[:.](?P<to_m>\d{2}))?"
)
_AVAILABILITY_DATE_RE = re.compile(
    r"(?P<day>\d{1,2})[./](?P<month>\d{1,2})(?:[./](?P<year>\d{2,4}))?"
)
_KEYWORD_DATE_OFFSETS = {
    "послезавтра": 2,
    "завтра": 1,
    "сегодня": 0,
}


def _clamp(value: int, *, low: int, high: int) -> int:
    return max(low, min(value, high))


def _parse_manual_availability_window(
    text: str,
    tz_label: Optional[str],
) -> Tuple[Optional[datetime], Optional[datetime]]:
    """Attempt to parse candidate-provided availability window."""

    cleaned = (text or "").strip()
    if not cleaned:
        return None, None

    range_match = _AVAILABILITY_RANGE_RE.search(cleaned)
    if not range_match:
        return None, None

    try:
        start_hour = _clamp(int(range_match.group("from_h")), low=0, high=23)
    except (TypeError, ValueError):
        start_hour = 0
    try:
        start_min = _clamp(int(range_match.group("from_m") or 0), low=0, high=59)
    except (TypeError, ValueError):
        start_min = 0
    try:
        end_hour = _clamp(int(range_match.group("to_h")), low=0, high=23)
    except (TypeError, ValueError):
        end_hour = 0
    try:
        end_min = _clamp(int(range_match.group("to_m") or 0), low=0, high=59)
    except (TypeError, ValueError):
        end_min = 0

    tzinfo = _safe_zone(tz_label or DEFAULT_TZ)
    now_local = datetime.now(tzinfo)
    target_date = None

    date_match = _AVAILABILITY_DATE_RE.search(cleaned)
    if date_match:
        try:
            day = int(date_match.group("day"))
            month = int(date_match.group("month"))
            year_raw = date_match.group("year")
            if year_raw:
                year = int(year_raw)
                if year < 100:
                    year += 2000
            else:
                year = now_local.year
            candidate_date = date(year, month, day)
            if not year_raw and candidate_date < now_local.date():
                candidate_date = date(year + 1, month, day)
            target_date = candidate_date
        except ValueError:
            target_date = None

    if target_date is None:
        lowered = cleaned.lower()
        for keyword, offset in _KEYWORD_DATE_OFFSETS.items():
            if keyword in lowered:
                target_date = (now_local + timedelta(days=offset)).date()
                break

    if target_date is None:
        target_date = now_local.date()
        candidate_start = datetime.combine(target_date, time(start_hour, start_min), tzinfo=tzinfo)
        if candidate_start <= now_local - timedelta(minutes=30):
            target_date = target_date + timedelta(days=1)

    start_dt = datetime.combine(target_date, datetime_time(start_hour, start_min), tzinfo=tzinfo)
    end_date = target_date
    end_dt = datetime.combine(end_date, datetime_time(end_hour, end_min), tzinfo=tzinfo)
    if end_dt <= start_dt:
        end_dt = datetime.combine(
            target_date + timedelta(days=1),
            datetime_time(end_hour, end_min),
            tzinfo=tzinfo,
        )

    return start_dt, end_dt


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

    message = await _render_tpl(city_id, "manual_schedule_prompt")
    if not message:
        message = (
            "Свободных слотов в вашем городе сейчас нет.\n"
            "Напишите, пожалуйста, когда вам удобно, и мы постараемся выделить время.\n"
            "Чтобы ускорить назначение, укажите диапазон времени: например, 25.07 12:00-16:00 "
            "или завтра 10:00-13:00."
        )

    await bot.send_message(
        user_id,
        message,
        reply_markup=ForceReply(selective=True, input_field_placeholder="25.07 12:00-16:00"),
    )

    def _mark_prompt_sent(st: State) -> Tuple[State, None]:
        st["manual_contact_prompt_sent"] = True
        st["manual_availability_expected"] = True
        return st, None

    await state_manager.atomic_update(user_id, _mark_prompt_sent)

    return True


def _format_manual_window_label(
    start_dt: Optional[datetime],
    end_dt: Optional[datetime],
    tz_label: Optional[str],
) -> Optional[str]:
    if not start_dt or not end_dt:
        return None
    tzinfo = _safe_zone(tz_label or DEFAULT_TZ)
    start_local = start_dt.astimezone(tzinfo)
    end_local = end_dt.astimezone(tzinfo)
    if start_local.date() == end_local.date():
        date_part = start_local.strftime("%d.%m")
        return f"{date_part} {start_local.strftime('%H:%M')}–{end_local.strftime('%H:%M')}"
    return f"{start_local.strftime('%d.%m %H:%M')} – {end_local.strftime('%d.%m %H:%M')}"


async def record_manual_availability_response(user_id: int, text: str) -> bool:
    """Persist candidate-provided availability window from manual prompt."""
    payload = (text or "").strip()
    if not payload:
        return False

    state_manager = get_state_manager()
    try:
        state = await state_manager.get(user_id)
    except Exception:
        state = None
    if not isinstance(state, dict):
        state = {}

    tz_label = state.get("candidate_tz") or DEFAULT_TZ
    start_local, end_local = _parse_manual_availability_window(payload, tz_label)
    start_utc = start_local.astimezone(timezone.utc) if start_local else None
    end_utc = end_local.astimezone(timezone.utc) if end_local else None

    db_user = await candidate_services.save_manual_slot_response(
        telegram_id=user_id,
        window_start=start_utc,
        window_end=end_utc,
        note=payload[:1000],
        timezone_label=tz_label,
    )

    if db_user and db_user.candidate_status not in {
        CandidateStatus.WAITING_SLOT,
        CandidateStatus.STALLED_WAITING_SLOT,
    }:
        try:
            await set_status_waiting_slot(user_id)
        except Exception:
            logger.exception("Failed to mark candidate %s as waiting_slot", user_id)

    window_label = _format_manual_window_label(start_local, end_local, tz_label)
    safe_window = html.escape(window_label) if window_label else None
    safe_payload = html.escape(payload)
    if safe_window:
        ack = (
            f"✅ Спасибо! Зафиксировали диапазон <b>{safe_window}</b>.\n"
            "Рекрутёр свяжется, как только появится свободное окно."
        )
    else:
        ack = (
            "✅ Спасибо! Мы передали ваши пожелания рекрутёрам.\n"
            f"<code>{safe_payload}</code>"
        )

    bot = get_bot()
    await bot.send_message(user_id, ack)

    def _clear_prompt(st: State) -> Tuple[State, None]:
        st["manual_availability_expected"] = False
        st["manual_contact_prompt_sent"] = True
        st["manual_availability_last_note"] = payload
        return st, None

    await state_manager.atomic_update(user_id, _clear_prompt)
    return True


async def handle_pick_recruiter(callback: CallbackQuery) -> None:
    user_id = callback.from_user.id
    payload = verify_callback_data(callback.data, expected_prefix="pick_rec:")
    if not payload:
        await callback.answer("Невалидная ссылка. Откройте меню заново.", show_alert=True)
        logger.warning(
            "Invalid pick_rec callback signature",
            extra={"user_id": user_id, "callback_data": callback.data},
        )
        return
    rid_s = payload.split(":", 1)[1]

    state_manager = get_state_manager()
    state = await state_manager.get(user_id)

    if rid_s == "__again__":
        tz_label = (state or {}).get("candidate_tz", DEFAULT_TZ)
        kb = await kb_recruiters(tz_label, city_id=(state or {}).get("city_id"))
        text = await _render_tpl(state.get("city_id") if state else None, "choose_recruiter")
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
        text = f"{text}\n\n{await _render_tpl(state.get('city_id'), 'no_slots')}"
    try:
        await callback.message.edit_text(text, reply_markup=kb)
    except TelegramBadRequest:
        await callback.message.edit_text(text)
        await callback.message.edit_reply_markup(reply_markup=kb)
    await callback.answer()


async def handle_refresh_slots(callback: CallbackQuery) -> None:
    user_id = callback.from_user.id
    payload = verify_callback_data(callback.data, expected_prefix="refresh_slots:")
    if not payload:
        await callback.answer("Ссылка устарела, откройте список слотов заново.", show_alert=True)
        logger.warning(
            "Invalid refresh_slots callback signature",
            extra={"user_id": user_id, "callback_data": callback.data},
        )
        return
    _, rid_s = payload.split(":", 1)
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
        text = f"{text}\n\n{await _render_tpl(state.get('city_id'), 'no_slots')}"
    try:
        await callback.message.edit_text(text, reply_markup=kb)
    except TelegramBadRequest:
        await callback.message.edit_text(text)
        await callback.message.edit_reply_markup(reply_markup=kb)
    await callback.answer("Обновлено")


async def handle_pick_slot(callback: CallbackQuery) -> None:
    user_id = callback.from_user.id
    payload = verify_callback_data(callback.data, expected_prefix="pick_slot:")
    if not payload:
        await callback.answer("Ссылка устарела. Выберите слот из меню.", show_alert=True)
        logger.warning(
            "Invalid pick_slot callback signature",
            extra={"user_id": user_id, "callback_data": callback.data},
        )
        return
    _, rid_s, slot_id_s = payload.split(":", 2)

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
    candidate = await candidate_services.get_user_by_telegram_id(user_id)
    reservation = await reserve_slot(
        slot_id,
        candidate_tg_id=user_id,
        candidate_fio=state.get("fio", str(user_id)),
        candidate_tz=state.get("candidate_tz", DEFAULT_TZ),
        candidate_id=candidate.candidate_id if candidate else None,
        candidate_city_id=state.get("city_id"),
        candidate_username=state.get("username"),  # Pass username to reserve_slot
        purpose="intro_day" if is_intro else "interview",
        expected_recruiter_id=recruiter_id,
        expected_city_id=city_id,
        allow_candidate_replace=True,
    )

    if reservation.status == "slot_taken":
        text = await _render_tpl(state.get("city_id"), "slot_taken")
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
    caption = _format_recruiter_slot_caption(
        candidate_label=slot.candidate_fio or str(user_id),
        city_label=state.get("city_name", "—"),
        dt_label=fmt_dt_local(slot.start_utc, (rec.tz if rec else DEFAULT_TZ) or DEFAULT_TZ),
        purpose=purpose,
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
                logger.warning(
                    "bot.send_document_failed",
                    extra={"recruiter_id": rec.id if rec else None, "slot_id": slot.id},
                    exc_info=True,
                )
            break

    if rec and rec.tg_chat_id and not attached:
        try:
            await bot.send_message(
                rec.tg_chat_id, caption, reply_markup=kb_approve(slot.id)
            )
        except Exception:
            logger.warning(
                "bot.send_message_to_recruiter_failed",
                extra={"recruiter_id": rec.id if rec else None, "slot_id": slot.id},
                exc_info=True,
            )
    elif not rec or not rec.tg_chat_id:
        await bot.send_message(
            user_id,
            "ℹ️ Рекрутёр ещё не активировал DM с ботом (/iam_mih) или не указан tg_chat_id.\n"
            "Заявка создана, но уведомление не отправлено.",
        )

    await callback.message.edit_text(
        await _render_tpl(state.get("city_id"), "slot_sent")
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
    candidate_name_raw = slot.candidate_fio or ""
    city_name_raw = state.get("city_name") or ""
    candidate_name = _sanitize_text(candidate_name_raw)
    city_name = _sanitize_text(city_name_raw)
    intro_address_safe, _ = _intro_detail(
        getattr(slot, "intro_address", None),
        fallback=city_name_raw,
        default=INTRO_ADDRESS_FALLBACK,
    )
    intro_contact_safe, _ = _intro_detail(
        getattr(slot, "intro_contact", None),
        fallback=None,
        default=INTRO_CONTACT_FALLBACK,
    )
    is_intro_day = (getattr(slot, "purpose", "") or "").strip().lower() == "intro_day"
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
        "intro_address": intro_address_safe,
        "intro_contact": intro_contact_safe,
    }
    if getattr(slot, "purpose", "interview") == "intro_day":
        context.update(
            {
                "address": intro_address_safe,
                "city_address": intro_address_safe,
                "recruiter_contact": intro_contact_safe,
            }
        )
    if is_intro_day:
        template_key = "intro_day_invitation"
    else:
        template_key = "interview_confirmed_candidate"
    provider = get_template_provider()
    rendered = await provider.render(
        template_key,
        context,
        locale="ru",
        channel="tg",
        city_id=getattr(slot, "candidate_city_id", None),
    )
    if rendered is not None:
        return rendered.text, tz, city_name, rendered.key, rendered.version

    logger.error(
        "Notification template not found",
        extra={"key": template_key, "slot_id": slot.id, "city_id": getattr(slot, "candidate_city_id", None)},
    )
    return "", tz, city_name, template_key, None


async def approve_slot_and_notify(slot_id: int, *, force_notify: bool = False) -> SlotApprovalResult:
    slot = await get_slot(slot_id)
    if not slot:
        return SlotApprovalResult(
            status="not_found",
            message="Заявка уже обработана или слот не найден.",
        )

    status_value = (slot.status or "").lower()
    already_booked = status_value in {SlotStatus.BOOKED, SlotStatus.CONFIRMED_BY_CANDIDATE}
    if already_booked and not force_notify:
        return SlotApprovalResult(
            status="already",
            message="Слот уже согласован.",
            slot=slot,
        )
    if already_booked and slot.candidate_tg_id is not None:
        try:
            await set_status_interview_scheduled(slot.candidate_tg_id)
        except Exception:
            logger.exception(
                "Failed to sync candidate status for booked slot",
                extra={"slot_id": slot.id, "candidate_tg_id": slot.candidate_tg_id},
            )
    if status_value == SlotStatus.FREE:
        return SlotApprovalResult(
            status="slot_free",
            message="Слот уже освобождён.",
            slot=slot,
        )
    if slot.candidate_tg_id is None:
        return SlotApprovalResult(
            status="missing_candidate",
            message="Слот не привязан к кандидату.",
            slot=slot,
        )

    if not already_booked:
        slot = await approve_slot(slot_id)
        if not slot:
            return SlotApprovalResult(
                status="error",
                message="Не удалось согласовать слот.",
            )

    if slot.candidate_tg_id is not None:
        try:
            await clear_candidate_chat_state(slot.candidate_tg_id)
        except Exception:
            logger.exception(
                "Failed to clear candidate chat state after approval",
                extra={"slot_id": slot.id, "candidate_tg_id": slot.candidate_tg_id},
            )

    candidate_label = (
        slot.candidate_fio
        or (str(slot.candidate_tg_id) if slot.candidate_tg_id is not None else "—")
    )
    message_text, candidate_tz, candidate_city, template_key, template_version = await _render_candidate_notification(
        slot
    )

    try:
        reminder_service = get_reminder_service()
    except RuntimeError:
        reminder_service = None

    already_sent = await notification_log_exists(
        "candidate_interview_confirmed",
        slot.id,
        candidate_tg_id=slot.candidate_tg_id,
    )
    if not already_sent:
        already_sent = await notification_log_exists(
            "interview_confirmed_candidate",
            slot.id,
            candidate_tg_id=slot.candidate_tg_id,
        )

    should_notify = force_notify or (not already_sent)

    if should_notify:
        notify_status: Optional[str] = None
        notify_note: Optional[str] = None
        try:
            notification_service = get_notification_service()
        except RuntimeError:
            notification_service = None

        if notification_service is not None:
            try:
                snapshot = await capture_slot_snapshot(slot)
                notify_result = await notification_service.on_booking_status_changed(
                    slot.id,
                    BookingNotificationStatus.APPROVED,
                    snapshot=snapshot,
                )
            except Exception:
                logger.exception("Failed to enqueue approval notification")
                notify_result = None
            if notify_result and notify_result.status in {"queued", "sent"}:
                notify_status = "sent"
                notify_note = "queued" if notify_result.status == "queued" else "sent"
            else:
                notify_status = "failed"
        else:
            bot = None
            try:
                bot = get_bot()
            except RuntimeError:
                logger.warning("Bot is not configured; cannot send approval notification.")

            if bot is None:
                failure_parts = [
                    "⚠️ Слот подтверждён, но бот недоступен и отправить сообщение кандидату невозможно.",
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
                        "Свяжитесь с кандидатом вручную и передайте детали встречи.",
                    ]
                )
                return SlotApprovalResult(
                    status="notify_failed",
                    message="Слот подтверждён, но бот недоступен. Свяжитесь с кандидатом вручную.",
                    slot=slot,
                    summary_html="\n".join(failure_parts),
                )

            try:
                await _send_with_retry(
                    bot,
                    SendMessage(chat_id=slot.candidate_tg_id, text=message_text),
                    correlation_id=f"approve:{slot.id}:{uuid.uuid4().hex}",
                )
                notify_status = "sent"
            except Exception:
                logger.exception("Failed to send approval message to candidate")
                notify_status = "failed"

            if notify_status == "sent":
                logged = await add_notification_log(
                    "candidate_interview_confirmed",
                    slot.id,
                    candidate_tg_id=slot.candidate_tg_id,
                    payload=message_text,
                    template_key=template_key,
                    template_version=template_version,
                    overwrite=force_notify,
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

        if notify_status != "sent":
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
            return SlotApprovalResult(
                status="notify_failed",
                message="Слот подтверждён, но отправить сообщение кандидату не удалось. Свяжитесь вручную.",
                slot=slot,
                summary_html="\n".join(failure_parts),
            )

        summary_head = (
            "✅ Слот подтверждён. Сообщение поставлено в очередь на отправку."
            if notify_note == "queued"
            else "✅ Слот подтверждён. Сообщение отправлено кандидату автоматически."
        )
        summary_parts = [
            summary_head,
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
    else:
        summary_parts = [
            "ℹ️ Слот уже был подтверждён ранее — повторная отправка сообщения не выполнялась.",
            f"👤 {html.escape(candidate_label)}",
            f"🕒 {fmt_dt_local(slot.start_utc, candidate_tz)} ({candidate_tz})",
        ]
        if candidate_city:
            summary_parts.append(f"📍 {html.escape(candidate_city)}")

    return SlotApprovalResult(
        status="approved" if should_notify else "already",
        message="Интервью согласовано, кандидат уведомлён." if should_notify else "Слот уже был согласован ранее.",
        slot=slot,
        summary_html="\n".join(summary_parts),
    )


async def handle_approve_slot(callback: CallbackQuery) -> None:
    slot_id = int(callback.data.split(":", 1)[1])
    result = await approve_slot_and_notify(slot_id)

    if result.status == "not_found":
        await callback.answer("Заявка уже обработана.", show_alert=True)
        await safe_remove_reply_markup(callback.message)
        return

    if result.status == "slot_free":
        await callback.answer("Слот уже освобождён.", show_alert=True)
        await safe_remove_reply_markup(callback.message)
        return

    if result.status == "missing_candidate":
        await callback.answer("Кандидат не найден.", show_alert=True)
        await safe_remove_reply_markup(callback.message)
        return

    if result.status == "error":
        await callback.answer("Не удалось согласовать.", show_alert=True)
        return

    if result.status == "notify_failed":
        await safe_edit_text_or_caption(
            callback.message,
            result.summary_html or result.message,
        )
        await safe_remove_reply_markup(callback.message)
        await callback.answer("Не удалось отправить сообщение кандидату.", show_alert=True)
        return

    if result.status == "approved":
        await safe_edit_text_or_caption(
            callback.message,
            result.summary_html or result.message,
        )
        await safe_remove_reply_markup(callback.message)
        await callback.answer("Сообщение отправлено кандидату.")
        return

    await callback.answer("Уже согласовано ✔️")
    await safe_remove_reply_markup(callback.message)
    return


if not hasattr(builtins, "handle_approve_slot"):
    builtins.handle_approve_slot = handle_approve_slot


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
    link_text = await _render_tpl(
        city_id,
        "att_confirmed_link",
        link=link,
        dt=dt_local,
        **labels,
    )
    bot = get_bot()

    if result.status == "confirmed":
        try:
            if getattr(slot, "purpose", "interview") != "intro_day":
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

        # Update candidate status for intro day confirmations
        if slot.candidate_tg_id and getattr(slot, "purpose", "interview") == "intro_day":
            try:
                from backend.domain.candidates.status_service import (
                    get_candidate_status,
                    set_status_intro_day_confirmed_preliminary,
                    set_status_intro_day_confirmed_day_of,
                )
                from backend.domain.candidates.status import CandidateStatus

                # Check current status to determine which confirmation this is
                current_status = await get_candidate_status(slot.candidate_tg_id)

                if current_status == CandidateStatus.INTRO_DAY_CONFIRMED_PRELIMINARY:
                    # This is the day-of confirmation (responding to 3H reminder)
                    await set_status_intro_day_confirmed_day_of(slot.candidate_tg_id, force=True)
                else:
                    # This is the initial confirmation
                    await set_status_intro_day_confirmed_preliminary(slot.candidate_tg_id, force=True)
            except Exception:
                logger.exception("Failed to update intro day confirmation status for candidate %s", slot.candidate_tg_id)

        ack_text = await _render_tpl(
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
            candidate_label = escape_html(slot.candidate_fio or str(slot.candidate_tg_id or ""))
            await bot.send_message(
                rec.tg_chat_id,
                f"❌ Кандидат {candidate_label} отказался от слота "
                f"{fmt_dt_local(slot.start_utc, rec.tz or DEFAULT_TZ)}. Слот освобождён.",
            )
        except Exception:
            logger.warning(
                "bot.slot_rejection_notify_failed",
                extra={"recruiter_id": rec.id, "slot_id": slot.id},
                exc_info=True,
            )

    st = await get_state_manager().get(callback.from_user.id) or {}
    prompt = await _render_tpl(
        getattr(slot, "candidate_city_id", None),
        "att_declined_reason_prompt",
    )
    if not prompt:
        prompt = (
            "Понимаю. Напишите, пожалуйста, коротко причину отказа, "
            "чтобы мы могли предложить другой день."
        )
    reason_state = {
        "slot_id": slot.id,
        "city_id": getattr(slot, "candidate_city_id", None),
        "recruiter_id": slot.recruiter_id,
        "start_local": fmt_dt_local(slot.start_utc, slot.candidate_tz or DEFAULT_TZ),
        "candidate_fio": slot.candidate_fio or "",
    }
    try:
        state_manager = get_state_manager()
        await state_manager.update(callback.from_user.id, {"awaiting_intro_decline_reason": reason_state})
    except Exception:
        logger.exception("Failed to set intro decline reason state", extra={"candidate": callback.from_user.id})
    await bot.send_message(
        callback.from_user.id,
        prompt,
        reply_markup=ForceReply(selective=True),
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


async def capture_intro_decline_reason(message, state) -> bool:
    """Handle free-text reason when candidate declines intro day."""
    reason_payload = state.get("awaiting_intro_decline_reason") or {}
    slot_id = reason_payload.get("slot_id")
    if not slot_id:
        return False

    text = (message.text or message.caption or "").strip()
    if not text:
        await message.answer("Напишите, пожалуйста, коротко причину отказа.")
        return True

    # Persist reason on the candidate profile for analytics
    try:
        from backend.core.db import async_session
        from backend.domain.candidates.models import User
        async with async_session() as session:
            user = await session.scalar(select(User).where(User.telegram_id == message.from_user.id))
            if user:
                user.intro_decline_reason = text
                await session.commit()
    except Exception:
        logger.exception("Failed to save intro decline reason", extra={"candidate": message.from_user.id})

    slot = await get_slot(slot_id)
    bot = get_bot()
    recruiter_note_sent = False
    try:
        if slot and slot.recruiter_id:
            recruiter = await get_recruiter(slot.recruiter_id)
        else:
            recruiter = None
        if recruiter and recruiter.tg_chat_id:
            dt_label = reason_payload.get("start_local") or (
                fmt_dt_local(slot.start_utc, recruiter.tz or DEFAULT_TZ) if slot else ""
            )
            candidate_label = reason_payload.get("candidate_fio") or getattr(slot, "candidate_fio", "") or str(message.from_user.id)
            reason_text = (
                "❌ Кандидат отказался от ознакомительного дня.\n"
                f"👤 {escape_html(candidate_label)}\n"
                f"🗓 {dt_label}\n"
                f"Причина: {escape_html(text)}"
            )
            try:
                await bot.send_message(recruiter.tg_chat_id, reason_text)
                recruiter_note_sent = True
            except Exception:
                logger.exception("Failed to send intro decline reason to recruiter", extra={"slot_id": slot_id})
    except Exception:
        logger.exception("Failed to resolve recruiter for intro decline reason", extra={"slot_id": slot_id})

    ack = "Спасибо, передали информацию рекрутеру."
    if not recruiter_note_sent:
        ack = "Спасибо, получили ответ."
    await message.answer(ack)

    try:
        state_manager = get_state_manager()
        def _clear(st: State) -> Tuple[State, None]:
            st = dict(st or {})
            st.pop("awaiting_intro_decline_reason", None)
            return st, None
        await state_manager.atomic_update(message.from_user.id, _clear)
    except Exception:
        logger.exception("Failed to clear intro decline reason state", extra={"candidate": message.from_user.id})

    return True


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


def configure_template_provider() -> None:
    """Configure template provider (DB-backed by default)."""
    global _template_provider
    provider_kind = os.environ.get("BOT_TEMPLATE_PROVIDER", "").strip().lower()
    if provider_kind in {"jinja", "file", "filesystem"}:
        from .template_provider import Jinja2TemplateProvider
        _template_provider = Jinja2TemplateProvider()
        logger.info("Bot template provider: jinja (filesystem)")
    else:
        from .template_provider import TemplateProvider
        _template_provider = TemplateProvider()
        logger.info("Bot template provider: database")


__all__ = [
    "StateManager",
    "BookingNotificationStatus",
    "NotificationService",
    "NotificationNotConfigured",
    "configure_notification_service",
    "get_notification_service",
    "reset_notification_service",
    "calculate_score",
    "configure",
    "configure_template_provider",
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
    "clear_candidate_chat_state",
    "now_utc",
    "save_test1_answer",
    "send_test1_question",
    "send_test2_question",
    "send_manual_scheduling_prompt",
    "record_manual_availability_response",
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
    "approve_slot_and_notify",
    "templates",
    "SlotApprovalResult",
    "capture_slot_snapshot",
    "cancel_slot_reminders",
    "notify_reschedule",
    "notify_rejection",
    "capture_intro_decline_reason",
    "SlotSnapshot",
    "set_pending_test2",
    "dispatch_interview_success",
    "register_interview_success_handler",
    "launch_test2",
    "_extract_option_label",
    "_extract_option_value",
    "_mark_test1_question_answered",
    "_shorten_answer",
    "run_scheduled_poll",
]


async def run_scheduled_poll() -> None:
    """Standalone job wrapper to avoid pickling issues with self._scheduler."""
    try:
        svc = get_notification_service()
    except NotificationNotConfigured:
        return
    if svc:
        await svc._scheduled_poll()
