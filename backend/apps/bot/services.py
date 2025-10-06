"""Supporting services and helpers for the Telegram bot."""

from __future__ import annotations

import asyncio
import html
import logging
import math
from datetime import datetime, timezone
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Tuple, Literal
from zoneinfo import ZoneInfo

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, ForceReply, Message, FSInputFile

from pydantic import ValidationError

from backend.core.settings import get_settings
from backend.domain.candidates import services as candidate_services
from backend.domain.models import SlotStatus, Slot
from backend.domain.repositories import (
    ReservationResult,
    approve_slot,
    get_active_recruiters_for_city,
    get_free_slots_by_recruiter,
    get_recruiter,
    get_slot,
    mark_slot_attendance_confirmed,
    reject_slot,
    reserve_slot,
    set_recruiter_chat_id_by_command,
)

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
from .metrics import record_test1_completion, record_test1_rejection
from .state_store import StateManager
from .test1_validation import Test1Payload, apply_partial_validation, convert_age
from .reminders import get_reminder_service


logger = logging.getLogger(__name__)

_settings = get_settings()
REPORTS_DIR: Path = _settings.data_dir / "reports"
TEST1_DIR: Path = _settings.data_dir / "test1"
UPLOADS_DIR: Path = _settings.data_dir / "uploads"

for _path in (REPORTS_DIR, TEST1_DIR, UPLOADS_DIR):
    _path.mkdir(parents=True, exist_ok=True)



_bot: Optional[Bot] = None
_state_manager: Optional[StateManager] = None


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


def configure(bot: Optional[Bot], state_manager: StateManager) -> None:
    global _bot, _state_manager
    _bot = bot
    _state_manager = state_manager


def get_bot() -> Bot:
    if _bot is None:
        raise RuntimeError("Bot is not configured")
    return _bot


def get_state_manager() -> StateManager:
    if _state_manager is None:
        raise RuntimeError("State manager is not configured")
    return _state_manager


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
        "📋 <b>Новая анкета (Тест 1)</b>\n"
        f"👤 {candidate_name}\n"
        f"📍 {city_name}\n"
        f"TG: {user_id}"
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


async def begin_interview(user_id: int) -> None:
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
                "label": city.name,
                "value": city.name,
                "city_id": city.id,
                "tz": city.tz,
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

    fname = TEST1_DIR / f"test1_{(state.get('fio') or user_id)}.txt"
    try:
        with open(fname, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
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
        candidate = await candidate_services.create_or_update_user(
            telegram_id=user_id,
            fio=fio,
            city=city_name,
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


async def send_manual_scheduling_prompt(user_id: int) -> None:
    """Prompt the candidate to reach out when no automatic slots are available."""

    bot = get_bot()
    state_manager = get_state_manager()
    try:
        state = await state_manager.get(user_id)
    except Exception:
        state = None

    city_id: Optional[int] = None
    if isinstance(state, dict):
        city_id = state.get("city_id")

    message = await templates.tpl(city_id, "manual_schedule_prompt")
    if not message:
        message = (
            "Свободных слотов сейчас нет. Напишите, пожалуйста, когда вам удобно, "
            "и мы подберём время вручную."
        )

    await bot.send_message(user_id, message)


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

    is_intro = state.get("flow") == "intro"
    city_id = state.get("city_id")
    reservation = await reserve_slot(
        slot_id,
        candidate_tg_id=user_id,
        candidate_fio=state.get("fio", str(user_id)),
        candidate_tz=state.get("candidate_tz", DEFAULT_TZ),
        candidate_city_id=state.get("city_id"),
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


async def _render_candidate_notification(slot: Slot) -> Tuple[str, str, str]:
    tz = slot.candidate_tz or DEFAULT_TZ
    labels = slot_local_labels(slot.start_utc, tz)
    template_key = (
        "stage3_intro_invite"
        if getattr(slot, "purpose", "interview") == "intro_day"
        else "approved_msg"
    )
    state = await _resolve_candidate_state_for_slot(slot)
    text = await templates.tpl(
        getattr(slot, "candidate_city_id", None),
        template_key,
        candidate_fio=slot.candidate_fio or "",
        city_name=state.get("city_name") or "",
        dt=fmt_dt_local(slot.start_utc, tz),
        **labels,
    )
    return text, tz, state.get("city_name") or ""


async def handle_approve_slot(callback: CallbackQuery) -> None:
    slot_id = int(callback.data.split(":", 1)[1])
    slot = await get_slot(slot_id)
    if not slot:
        await callback.answer("Заявка уже обработана.", show_alert=True)
        await safe_remove_reply_markup(callback.message)
        return

    status_value = (slot.status or "").lower()

    if status_value == SlotStatus.BOOKED:
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

    message_text, candidate_tz, candidate_city = await _render_candidate_notification(slot)
    bot = get_bot()
    try:
        await bot.send_message(slot.candidate_tg_id, message_text)
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
    if status_value != SlotStatus.BOOKED:
        await callback.answer("Слот ещё не подтверждён.", show_alert=True)
        await safe_remove_reply_markup(callback.message)
        return

    message_text, candidate_tz, candidate_city = await _render_candidate_notification(slot)
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
    slot = await get_slot(slot_id)
    status_value = (slot.status or "").lower() if slot else None
    if not slot or status_value != SlotStatus.BOOKED:
        await callback.answer("Заявка не найдена или ещё не подтверждена рекрутёром.", show_alert=True)
        return

    if slot.attendance_confirmed_at is not None:
        await callback.answer("Уже подтверждено ✔️")
        await safe_remove_reply_markup(callback.message)
        return

    rec = await get_recruiter(slot.recruiter_id)
    link = (
        rec.telemost_url if rec and rec.telemost_url else "https://telemost.yandex.ru/j/REPLACE_ME"
    )
    tz = slot.candidate_tz or DEFAULT_TZ
    text = await templates.tpl(
        getattr(slot, "candidate_city_id", None),
        "att_confirmed_link",
        link=link,
        dt=fmt_dt_local(slot.start_utc, tz),
    )
    bot = get_bot()
    await bot.send_message(slot.candidate_tg_id, text)

    updated_slot = await mark_slot_attendance_confirmed(slot_id)
    if updated_slot is not None:
        slot = updated_slot

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
        getattr(slot, "candidate_city_id", None),
        "att_confirmed_ack",
    )
    if ack_text:
        try:
            await callback.message.edit_text(ack_text)
        except TelegramBadRequest:
            pass
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except TelegramBadRequest:
        pass

    if rec and rec.tg_chat_id:
        recruiter_notice = await templates.tpl(
            getattr(slot, "candidate_city_id", None),
            "att_confirmed_recruiter",
            candidate=(
                slot.candidate_fio
                or (str(slot.candidate_tg_id) if slot.candidate_tg_id is not None else "")
            ).strip(),
            dt=fmt_dt_local(slot.start_utc, rec.tz or DEFAULT_TZ),
        )
        if recruiter_notice:
            try:
                await bot.send_message(rec.tg_chat_id, recruiter_notice)
            except Exception:
                logger.exception("Failed to notify recruiter about attendance confirmation")

    await callback.answer("Подтверждено")


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
    "_extract_option_label",
    "_extract_option_value",
    "_mark_test1_question_answered",
    "_shorten_answer",
]
