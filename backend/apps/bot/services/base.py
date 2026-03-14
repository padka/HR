"""Shared helpers and infrastructure for Telegram bot services."""

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
from contextlib import contextmanager
from contextvars import ContextVar
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
    claim_outbox_item_by_id,
    get_active_recruiters_for_city,
    get_city,
    get_notification_log,
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


from ..config import (
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
    get_questions_bank_version,
    refresh_questions_bank,
)
from ..keyboards import (
    create_keyboard,
    kb_approve,
    kb_attendance_confirm,
    kb_recruiters,
    kb_slots_for_recruiter,
    kb_slot_assignment_offer,
    kb_start,
)
from ..city_registry import (
    CityInfo,
    find_candidate_city_by_id,
    find_candidate_city_by_name,
    list_candidate_cities,
)
from ..metrics import (
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
from ..security import verify_callback_data
from ..state_store import StateManager
from ..test1_validation import Test1Payload, apply_partial_validation, convert_age
from ..reminders import ReminderKind, get_reminder_service
from ..template_provider import TemplateProvider, RenderedTemplate


logger = logging.getLogger(__name__)

_AVAILABILITY_RANGE_RE = re.compile(
    r"(?P<from_h>\d{1,2})(?::(?P<from_m>\d{2}))?\s*[-–—]\s*"
    r"(?P<to_h>\d{1,2})(?::(?P<to_m>\d{2}))?"
)
_AVAILABILITY_DATE_RE = re.compile(
    r"(?P<day>\d{1,2})\.(?P<month>\d{1,2})(?:\.(?P<year>\d{2,4}))?"
)

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
    try:
        _path.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        # Don't fail app import on misconfigured DATA_DIR (common in docker/CI).
        # The actual write attempt will still fail later with a clearer context.
        logger.error("data_dir.permission_denied", extra={"path": str(_path)})

_bot: Optional[Bot] = None
_state_manager: Optional[StateManager] = None
_notification_service: Optional["NotificationService"] = None
_template_provider: Optional[TemplateProvider] = None
_interview_success_handlers: List[
    Callable[[InterviewSuccessEvent], Awaitable[None]]
] = []
_suppress_outbound_chat_logging: ContextVar[bool] = ContextVar(
    "suppress_outbound_chat_logging",
    default=False,
)


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

    # Keep meeting-link aliases in sync so templates can use any common key.
    link_value = None
    for key in ("join_link", "link", "meeting_link", "meeting_url", "interview_link", "slot_link"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            link_value = value.strip()
            break
    if link_value is None:
        link_value = ""
    for key in ("join_link", "link", "meeting_link", "meeting_url", "interview_link", "slot_link"):
        if key not in data or data.get(key) in (None, ""):
            data[key] = link_value

    # Keep interview datetime aliases in sync.
    if "interview_datetime_local" not in data and "slot_datetime_local" in data:
        data["interview_datetime_local"] = data["slot_datetime_local"]
    if "interview_date_local" not in data and "slot_date_local" in data:
        data["interview_date_local"] = data["slot_date_local"]
    if "interview_time_local" not in data and "slot_time_local" in data:
        data["interview_time_local"] = data["slot_time_local"]
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


BROKER_UNAVAILABLE_REASON = "broker_unavailable"
DIRECT_NO_BROKER_REASON = "direct:no-broker"


@dataclass
class SlotApprovalResult:
    status: str
    message: str
    slot: Optional[Slot] = None
    summary_html: Optional[str] = None


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


INTRO_ADDRESS_FALLBACK = "Адрес уточняется — рекрутёр подтвердит детали перед встречей"
INTRO_CONTACT_FALLBACK = "Руководитель свяжется с вами для подтверждения деталей"
def configure(
    bot: Optional[Bot],
    state_manager: StateManager,
    dispatcher: Optional["Dispatcher"] = None,
) -> None:
    global _bot, _state_manager
    _bot = bot
    _state_manager = state_manager
    if isinstance(_bot, Bot):
        _install_outbound_chat_logging(_bot)
    if dispatcher is not None:
        logger.debug(
            "Dispatcher argument provided to configure(); interview events use internal handlers registry.",
            extra={"dispatcher": type(dispatcher).__name__},
        )


@contextmanager
def suppress_outbound_chat_logging():
    token = _suppress_outbound_chat_logging.set(True)
    try:
        yield
    finally:
        _suppress_outbound_chat_logging.reset(token)


def _install_outbound_chat_logging(bot: Bot) -> None:
    if getattr(bot, "_recruitsmart_chat_logging_installed", False):
        return

    original_send_message = bot.send_message

    async def _send_message_with_chat_log(chat_id: Any, text: Optional[str], *args: Any, **kwargs: Any):
        sent_message = await original_send_message(chat_id, text, *args, **kwargs)
        if _suppress_outbound_chat_logging.get():
            return sent_message

        try:
            candidate_tg_id = int(chat_id)
        except (TypeError, ValueError):
            return sent_message

        try:
            clean_text = _strip_markup(text)
            if clean_text:
                await candidate_services.log_outbound_chat_message(
                    candidate_tg_id,
                    text=clean_text,
                    telegram_message_id=getattr(sent_message, "message_id", None),
                    payload={"source": "bot"},
                    author_label="bot",
                )
        except Exception:
            logger.exception(
                "Failed to record outbound bot message in candidate chat",
                extra={"candidate_tg_id": candidate_tg_id},
            )

        return sent_message

    setattr(bot, "_recruitsmart_chat_logging_installed", True)
    bot.send_message = _send_message_with_chat_log  # type: ignore[assignment]


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
    starter = globals().get("start_test2")
    if starter is None:
        from . import test2_flow as _test2_flow

        starter = getattr(_test2_flow, "start_test2", None)
    if starter is None:
        raise RuntimeError("start_test2 is not configured")
    await starter(candidate_id)


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


def _slot_timezone(slot: Slot, recruiter_tz: Optional[str] = None) -> str:
    return (
        getattr(slot, "candidate_tz", None)
        or getattr(slot, "tz_name", None)
        or recruiter_tz
        or DEFAULT_TZ
    )


def _is_slot_confirmation_on_local_day(
    slot: Slot,
    *,
    now: Optional[datetime] = None,
    recruiter_tz: Optional[str] = None,
) -> bool:
    reference_utc = now or now_utc()
    tz = _slot_timezone(slot, recruiter_tz)
    zone = _safe_zone(tz)
    return slot.start_utc.astimezone(zone).date() == reference_utc.astimezone(zone).date()


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
    state = await _resolve_candidate_state_for_slot(slot)
    candidate_tz = await _resolve_candidate_timezone_for_slot(
        slot, state=state, recruiter=recruiter
    )
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
async def show_recruiter_menu(user_id: int, *, notice: Optional[str] = None) -> bool:
    bot = get_bot()
    state_manager = get_state_manager()
    state = await state_manager.get(user_id) or {}
    tz_label = state.get("candidate_tz", DEFAULT_TZ)
    kb = await kb_recruiters(tz_label, city_id=state.get("city_id"))
    if kb.inline_keyboard:
        text = await _render_tpl(state.get("city_id"), "choose_recruiter")
        if notice:
            text = f"{notice}\n\n{text}"
        await bot.send_message(user_id, text, reply_markup=kb)
        return True

    # No recruiter with available slots in the selected city: switch to manual flow.
    from .slot_flow import send_manual_scheduling_prompt

    sent = await send_manual_scheduling_prompt(user_id, notice=notice)
    return sent
def _safe_data_path(relative_path: str) -> Optional[Path]:
    """Resolve a data-dir relative path to an absolute Path (guarding traversal)."""

    if not relative_path:
        return None
    settings = get_settings()
    base_dir = Path(settings.data_dir).resolve()
    candidate = (base_dir / relative_path).resolve()
    if not str(candidate).startswith(str(base_dir)):
        return None
    return candidate


def _candidate_report_paths(db_user: Any) -> List[Path]:
    """Return existing report file paths for the candidate (best effort)."""

    paths: List[Path] = []
    for rel in (
        getattr(db_user, "test1_report_url", None),
        getattr(db_user, "test2_report_url", None),
    ):
        if not rel:
            continue
        abs_path = _safe_data_path(str(rel))
        if abs_path and abs_path.exists() and abs_path not in paths:
            paths.append(abs_path)

    try:
        db_id = int(getattr(db_user, "id", 0) or 0)
    except Exception:
        db_id = 0
    if db_id:
        fallback = REPORTS_DIR / str(db_id) / "test1.txt"
        if fallback.exists() and fallback not in paths:
            paths.insert(0, fallback)
    return paths
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


def _resolve_recruiter_meeting_link(recruiter: Optional[Recruiter]) -> str:
    if recruiter is None:
        return ""
    value = getattr(recruiter, "telemost_url", None)
    if isinstance(value, str):
        return value.strip()
    return ""


def _extract_tz(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None


async def _resolve_candidate_timezone_for_slot(
    slot: Slot,
    *,
    state: Optional[Dict[str, Any]] = None,
    recruiter: Optional[Recruiter] = None,
) -> str:
    tz_value = _extract_tz(getattr(slot, "candidate_tz", None))
    if tz_value:
        return tz_value

    if state:
        tz_value = _extract_tz(state.get("candidate_tz"))
        if tz_value:
            return tz_value

    city_id = getattr(slot, "candidate_city_id", None) or getattr(slot, "city_id", None)
    if city_id is not None:
        try:
            city = await get_city(int(city_id))
        except Exception:
            city = None
        if city is not None:
            tz_value = _extract_tz(getattr(city, "tz", None))
            if tz_value:
                return tz_value

    recruiter_obj = recruiter
    if recruiter_obj is None and getattr(slot, "recruiter_id", None):
        try:
            recruiter_obj = await get_recruiter(int(slot.recruiter_id))
        except Exception:
            recruiter_obj = None
    if recruiter_obj is not None:
        tz_value = _extract_tz(getattr(recruiter_obj, "tz", None))
        if tz_value:
            return tz_value

    return DEFAULT_TZ


async def _render_candidate_notification(slot: Slot) -> Tuple[str, str, str, str, Optional[int]]:
    state = await _resolve_candidate_state_for_slot(slot)
    recruiter = await get_recruiter(slot.recruiter_id) if slot.recruiter_id else None
    tz = await _resolve_candidate_timezone_for_slot(slot, state=state, recruiter=recruiter)
    labels = slot_local_labels(slot.start_utc, tz)
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
    context = _normalize_format_context({
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
        "recruiter_name": recruiter.name if recruiter else "",
        "join_link": _resolve_recruiter_meeting_link(recruiter),
        "intro_address": intro_address_safe,
        "intro_contact": intro_contact_safe,
    })
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
def configure_template_provider() -> None:
    """Configure template provider (DB-backed by default)."""
    global _template_provider
    provider_kind = os.environ.get("BOT_TEMPLATE_PROVIDER", "").strip().lower()
    if provider_kind in {"jinja", "file", "filesystem"}:
        from ..template_provider import Jinja2TemplateProvider
        _template_provider = Jinja2TemplateProvider()
        logger.info("Bot template provider: jinja (filesystem)")
    else:
        from ..template_provider import TemplateProvider
        _template_provider = TemplateProvider()
        logger.info("Bot template provider: database")
