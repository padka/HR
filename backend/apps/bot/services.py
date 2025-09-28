"""Supporting services and helpers for the Telegram bot."""

from __future__ import annotations

import asyncio
import html
import logging
import math
import os
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Tuple, cast
from zoneinfo import ZoneInfo

from aiogram import Bot
from aiogram import Dispatcher
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, ForceReply, Message, FSInputFile

from backend.domain.models import SlotStatus
from backend.domain.repositories import (
    approve_slot,
    get_city_by_name,
    get_free_slots_by_recruiter,
    get_recruiter,
    get_slot,
    reject_slot,
    reserve_slot,
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


class StateManager:
    """Simple in-memory state storage for bot flows."""

    def __init__(self) -> None:
        self._storage: Dict[int, State] = {}

    def get(self, user_id: int) -> Optional[State]:
        return self._storage.get(user_id)

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

@dataclass(slots=True)
class BotContext:
    """Aggregates stateful bot dependencies for explicit injection.

    The in-memory reminder registries are kept together with other runtime
    components so they can be swapped with a persistent scheduler (e.g. Redis,
    APScheduler) without touching business logic.
    """

    bot: Bot
    dispatcher: Dispatcher
    state_manager: StateManager
    reminders: Dict[RemKey, asyncio.Task] = field(default_factory=dict)
    confirm_tasks: Dict[RemKey, asyncio.Task] = field(default_factory=dict)

    def reset_tasks(self) -> None:
        """Cancel and clear scheduled reminder tasks."""

        for task in list(self.reminders.values()):
            if not task.done():
                task.cancel()
        self.reminders.clear()

        for task in list(self.confirm_tasks.values()):
            if not task.done():
                task.cancel()
        self.confirm_tasks.clear()


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


async def schedule_reminder(context: BotContext, slot_id: int, candidate_id: int) -> None:
    bot = context.bot
    key: RemKey = (slot_id, candidate_id)
    t2 = context.reminders.pop(key, None)
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

    context.reminders[key] = asyncio.create_task(_rem())


async def schedule_confirm_prompt(
    context: BotContext, slot_id: int, candidate_id: int
) -> None:
    bot = context.bot
    key: RemKey = (slot_id, candidate_id)
    t = context.confirm_tasks.pop(key, None)
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
            state = context.state_manager.get(candidate_id) or {}
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

    context.confirm_tasks[key] = asyncio.create_task(_rem())


async def begin_interview(context: BotContext, user_id: int) -> None:
    state_manager = context.state_manager
    bot = context.bot
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
    await send_test1_question(context, user_id)


async def send_welcome(context: BotContext, user_id: int) -> None:
    bot = context.bot
    text = (
        "👋 Добро пожаловать!\n"
        "Нажмите «Начать», чтобы заполнить мини-анкету и выбрать время для интервью."
    )
    await bot.send_message(user_id, text, reply_markup=kb_start())


async def start_introday_flow(context: BotContext, message: Message) -> None:
    state_manager = context.state_manager
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
    await start_test2(context, user_id)


def _format_prompt(prompt: Any) -> str:
    if isinstance(prompt, (list, tuple)):
        return "\n".join(str(p) for p in prompt)
    return str(prompt)


async def send_test1_question(context: BotContext, user_id: int) -> None:
    bot = context.bot
    state_manager = context.state_manager
    state = state_manager.ensure(user_id)
    sequence = state.get("t1_sequence") or list(TEST1_QUESTIONS)
    idx = state.get("t1_idx", 0)
    total = len(sequence)
    if idx >= total:
        await finalize_test1(context, user_id)
        return
    q = sequence[idx]
    progress = await templates.tpl(state.get("city_id"), "t1_progress", n=idx + 1, total=total)
    progress_bar = create_progress_bar(idx, total)
    helper = q.get("helper")
    base_text = f"{progress}\n{progress_bar}\n\n{_format_prompt(q['prompt'])}"
    if helper:
        base_text += f"\n\n<i>{helper}</i>"

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


def _shorten_answer(text: str, limit: int = 80) -> str:
    clean = text.strip()
    if len(clean) <= limit:
        return clean
    return clean[: limit - 1] + "…"


async def _mark_test1_question_answered(
    context: BotContext, user_id: int, summary: str
) -> None:
    bot = context.bot
    state = context.state_manager.get(user_id)
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
    context: BotContext, user_id: int, question: Dict[str, Any], answer: str
) -> None:
    state_manager = context.state_manager
    state = state_manager.ensure(user_id)
    state.setdefault("test1_answers", {})
    state["test1_answers"][question["id"]] = answer
    sequence = state.setdefault("t1_sequence", list(TEST1_QUESTIONS))

    if question["id"] == "fio":
        state["fio"] = answer
    elif question["id"] == "city":
        state["city_name"] = answer
        city = await get_city_by_name(answer)
        if city:
            state["city_id"] = city.id
            state["candidate_tz"] = city.tz
        else:
            state["city_id"] = None
            state["candidate_tz"] = DEFAULT_TZ
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


