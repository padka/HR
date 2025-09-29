"""Supporting services and helpers for the Telegram bot."""

from __future__ import annotations

import asyncio
import html
import logging
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple, TypeVar, cast, overload
from zoneinfo import ZoneInfo

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, ForceReply, Message, FSInputFile

from backend.core.settings import get_settings
from backend.domain.models import SlotStatus
from backend.domain.repositories import (
    approve_slot,
    get_active_recruiters_for_city,
    get_candidate_cities,
    get_city_by_name,
    get_free_slots_by_recruiter,
    get_recruiter,
    get_slot,
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
    MAX_ATTEMPTS,
    PASS_THRESHOLD,
    RemKey,
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


_settings = get_settings()
REPORTS_DIR: Path = _settings.data_dir / "reports"
TEST1_DIR: Path = _settings.data_dir / "test1"
UPLOADS_DIR: Path = _settings.data_dir / "uploads"

for _path in (REPORTS_DIR, TEST1_DIR, UPLOADS_DIR):
    _path.mkdir(parents=True, exist_ok=True)


T = TypeVar("T")


class StateManager:
    """Simple in-memory state storage for bot flows."""

    def __init__(self) -> None:
        self._storage: Dict[int, State] = {}

    @overload
    def get(self, user_id: int) -> Optional[State]:
        ...

    @overload
    def get(self, user_id: int, default: T) -> State | T:
        ...

    def get(self, user_id: int, default: T | None = None) -> State | T | None:
        return self._storage.get(user_id, default)

    def ensure(self, user_id: int) -> State:
        state = self._storage.get(user_id)
        if state is None:
            state = cast(State, {})
            self._storage[user_id] = state
        return state

    def set(self, user_id: int, state: State) -> None:
        self._storage[user_id] = state

    def pop(self, user_id: int) -> Optional[State]:
        return self._storage.pop(user_id, None)

    def clear(self) -> None:
        self._storage.clear()


_bot: Optional[Bot] = None
_state_manager: Optional[StateManager] = None
REMINDERS: Dict[RemKey, asyncio.Task] = {}
CONFIRM_TASKS: Dict[RemKey, asyncio.Task] = {}


def configure(bot: Bot, state_manager: StateManager) -> None:
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


async def schedule_reminder(slot_id: int, candidate_id: int) -> None:
    bot = get_bot()
    key: RemKey = (slot_id, candidate_id)
    t2 = REMINDERS.pop(key, None)
    if t2 and not t2.done():
        t2.cancel()

    slot = await get_slot(slot_id)
    if not slot:
        return

    start_utc = slot.start_utc
    delay = (start_utc - now_utc()).total_seconds() - 3600  # -1h
    if delay <= 0:
        return

    async def _rem() -> None:
        try:
            await asyncio.sleep(delay)
            fresh = await get_slot(slot_id)
            if not fresh or fresh.candidate_tg_id != candidate_id:
                return
            tz = fresh.candidate_tz or DEFAULT_TZ
            labels = slot_local_labels(fresh.start_utc, tz)
            text = await templates.tpl(
                getattr(fresh, "candidate_city_id", None),
                "reminder_1h",
                candidate_fio=getattr(fresh, "candidate_fio", "") or "",
                dt=fmt_dt_local(fresh.start_utc, tz),
                **labels,
            )
            await bot.send_message(candidate_id, text)
        except asyncio.CancelledError:
            pass
        except Exception as exc:  # pragma: no cover - logging path
            logging.exception("Reminder error: %s", exc)

    REMINDERS[key] = asyncio.create_task(_rem())


async def schedule_confirm_prompt(slot_id: int, candidate_id: int) -> None:
    bot = get_bot()
    key: RemKey = (slot_id, candidate_id)
    t = CONFIRM_TASKS.pop(key, None)
    if t and not t.done():
        t.cancel()

    slot = await get_slot(slot_id)
    if not slot:
        return

    start_utc = slot.start_utc
    delay = (start_utc - now_utc()).total_seconds() - 7200  # -2h

    async def _ask_now() -> None:
        try:
            fresh = await get_slot(slot_id)
            if not fresh or fresh.candidate_tg_id != candidate_id:
                return
            tz = fresh.candidate_tz or DEFAULT_TZ
            labels = slot_local_labels(fresh.start_utc, tz)
            key_name = (
                "stage4_intro_reminder"
                if getattr(fresh, "purpose", "interview") == "intro_day"
                else "stage2_interview_reminder"
            )
            state = get_state_manager().get(candidate_id) or {}
            text = await templates.tpl(
                getattr(fresh, "candidate_city_id", None),
                key_name,
                candidate_fio=getattr(fresh, "candidate_fio", "") or "",
                city_name=state.get("city_name") or "",
                dt=fmt_dt_local(fresh.start_utc, tz),
                **labels,
            )
            await bot.send_message(
                candidate_id, text, reply_markup=kb_attendance_confirm(slot_id)
            )
        except asyncio.CancelledError:
            pass
        except Exception as exc:  # pragma: no cover - logging path
            logging.exception("Confirm prompt error: %s", exc)

    if delay <= 0:
        await _ask_now()
        return

    async def _rem() -> None:
        try:
            await asyncio.sleep(delay)
            await _ask_now()
        except asyncio.CancelledError:
            pass
        except Exception as exc:  # pragma: no cover - logging path
            logging.exception("Confirm scheduler error: %s", exc)

    CONFIRM_TASKS[key] = asyncio.create_task(_rem())


async def begin_interview(user_id: int) -> None:
    state_manager = get_state_manager()
    bot = get_bot()
    state_manager.set(
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
    prev = state_manager.get(user_id) or {}
    state_manager.set(
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
    state = state_manager.ensure(user_id)
    sequence = state.get("t1_sequence") or list(TEST1_QUESTIONS)
    idx = state.get("t1_idx", 0)
    total = len(sequence)
    if idx >= total:
        await finalize_test1(user_id)
        return
    q = dict(sequence[idx])
    sequence[idx] = q
    state["t1_sequence"] = sequence
    progress = await templates.tpl(state.get("city_id"), "t1_progress", n=idx + 1, total=total)
    progress_bar = create_progress_bar(idx, total)
    helper = q.get("helper")
    base_text = f"{progress}\n{progress_bar}\n\n{_format_prompt(q['prompt'])}"
    if helper:
        base_text += f"\n\n<i>{helper}</i>"

    resolved_options = await _resolve_test1_options(q)
    if resolved_options is not None:
        q["options"] = resolved_options

    options = q.get("options") or []
    if options:
        markup = _build_test1_options_markup(idx, options)
        sent = await bot.send_message(user_id, base_text, reply_markup=markup)
        state["t1_requires_free_text"] = False
    else:
        placeholder = q.get("placeholder", "Введите ответ…")[:64]
        sent = await bot.send_message(
            user_id,
            base_text,
            reply_markup=ForceReply(selective=True, input_field_placeholder=placeholder),
        )
        state["t1_requires_free_text"] = True

    state["t1_last_prompt_id"] = sent.message_id
    state["t1_last_question_text"] = base_text
    state["t1_current_idx"] = idx


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
        cities = await get_candidate_cities()
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
    state = get_state_manager().get(user_id)
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
    state["t1_last_prompt_id"] = None
    state["t1_last_question_text"] = ""
    state["t1_requires_free_text"] = False


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
) -> None:
    state_manager = get_state_manager()
    state = state_manager.ensure(user_id)
    state.setdefault("test1_answers", {})
    sequence = state.setdefault("t1_sequence", list(TEST1_QUESTIONS))

    if question["id"] == "fio":
        state["fio"] = answer
    elif question["id"] == "city":
        meta = metadata or {}
        resolved_name = str(
            meta.get("name")
            or meta.get("label")
            or meta.get("value")
            or answer
        )
        state["city_name"] = resolved_name

        meta_city_id = meta.get("city_id")
        meta_tz = meta.get("tz")
        candidate_tz: Optional[str] = None
        resolved_city = None

        if meta_city_id is not None:
            try:
                state["city_id"] = int(meta_city_id)
            except (TypeError, ValueError):
                state["city_id"] = None
                resolved_city = await get_city_by_name(answer)
            candidate_tz = str(meta_tz or DEFAULT_TZ)
        else:
            resolved_city = await get_city_by_name(answer)

        if resolved_city:
            state["city_id"] = resolved_city.id
            candidate_tz = resolved_city.tz
            resolved_name = resolved_city.name
        elif meta_city_id is None:
            state["city_id"] = None
            candidate_tz = candidate_tz or DEFAULT_TZ

        state["candidate_tz"] = candidate_tz or DEFAULT_TZ
        state["test1_answers"][question["id"]] = resolved_name
    elif question["id"] == "status":
        lower = answer.lower()
        insert_pos = state.get("t1_idx", 0) + 1
        existing_ids = {q.get("id") for q in sequence}

        if "работ" in lower:
            if FOLLOWUP_NOTICE_PERIOD["id"] not in existing_ids:
                sequence.insert(insert_pos, FOLLOWUP_NOTICE_PERIOD.copy())
                existing_ids.add(FOLLOWUP_NOTICE_PERIOD["id"])
                insert_pos += 1
        elif "уч" in lower:
            if FOLLOWUP_STUDY_MODE["id"] not in existing_ids:
                sequence.insert(insert_pos, FOLLOWUP_STUDY_MODE.copy())
                existing_ids.add(FOLLOWUP_STUDY_MODE["id"])
                insert_pos += 1
            if FOLLOWUP_STUDY_SCHEDULE["id"] not in existing_ids:
                sequence.insert(insert_pos, FOLLOWUP_STUDY_SCHEDULE.copy())
                existing_ids.add(FOLLOWUP_STUDY_SCHEDULE["id"])

    if question["id"] != "city":
        state["test1_answers"][question["id"]] = answer


async def handle_test1_answer(message: Message) -> None:
    user_id = message.from_user.id
    state = get_state_manager().get(user_id)
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

    await save_test1_answer(user_id, question, answer_text)
    await _mark_test1_question_answered(user_id, _shorten_answer(answer_text))

    state["t1_idx"] = idx + 1
    if state["t1_idx"] >= total:
        await finalize_test1(user_id)
    else:
        await send_test1_question(user_id)


async def handle_test1_option(callback: CallbackQuery) -> None:
    user_id = callback.from_user.id
    state = get_state_manager().get(user_id)
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

    await save_test1_answer(user_id, question, value, metadata=metadata)
    await _mark_test1_question_answered(user_id, label)

    state["t1_idx"] = idx + 1

    await callback.answer(f"Выбрано: {label}")

    if state["t1_idx"] >= len(sequence):
        await finalize_test1(user_id)
    else:
        await send_test1_question(user_id)


async def finalize_test1(user_id: int) -> None:
    bot = get_bot()
    state_manager = get_state_manager()
    state = state_manager.ensure(user_id)
    sequence = state.get("t1_sequence", list(TEST1_QUESTIONS))
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
        lines.append(f"- {q['prompt']}\n  {state['test1_answers'].get(qid, '—')}")

    fname = TEST1_DIR / f"test1_{(state.get('fio') or user_id)}.txt"
    try:
        with open(fname, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
    except Exception:
        pass

    invite_text = await templates.tpl(
        state.get("city_id"),
        "stage1_invite",
        candidate_fio=state.get("fio") or "",
        city_name=state.get("city_name") or "",
        interview_dt_hint="выберите удобное время из списка ниже (по-вашему времени)",
    )
    await bot.send_message(user_id, invite_text)

    await show_recruiter_menu(user_id)

    state["t1_idx"] = None
    state["t1_last_prompt_id"] = None
    state["t1_last_question_text"] = ""
    state["t1_requires_free_text"] = False


async def start_test2(user_id: int) -> None:
    bot = get_bot()
    state = get_state_manager().ensure(user_id)
    state["t2_attempts"] = {
        q_index: {"answers": [], "is_correct": False, "start_time": None}
        for q_index in range(len(TEST2_QUESTIONS))
    }
    intro = await templates.tpl(
        state.get("city_id"),
        "t2_intro",
        qcount=len(TEST2_QUESTIONS),
        timelimit=TIME_LIMIT // 60,
        attempts=MAX_ATTEMPTS,
    )
    await bot.send_message(user_id, intro)
    await send_test2_question(user_id, 0)


async def send_test2_question(user_id: int, q_index: int) -> None:
    bot = get_bot()
    state = get_state_manager().ensure(user_id)
    state["t2_attempts"][q_index]["start_time"] = datetime.now()
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
    state = get_state_manager().get(user_id)
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

    attempt = state["t2_attempts"][q_index]
    question = TEST2_QUESTIONS[q_index]

    now = datetime.now()
    start_time = attempt.get("start_time")
    time_spent = (now - start_time).seconds if start_time else 0
    overtime = time_spent > TIME_LIMIT

    attempt["answers"].append(
        {"answer": answer_index, "time": now.isoformat(), "overtime": overtime}
    )
    is_correct = answer_index == question["correct"]
    attempt["is_correct"] = is_correct

    feedback = question.get("feedback")
    if isinstance(feedback, list):
        feedback_message = feedback[answer_index]
    else:
        feedback_message = feedback if is_correct else "❌ <i>Неверно.</i>"

    if is_correct:
        final_feedback = f"{feedback_message}"
        if overtime:
            final_feedback += "\n⏰ <i>Превышено время</i>"
        if len(attempt["answers"]) > 1:
            penalty = 10 * (len(attempt["answers"]) - 1)
            final_feedback += f"\n⚠️ <i>Попыток: {len(attempt['answers'])} (-{penalty}%)</i>"
        await callback.message.edit_text(final_feedback)

        if q_index < len(TEST2_QUESTIONS) - 1:
            await send_test2_question(user_id, q_index + 1)
        else:
            await finalize_test2(user_id)
    else:
        attempts_left = MAX_ATTEMPTS - len(attempt["answers"])
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
    state = state_manager.ensure(user_id)
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
        get_state_manager().pop(user_id)
        return

    await show_recruiter_menu(user_id)


async def show_recruiter_menu(user_id: int, *, notice: Optional[str] = None) -> None:
    bot = get_bot()
    state = get_state_manager().get(user_id) or {}
    tz_label = state.get("candidate_tz", DEFAULT_TZ)
    kb = await kb_recruiters(tz_label, city_id=state.get("city_id"))
    text = await templates.tpl(state.get("city_id"), "choose_recruiter")
    if notice:
        text = f"{notice}\n\n{text}"
    await bot.send_message(user_id, text, reply_markup=kb)


async def handle_home_start(callback: CallbackQuery) -> None:
    await callback.answer()
    await begin_interview(callback.from_user.id)


async def handle_pick_recruiter(callback: CallbackQuery) -> None:
    user_id = callback.from_user.id
    rid_s = callback.data.split(":", 1)[1]

    state_manager = get_state_manager()
    state = state_manager.get(user_id)

    if rid_s == "__again__":
        tz_label = (state or {}).get("candidate_tz", DEFAULT_TZ)
        kb = await kb_recruiters(tz_label, city_id=(state or {}).get("city_id"))
        text = await templates.tpl(state.get("city_id") if state else None, "choose_recruiter")
        if state is not None:
            state["picked_recruiter_id"] = None
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

    state["picked_recruiter_id"] = rid
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

    state = get_state_manager().get(user_id)
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

    state = get_state_manager().get(user_id)
    if not state:
        await callback.answer("Сессия истекла. Введите /start", show_alert=True)
        return

    is_intro = state.get("flow") == "intro"
    city_id = state.get("city_id")
    slot = await reserve_slot(
        slot_id,
        candidate_tg_id=user_id,
        candidate_fio=state.get("fio", str(user_id)),
        candidate_tz=state.get("candidate_tz", DEFAULT_TZ),
        candidate_city_id=state.get("city_id"),
        purpose="intro_day" if is_intro else "interview",
        expected_recruiter_id=recruiter_id,
        expected_city_id=city_id,
    )
    if not slot:
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


async def handle_approve_slot(callback: CallbackQuery) -> None:
    slot_id = int(callback.data.split(":", 1)[1])
    slot = await get_slot(slot_id)
    if not slot:
        await callback.answer("Заявка уже обработана.", show_alert=True)
        await safe_remove_reply_markup(callback.message)
        return

    if slot.status == SlotStatus.BOOKED:
        await callback.answer("Уже согласовано ✔️")
        await safe_remove_reply_markup(callback.message)
        return

    if slot.status == SlotStatus.FREE:
        await callback.answer("Слот уже освобождён.", show_alert=True)
        await safe_remove_reply_markup(callback.message)
        return

    slot = await approve_slot(slot_id)
    if not slot:
        await callback.answer("Не удалось согласовать.", show_alert=True)
        return

    tz = slot.candidate_tz or DEFAULT_TZ
    labels = slot_local_labels(slot.start_utc, tz)
    template_key = (
        "stage3_intro_invite"
        if getattr(slot, "purpose", "interview") == "intro_day"
        else "approved_msg"
    )
    state = get_state_manager().get(slot.candidate_tg_id) or {}
    text = await templates.tpl(
        getattr(slot, "candidate_city_id", None),
        template_key,
        candidate_fio=slot.candidate_fio or "",
        city_name=state.get("city_name") or "",
        dt=fmt_dt_local(slot.start_utc, tz),
        **labels,
    )
    await get_bot().send_message(slot.candidate_tg_id, text)
    await schedule_confirm_prompt(slot.id, slot.candidate_tg_id)

    confirm_text = (
        f"✅ Согласовано: {slot.candidate_fio or slot.candidate_tg_id} — "
        f"{fmt_dt_local(slot.start_utc, DEFAULT_TZ)}"
    )
    await safe_edit_text_or_caption(callback.message, confirm_text)
    await safe_remove_reply_markup(callback.message)
    await callback.answer("Согласовано")


async def handle_reject_slot(callback: CallbackQuery) -> None:
    slot_id = int(callback.data.split(":", 1)[1])
    slot = await get_slot(slot_id)
    if not slot:
        await callback.answer("Заявка уже обработана.")
        await safe_remove_reply_markup(callback.message)
        return

    if slot.status == SlotStatus.BOOKED:
        await callback.answer("Уже согласовано — слот занят.", show_alert=True)
        await safe_remove_reply_markup(callback.message)
        return

    await reject_slot(slot_id)

    bot = get_bot()
    await bot.send_message(slot.candidate_tg_id, "К сожалению, выбранное время недоступно.")

    st = get_state_manager().get(slot.candidate_tg_id) or {}
    if st.get("flow") == "intro":
        await show_recruiter_menu(slot.candidate_tg_id)
    else:
        city_for_candidate = st.get("city_id") or getattr(slot, "candidate_city_id", None)
        kb = await kb_recruiters(
            st.get("candidate_tz", DEFAULT_TZ), city_id=city_for_candidate
        )
        await bot.send_message(
            slot.candidate_tg_id,
            await templates.tpl(getattr(slot, "candidate_city_id", None), "choose_recruiter"),
            reply_markup=kb,
        )

    await safe_edit_text_or_caption(callback.message, "❌ Отказано. Слот освобождён.")
    await safe_remove_reply_markup(callback.message)
    await callback.answer("Отказано")


async def handle_attendance_yes(callback: CallbackQuery) -> None:
    slot_id = int(callback.data.split(":", 1)[1])
    slot = await get_slot(slot_id)
    if not slot or slot.status != SlotStatus.BOOKED:
        await callback.answer("Заявка не найдена или ещё не подтверждена рекрутёром.", show_alert=True)
        return

    key: RemKey = (slot_id, callback.from_user.id)
    t = CONFIRM_TASKS.pop(key, None)
    if t and not t.done():
        t.cancel()

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

    await schedule_reminder(slot_id, slot.candidate_tg_id)

    try:
        await callback.message.edit_text("Спасибо! Участие подтверждено. Ссылка отправлена.")
    except TelegramBadRequest:
        pass
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except TelegramBadRequest:
        pass

    await callback.answer("Подтверждено")


async def handle_attendance_no(callback: CallbackQuery) -> None:
    slot_id = int(callback.data.split(":", 1)[1])
    slot = await get_slot(slot_id)
    if not slot:
        await callback.answer("Заявка уже обработана.")
        await safe_remove_reply_markup(callback.message)
        return

    key: RemKey = (slot_id, slot.candidate_tg_id)
    t = CONFIRM_TASKS.pop(key, None)
    if t and not t.done():
        t.cancel()
    t2 = REMINDERS.pop(key, None)
    if t2 and not t2.done():
        t2.cancel()

    await reject_slot(slot_id)

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

    st = get_state_manager().get(callback.from_user.id) or {}
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
    "get_bot",
    "get_rating",
    "get_state_manager",
    "now_utc",
    "save_test1_answer",
    "schedule_confirm_prompt",
    "schedule_reminder",
    "send_test1_question",
    "send_test2_question",
    "show_recruiter_menu",
    "slot_local_labels",
    "start_introday_flow",
    "start_test2",
    "begin_interview",
    "send_welcome",
    "safe_edit_text_or_caption",
    "safe_remove_reply_markup",
    "handle_approve_slot",
    "handle_reject_slot",
    "_extract_option_label",
    "_extract_option_value",
    "_mark_test1_question_answered",
    "_shorten_answer",
]