async def handle_test1_answer(context: BotContext, message: Message) -> None:
    user_id = message.from_user.id
    state = context.state_manager.get(user_id)
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

    await save_test1_answer(context, user_id, question, answer_text)
    await _mark_test1_question_answered(context, user_id, _shorten_answer(answer_text))

    state["t1_idx"] = idx + 1
    if state["t1_idx"] >= total:
        await finalize_test1(context, user_id)
    else:
        await send_test1_question(context, user_id)


async def handle_test1_option(context: BotContext, callback: CallbackQuery) -> None:
    user_id = callback.from_user.id
    state = context.state_manager.get(user_id)
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

    label = _extract_option_label(options[opt_idx])
    value = _extract_option_value(options[opt_idx])

    await save_test1_answer(user_id, question, value)
    await _mark_test1_question_answered(user_id, label)

    state["t1_idx"] = idx + 1

    await callback.answer(f"Выбрано: {label}")

    if state["t1_idx"] >= len(sequence):
        await finalize_test1(user_id)
    else:
        await send_test1_question(context, user_id)


async def finalize_test1(context: BotContext, user_id: int) -> None:
    bot = context.bot
    state_manager = context.state_manager
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

    fname = f"test1_{(state.get('fio') or user_id)}.txt"
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
        interview_dt_hint="выберите удобное время из списка ниже",
    )
    await bot.send_message(user_id, invite_text)

    await show_recruiter_menu(context, user_id)

    state["t1_idx"] = None
    state["t1_last_prompt_id"] = None
    state["t1_last_question_text"] = ""
    state["t1_requires_free_text"] = False


async def start_test2(context: BotContext, user_id: int) -> None:
    bot = context.bot
    state = context.state_manager.ensure(user_id)
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
    await send_test2_question(context, user_id, 0)


async def send_test2_question(context: BotContext, user_id: int, q_index: int) -> None:
    bot = context.bot
    state = context.state_manager.ensure(user_id)
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


async def handle_test2_answer(context: BotContext, callback: CallbackQuery) -> None:
    user_id = callback.from_user.id
    state = context.state_manager.get(user_id)
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
            await send_test2_question(context, user_id, q_index + 1)
        else:
            await finalize_test2(context, user_id)
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
                await send_test2_question(context, user_id, q_index + 1)
            else:
                await finalize_test2(context, user_id)


async def finalize_test2(context: BotContext, user_id: int) -> None:
    bot = context.bot
    state_manager = context.state_manager
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
        context.state_manager.pop(user_id)
        return

    await show_recruiter_menu(context, user_id)


async def show_recruiter_menu(
    context: BotContext, user_id: int, *, notice: Optional[str] = None
) -> None:
    bot = context.bot
    state = context.state_manager.get(user_id) or {}
    tz_label = state.get("candidate_tz", DEFAULT_TZ)
    kb = await kb_recruiters(tz_label)
    text = await templates.tpl(state.get("city_id"), "choose_recruiter")
    if notice:
        text = f"{notice}\n\n{text}"
    await bot.send_message(user_id, text, reply_markup=kb)


async def handle_home_start(context: BotContext, callback: CallbackQuery) -> None:
    await callback.answer()
    await begin_interview(context, callback.from_user.id)


async def handle_pick_recruiter(context: BotContext, callback: CallbackQuery) -> None:
    user_id = callback.from_user.id
    rid_s = callback.data.split(":", 1)[1]

    state_manager = context.state_manager
    state = state_manager.get(user_id)

    if rid_s == "__again__":
        tz_label = (state or {}).get("candidate_tz", DEFAULT_TZ)
        kb = await kb_recruiters(tz_label)
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

    state["picked_recruiter_id"] = rid
    tz_label = state.get("candidate_tz", DEFAULT_TZ)
    slots_list = await get_free_slots_by_recruiter(rid)
    kb = await kb_slots_for_recruiter(rid, tz_label, slots=slots_list)
    text = _recruiter_header(rec.name, tz_label)
    if not slots_list:
        text = f"{text}\n\n{await templates.tpl(state.get('city_id'), 'no_slots')}"
    try:
        await callback.message.edit_text(text, reply_markup=kb)
    except TelegramBadRequest:
        await callback.message.edit_text(text)
        await callback.message.edit_reply_markup(reply_markup=kb)
    await callback.answer()


async def handle_refresh_slots(context: BotContext, callback: CallbackQuery) -> None:
    user_id = callback.from_user.id
    _, rid_s = callback.data.split(":", 1)
    try:
        rid = int(rid_s)
    except ValueError:
        await callback.answer("Рекрутёр не найден", show_alert=True)
        return

    state = context.state_manager.get(user_id)
    if not state:
        await callback.answer("Сессия истекла. Введите /start", show_alert=True)
        return

    tz_label = state.get("candidate_tz", DEFAULT_TZ)
    slots_list = await get_free_slots_by_recruiter(rid)
    kb = await kb_slots_for_recruiter(rid, tz_label, slots=slots_list)
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


async def handle_pick_slot(context: BotContext, callback: CallbackQuery) -> None:
    user_id = callback.from_user.id
    _, rid_s, slot_id_s = callback.data.split(":", 2)

    try:
        slot_id = int(slot_id_s)
    except ValueError:
        await callback.answer("Слот не найден", show_alert=True)
        return

    state = context.state_manager.get(user_id)
    if not state:
        await callback.answer("Сессия истекла. Введите /start", show_alert=True)
        return

    is_intro = state.get("flow") == "intro"
    slot = await reserve_slot(
        slot_id,
        candidate_tg_id=user_id,
        candidate_fio=state.get("fio", str(user_id)),
        candidate_tz=state.get("candidate_tz", DEFAULT_TZ),
        candidate_city_id=state.get("city_id"),
        purpose="intro_day" if is_intro else "interview",
    )
    if not slot:
        text = await templates.tpl(state.get("city_id"), "slot_taken")
        if is_intro:
            try:
                await callback.message.edit_text(text)
                await callback.message.edit_reply_markup(reply_markup=None)
            except TelegramBadRequest:
                pass
            await show_recruiter_menu(context, user_id, notice=text)
        else:
            kb = await kb_slots_for_recruiter(
                int(rid_s), state.get("candidate_tz", DEFAULT_TZ)
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
    bot = context.bot
    caption = (
        f"📥 <b>Новый кандидат на {purpose}</b>\n"
        f"👤 {slot.candidate_fio or user_id}\n"
        f"📍 {state.get('city_name','—')}\n"
        f"🗓 {fmt_dt_local(slot.start_utc, (rec.tz if rec else DEFAULT_TZ) or DEFAULT_TZ)}\n"
    )

    attached = False
    for name in [
        f"test1_{state.get('fio') or user_id}.txt",
        f"report_{state.get('fio') or user_id}.txt",
    ]:
        if os.path.exists(name):
            try:
                if rec and rec.tg_chat_id:
                    await bot.send_document(
                        rec.tg_chat_id,
                        FSInputFile(name),
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


async def handle_approve_slot(context: BotContext, callback: CallbackQuery) -> None:
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
    state = context.state_manager.get(slot.candidate_tg_id, {})
    text = await templates.tpl(
        getattr(slot, "candidate_city_id", None),
        template_key,
        candidate_fio=slot.candidate_fio or "",
        city_name=state.get("city_name") or "",
        dt=fmt_dt_local(slot.start_utc, tz),
        **labels,
    )
    await context.bot.send_message(slot.candidate_tg_id, text)
    await schedule_confirm_prompt(context, slot.id, slot.candidate_tg_id)

    confirm_text = (
        f"✅ Согласовано: {slot.candidate_fio or slot.candidate_tg_id} — "
        f"{fmt_dt_local(slot.start_utc, DEFAULT_TZ)}"
    )
    await safe_edit_text_or_caption(callback.message, confirm_text)
    await safe_remove_reply_markup(callback.message)
    await callback.answer("Согласовано")


async def handle_reject_slot(context: BotContext, callback: CallbackQuery) -> None:
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

    bot = context.bot
    await bot.send_message(slot.candidate_tg_id, "К сожалению, выбранное время недоступно.")

    st = context.state_manager.get(slot.candidate_tg_id, {})
    if st.get("flow") == "intro":
        await show_recruiter_menu(context, slot.candidate_tg_id)
    else:
        kb = await kb_recruiters(st.get("candidate_tz", DEFAULT_TZ))
        await bot.send_message(
            slot.candidate_tg_id,
            await templates.tpl(getattr(slot, "candidate_city_id", None), "choose_recruiter"),
            reply_markup=kb,
        )

    await safe_edit_text_or_caption(callback.message, "❌ Отказано. Слот освобождён.")
    await safe_remove_reply_markup(callback.message)
    await callback.answer("Отказано")


async def handle_attendance_yes(context: BotContext, callback: CallbackQuery) -> None:
    slot_id = int(callback.data.split(":", 1)[1])
    slot = await get_slot(slot_id)
    if not slot or slot.status != SlotStatus.BOOKED:
        await callback.answer("Заявка не найдена или ещё не подтверждена рекрутёром.", show_alert=True)
        return

    key: RemKey = (slot_id, callback.from_user.id)
    t = context.confirm_tasks.pop(key, None)
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
    bot = context.bot
    await bot.send_message(slot.candidate_tg_id, text)

    await schedule_reminder(context, slot_id, slot.candidate_tg_id)

    try:
        await callback.message.edit_text("Спасибо! Участие подтверждено. Ссылка отправлена.")
    except TelegramBadRequest:
        pass
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except TelegramBadRequest:
        pass

    await callback.answer("Подтверждено")


async def handle_attendance_no(context: BotContext, callback: CallbackQuery) -> None:
    slot_id = int(callback.data.split(":", 1)[1])
    slot = await get_slot(slot_id)
    if not slot:
        await callback.answer("Заявка уже обработана.")
        await safe_remove_reply_markup(callback.message)
        return

    key: RemKey = (slot_id, slot.candidate_tg_id)
    t = context.confirm_tasks.pop(key, None)
    if t and not t.done():
        t.cancel()
    t2 = context.reminders.pop(key, None)
    if t2 and not t2.done():
        t2.cancel()

    await reject_slot(slot_id)

    rec = await get_recruiter(slot.recruiter_id)
    bot = context.bot
    if rec and rec.tg_chat_id:
        try:
            await bot.send_message(
                rec.tg_chat_id,
                f"❌ Кандидат {slot.candidate_fio or slot.candidate_tg_id} отказался от слота "
                f"{fmt_dt_local(slot.start_utc, rec.tz or DEFAULT_TZ)}. Слот освобождён.",
            )
        except Exception:
            pass

    st = context.state_manager.get(callback.from_user.id, {})
    await bot.send_message(
        callback.from_user.id,
        await templates.tpl(getattr(slot, "candidate_city_id", None), "att_declined"),
    )
    if st.get("flow") == "intro":
        await show_recruiter_menu(context, callback.from_user.id)
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
    "BotContext",
    "StateManager",
    "calculate_score",
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
    "get_rating",
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
