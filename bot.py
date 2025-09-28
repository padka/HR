# -*- coding: utf-8 -*-
"""
Recruitment TG-bot (aiogram v3)
Логика сохранена 1:1. Наведена структура:
- Константы и типы
- Данные (вопросы/шаблоны)
- Утилиты (форматирование, безоп. правки сообщений)
- Клавиатуры
- Планировщики (напоминания/подтверждения)
- Хэндлеры сценариев (/start, /intro)
- Тест 1 (анкета)
- Тест 2 (множественный выбор)
- Выбор рекрутёра/слота
- Согласование/отклонение
- Подтверждение явки
- Entrypoint
"""

import asyncio
import base64
import html
import json
import logging
import math
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple, TypedDict, Mapping, Sequence
from zoneinfo import ZoneInfo

from aiogram import Bot, Dispatcher, F
from aiogram.client.bot import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ForceReply,
    BufferedInputFile,
)
from aiogram.exceptions import TelegramBadRequest

# === ADMIN DB layer ===
from backend.domain.repositories import (
    get_active_recruiters,
    get_recruiter,
    get_free_slots_by_recruiter,
    get_city_by_name,
    get_city,
    get_slot,
    reserve_slot,
    approve_slot,
    reject_slot,
    get_template,
)
from backend.domain.models import SlotStatus
from backend.core.settings import get_settings
from backend.domain.default_questions import DEFAULT_TEST_QUESTIONS
from backend.domain.template_stages import STAGE_DEFAULTS
from backend.domain.test_questions import load_all_test_questions
from backend.domain.candidates import services as candidate_services


# =============================
#  Константы и типы
# =============================

settings = get_settings()

DEFAULT_TZ = settings.timezone or "Europe/Moscow"
TIME_FMT = "%d.%m %H:%M"

# Порог прохождения теста 2 (доля правильных)
PASS_THRESHOLD = 0.75
MAX_ATTEMPTS = 3
TIME_LIMIT = 120  # сек на вопрос (Тест 2)

# Напоминания/подтверждения: key=(slot_id, candidate_id) -> asyncio.Task
RemKey = Tuple[int, int]

class State(TypedDict, total=False):
    flow: str                    # 'interview' | 'intro'
    t1_idx: Optional[int]
    test1_answers: Dict[str, str]
    t1_last_prompt_id: Optional[int]
    t1_last_question_text: str
    t1_requires_free_text: bool
    t1_sequence: List[Dict[str, Any]]

    fio: str
    city_name: str
    city_id: Optional[int]
    candidate_tz: str

    t2_attempts: Dict[int, Dict[str, Any]]
    picked_recruiter_id: Optional[int]
    picked_slot_id: Optional[int]


# =============================
#  Bootstrap & configuration
# =============================

TOKEN = settings.bot_token
if not TOKEN or ":" not in TOKEN:
    raise SystemExit("BOT_TOKEN не найден или некорректен. Задай BOT_TOKEN=... (или используй .env)")

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# Глобальные in-memory структуры
REMINDERS: Dict[RemKey, asyncio.Task] = {}
CONFIRM_TASKS: Dict[RemKey, asyncio.Task] = {}
user_data: Dict[int, State] = {}   # состояние пользователя


# =============================
#  Данные: Тесты и шаблоны
# =============================

_QUESTIONS_BANK = load_all_test_questions()
test2_questions = _QUESTIONS_BANK.get("test2", DEFAULT_TEST_QUESTIONS.get("test2", [])).copy()
test1_questions = _QUESTIONS_BANK.get("test1", DEFAULT_TEST_QUESTIONS.get("test1", [])).copy()

FOLLOWUP_NOTICE_PERIOD = {
    "id": "notice_period",
    "prompt": (
        "⏳ Сколько времени потребуется, чтобы закрыть все текущие дела и приступить к обучению в нашей компании?\n"
        "<i>Нам важно понимать, сможете ли вы стартовать в ближайшие 2–3 дня.</i>"
    ),
    "placeholder": "Например: через 2 дня / уже готов завтра",
}

FOLLOWUP_STUDY_MODE = {
    "id": "study_mode",
    "prompt": "🎓 Учитесь очно или заочно?",
    "options": [
        "Очно",
        "Очно, но гибкий график",
        "Заочно",
        "Дистанционно",
        "Другое",
    ],
}

FOLLOWUP_STUDY_SCHEDULE = {
    "id": "study_schedule",
    "prompt": (
        "🗓️ Получится ли совмещать учёбу с графиком 5/2 с 9:00 до 18:00?\n"
        "<i>Рабочий график фиксированный, важно понимать вашу готовность.</i>"
    ),
    "options": [
        "Да, смогу",
        "Смогу, но нужен запас по времени",
        "Будет сложно",
        "Нет, не смогу",
    ],
}

DEFAULT_TEMPLATES: Dict[str, str] = {
    # Общие
    "choose_recruiter": (
        "👤 <b>Выбор рекрутёра</b>\n"
        "Нажмите на имя коллеги, чтобы увидеть доступные окна."
    ),
    "slot_taken": "Слот уже занят. Выберите другой:",
    "slot_sent": "Заявка отправлена. Ожидайте подтверждения.",
    "approved_msg": (
        "✅ <b>Встреча подтверждена</b>\n"
        "🗓 {dt}\n"
        "Ссылка/адрес придут после подтверждения явки за 2 часа."
    ),
    "confirm_2h": (
        "⏰ Напоминание: встреча (ознакомительный день) через 2 часа — {dt}.\n"
        "Пожалуйста, подтвердите участие. Ссылка придёт после подтверждения."
    ),
    "reminder_1h": "⏰ Напоминание: встреча (ознакомительный день) через час — {dt}.",
    "att_confirmed_link": "🔗 Ссылка на Яндекс.Телемост: {link}\nВстречаемся {dt}",
    "att_declined": "Понимаю. Давайте подберём другое время.",
    "result_fail": (
        "Спасибо за время! На текущем этапе мы не продолжаем процесс.\n"
        "Мы сохраним ваши контакты и свяжемся при появлении подходящих ролей."
    ),

    # Тест 1
    "t1_intro": (
        "✨ <b>SMART: мини-анкета</b>\n"
        "Ответьте, пожалуйста, на несколько вопросов — это займёт 2–3 минуты и поможет назначить интервью."
    ),
    "t1_progress": "<i>Вопрос {n}/{total}</i>",
    "t1_done": (
        "🎯 Спасибо! Анкета получена.\n"
        "Теперь выберите рекрутёра и время для короткого видео-интервью (15–20 минут)."
    ),

    # Тест 2
    "t2_intro": (
        "📘 <b>Ознакомительный тест</b>\n"
        "Вопросов: {qcount} • Лимит: {timelimit} мин/вопрос • Макс. попыток: {attempts}\n"
        "Учитываем скорость и число попыток."
    ),
    "t2_result": (
        "🎯 <b>Ваш результат</b>\n\n"
        "▫️ <b>Правильных ответов:</b> {correct}\n"
        "▫️ <b>Итоговый балл:</b> {score}\n"
        "▫️ <b>Уровень:</b> {rating}"
    ),

    # Выбор времени (после Теста 2)
    "no_slots": (
        "Пока нет свободных слотов у выбранного рекрутёра.\n"
        "Выберите другого специалиста или попробуйте позже."
    ),
}

DEFAULT_TEMPLATES.update(STAGE_DEFAULTS)


# =============================
#  Утилиты
# =============================

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

async def _fetch_template(city_id: Optional[int], key: str) -> Optional[str]:
    """Вернуть текст шаблона из БД (городской или глобальный), иначе None."""
    try:
        t = await get_template(city_id, key)
    except Exception:
        t = None
    if t is None:
        return None
    if isinstance(t, str):
        return t
    return getattr(t, "text", None) or getattr(t, "content", None)

async def tpl(city_id: Optional[int], key: str, **fmt) -> str:
    text = await _fetch_template(city_id, key) or DEFAULT_TEMPLATES.get(key, "")
    try:
        return text.format(**fmt)
    except Exception:
        return text

async def safe_edit_text_or_caption(cb_msg, text: str) -> None:
    """Безопасно меняет текст сообщения или подпись медиа."""
    try:
        if (cb_msg.document is not None) or (cb_msg.photo is not None) or \
           (cb_msg.video is not None) or (cb_msg.animation is not None):
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


# =============================
#  Клавиатуры
# =============================

def kb_start() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🚀 Начать", callback_data="home:start")]]
    )

def create_keyboard(options: List[str], question_index: int) -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(text=opt, callback_data=f"answer_{question_index}_{i}")
        for i, opt in enumerate(options)
    ]
    return InlineKeyboardMarkup(inline_keyboard=[[btn] for btn in buttons])


def _short_name(name: str) -> str:
    parts = name.split()
    if len(parts) >= 2:
        return f"{parts[0]} {parts[1][0]}.".strip()
    return name


def _slot_button_label(dt_utc: datetime, duration_min: int, tz: str, recruiter_name: Optional[str] = None) -> str:
    local_dt = dt_utc.astimezone(_safe_zone(tz))
    label = local_dt.strftime("%d %b • %H:%M")
    label += f" • {duration_min}м"
    if recruiter_name:
        label += f" • {recruiter_name}"
    return label


def _format_prompt(prompt: Any) -> str:
    if isinstance(prompt, (list, tuple)):
        return "\n".join(str(p) for p in prompt)
    return str(prompt)

async def kb_recruiters(candidate_tz: str = DEFAULT_TZ) -> InlineKeyboardMarkup:
    recs = await get_active_recruiters()
    if not recs:
        return InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="Рекрутёры не найдены", callback_data="noop")]]
        )

    seen_names: set[str] = set()
    rows: List[List[InlineKeyboardButton]] = []
    for recruiter in recs:
        key = recruiter.name.strip().lower()
        if key in seen_names:
            continue
        seen_names.add(key)

        slots = await get_free_slots_by_recruiter(recruiter.id)
        if not slots:
            continue

        next_local = fmt_dt_local(slots[0].start_utc, candidate_tz)
        label_suffix = f"{next_local} • {min(len(slots), 99)} сл."
        text = f"👤 {_short_name(recruiter.name)} — {label_suffix}"
        rows.append([
            InlineKeyboardButton(text=text, callback_data=f"pick_rec:{recruiter.id}")
        ])

    if not rows:
        no_rows = [
            [InlineKeyboardButton(text="Временно нет свободных рекрутёров", callback_data="noop")]
        ]
        return InlineKeyboardMarkup(inline_keyboard=no_rows)

    return InlineKeyboardMarkup(inline_keyboard=rows)

async def kb_slots_for_recruiter(recruiter_id: int, candidate_tz: str, *, slots: Optional[List[Any]] = None) -> InlineKeyboardMarkup:
    if slots is None:
        slots = await get_free_slots_by_recruiter(recruiter_id)
    if not slots:
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Обновить", callback_data=f"refresh_slots:{recruiter_id}")],
                [InlineKeyboardButton(text="👤 К рекрутёрам", callback_data="pick_rec:__again__")],
            ]
        )
    buttons = [
        InlineKeyboardButton(
            text=_slot_button_label(s.start_utc, s.duration_min, candidate_tz),
            callback_data=f"pick_slot:{recruiter_id}:{s.id}",
        )
        for s in slots[:12]
    ]
    rows: List[List[InlineKeyboardButton]] = []
    for i in range(0, len(buttons), 2):
        rows.append(buttons[i:i + 2])
    rows.append([
        InlineKeyboardButton(text="🔄 Обновить", callback_data=f"refresh_slots:{recruiter_id}"),
        InlineKeyboardButton(text="👤 Другой рекрутёр", callback_data="pick_rec:__again__"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)



def _recruiter_header(name: str, tz_label: str) -> str:
    return (
        f"👤 <b>{name}</b>\n"
        f"🕒 Время отображается в вашем поясе: <b>{tz_label}</b>.\n"
        "Выберите удобное окно:"
    )


async def _show_recruiter_menu(user_id: int, *, notice: Optional[str] = None) -> None:
    state = user_data.get(user_id) or {}
    tz_label = state.get("candidate_tz", DEFAULT_TZ)
    kb = await kb_recruiters(tz_label)
    text = await tpl(state.get("city_id"), "choose_recruiter")
    if notice:
        text = f"{notice}\n\n{text}"
    await bot.send_message(user_id, text, reply_markup=kb)


def kb_approve(slot_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Согласовано", callback_data=f"approve:{slot_id}")],
            [InlineKeyboardButton(text="❌ Отказать", callback_data=f"reject:{slot_id}")],
        ]
    )

def kb_attendance_confirm(slot_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(text="✅ Подтверждаю", callback_data=f"att_yes:{slot_id}"),
            InlineKeyboardButton(text="❌ Не смогу", callback_data=f"att_no:{slot_id}")
        ]]
    )


# =============================
#  Планировщики уведомлений
# =============================

async def schedule_reminder(slot_id: int, candidate_id: int):
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

    async def _rem():
        try:
            await asyncio.sleep(delay)
            fresh = await get_slot(slot_id)
            if not fresh or fresh.candidate_tg_id != candidate_id:
                return
            tz = fresh.candidate_tz or DEFAULT_TZ
            labels = slot_local_labels(fresh.start_utc, tz)
            text = await tpl(
                getattr(fresh, "candidate_city_id", None),
                "reminder_1h",
                candidate_fio=getattr(fresh, "candidate_fio", "") or "",
                dt=fmt_dt_local(fresh.start_utc, tz),
                **labels,
            )
            await bot.send_message(candidate_id, text)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logging.exception("Reminder error: %s", e)

    REMINDERS[key] = asyncio.create_task(_rem())

async def schedule_confirm_prompt(slot_id: int, candidate_id: int):
    """За 2 часа до встречи просим подтвердить участие. Потом шлём ссылку."""
    key: RemKey = (slot_id, candidate_id)
    t = CONFIRM_TASKS.pop(key, None)
    if t and not t.done():
        t.cancel()

    slot = await get_slot(slot_id)
    if not slot:
        return

    start_utc = slot.start_utc
    delay = (start_utc - now_utc()).total_seconds() - 7200  # -2h

    async def _ask_now():
        try:
            fresh = await get_slot(slot_id)
            if not fresh or fresh.candidate_tg_id != candidate_id:
                return
            tz = fresh.candidate_tz or DEFAULT_TZ
            labels = slot_local_labels(fresh.start_utc, tz)
            key = "stage4_intro_reminder" if getattr(fresh, "purpose", "interview") == "intro_day" else "stage2_interview_reminder"
            state = user_data.get(candidate_id, {})
            text = await tpl(
                getattr(fresh, "candidate_city_id", None),
                key,
                candidate_fio=getattr(fresh, "candidate_fio", "") or "",
                city_name=state.get("city_name") or "",
                dt=fmt_dt_local(fresh.start_utc, tz),
                **labels,
            )
            await bot.send_message(candidate_id, text, reply_markup=kb_attendance_confirm(slot_id))
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logging.exception("Confirm prompt error: %s", e)

    if delay <= 0:
        await _ask_now()
        return

    async def _rem():
        try:
            await asyncio.sleep(delay)
            await _ask_now()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logging.exception("Confirm scheduler error: %s", e)

    CONFIRM_TASKS[key] = asyncio.create_task(_rem())


# =============================
#  Хэндлеры запуска сценариев
# =============================

async def begin_interview(user_id: int):
    """Инициализирует сценарий A (анкета → выбор рекрутёра/слота)."""
    user_data[user_id] = State(
        flow="interview",
        t1_idx=0,
        test1_answers={},
        t1_last_prompt_id=None,
        t1_last_question_text="",
        t1_requires_free_text=True,
        t1_sequence=list(test1_questions),
        fio="",
        city_name="",
        city_id=None,
        candidate_tz=DEFAULT_TZ,
        t2_attempts={},
        picked_recruiter_id=None,
        picked_slot_id=None,
    )
    await bot.send_message(user_id, await tpl(None, "t1_intro"))
    await send_test1_question(user_id)

async def send_welcome(user_id: int):
    """Показывает приветствие и кнопку старта, если чат пуст/контекст не инициализирован."""
    text = (
        "👋 Добро пожаловать!\n"
        "Нажмите «Начать», чтобы заполнить мини-анкету и выбрать время для интервью."
    )
    await bot.send_message(user_id, text, reply_markup=kb_start())

@dp.message(Command(commands=["start"]))
async def start_interview_flow(message: Message):
    """
    Сценарий A: кандидат только откликнулся.
    Тест 1 (анкета) → выбор рекрутёра и слота для видео-интервью.
    """
    await begin_interview(message.from_user.id)

@dp.message(Command(commands=["intro", "test2"]))
async def start_introday_flow(message: Message):
    """
    Сценарий B: статус в Notion → «Прошел собеседование».
    Запускаем Тест 2 → сразу выбор времени для ознакомительного дня.
    """
    user_id = message.from_user.id
    prev = user_data.get(user_id, {})
    fio = prev.get("fio", "")
    city_name = prev.get("city_name", "")
    city_id = prev.get("city_id", None)
    candidate_tz = prev.get("candidate_tz", DEFAULT_TZ)

    user_data[user_id] = State(
        flow="intro",
        t1_idx=None,
        test1_answers=prev.get("test1_answers", {}),
        t1_last_prompt_id=None,
        t1_last_question_text="",
        t1_requires_free_text=False,
        t1_sequence=prev.get("t1_sequence", list(test1_questions)),
        fio=fio,
        city_name=city_name,
        city_id=city_id,
        candidate_tz=candidate_tz,
        t2_attempts={},
        picked_recruiter_id=None,
        picked_slot_id=None,
    )
    await start_test2(user_id)


# =============================
#  Тест 1: анкета (свободные ответы)
# =============================

async def send_test1_question(user_id: int):
    state = user_data.get(user_id)
    if not state:
        return
    idx = state.get("t1_idx", 0)
    sequence = state.get("t1_sequence") or list(test1_questions)
    total = len(sequence)
    if idx >= total:
        await finalize_test1(user_id)
        return
    q = sequence[idx]
    progress = await tpl(state.get("city_id"), "t1_progress", n=idx + 1, total=total)
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


def _build_test1_options_markup(question_idx: int, options: List[Any]) -> InlineKeyboardMarkup:
    buttons: List[InlineKeyboardButton] = []
    for opt_idx, option in enumerate(options):
        label = _extract_option_label(option)
        buttons.append(
            InlineKeyboardButton(text=label, callback_data=f"t1opt:{question_idx}:{opt_idx}")
        )

    rows: List[List[InlineKeyboardButton]] = [[btn] for btn in buttons]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _extract_option_label(option: Any) -> str:
    if isinstance(option, dict):
        return str(option.get("label") or option.get("value") or "-")
    if isinstance(option, (list, tuple)) and option:
        return str(option[0])
    return str(option)


def _extract_option_value(option: Any) -> str:
    if isinstance(option, dict):
        value = option.get("value") or option.get("label")
        return "" if value is None else str(value)
    if isinstance(option, (list, tuple)):
        if len(option) >= 2:
            return str(option[1])
        if option:
            return str(option[0])
        return ""
    return str(option)


def _shorten_answer(text: str, limit: int = 80) -> str:
    cleaned = text.strip()
    if not cleaned:
        return "Ответ записан"
    return (cleaned[: limit - 1] + "…") if len(cleaned) > limit else cleaned


def _normalize_filename_component(raw: Optional[str], fallback: str) -> str:
    if not raw:
        return fallback
    cleaned = "".join(ch for ch in raw if ch.isalnum() or ch in {" ", "_", "-"}).strip()
    return cleaned.replace(" ", "_") or fallback


def _render_survey_summary(meta: Mapping[str, Any], questions: Sequence[Mapping[str, Any]]) -> str:
    created_raw = meta.get("created_at")
    created_dt = None
    if isinstance(created_raw, str):
        try:
            created_dt = datetime.fromisoformat(created_raw)
        except ValueError:
            created_dt = None
    if created_dt is None:
        created_dt = datetime.now()

    lines = [
        "📋 Анкета кандидата (Тест 1)",
        "━━━━━━━━━━━━━━━━━━━━",
        f"Дата: {created_dt.astimezone().strftime('%Y-%m-%d %H:%M')}",
        f"TG ID: {meta.get('telegram_id') or meta.get('tg_id') or '—'}",
        f"ФИО: {meta.get('fio') or '—'}",
        f"Город: {meta.get('city') or '—'}",
        "",
        "Ответы:",
    ]

    for entry in questions:
        prompt = str(entry.get("prompt") or entry.get("title") or entry.get("id") or "—")
        answer = entry.get("answer")
        answer_text = "—" if answer is None or str(answer).strip() == "" else str(answer)
        lines.append(f"- {prompt}\n  {answer_text}")

    return "\n".join(lines)


def _prepare_survey_attachment(
    user_label: str,
    payload: Any,
    created_at: datetime,
    fallback_label: str,
) -> BufferedInputFile:
    meta: Mapping[str, Any] = {}
    questions: Sequence[Mapping[str, Any]] = []
    summary_text: Optional[str] = None
    html_content: Optional[str] = None
    pdf_bytes: Optional[bytes] = None

    if isinstance(payload, dict):
        meta_candidate = payload.get("meta")
        if isinstance(meta_candidate, dict):
            meta = {**meta_candidate}
        else:
            meta = {}
        meta.setdefault("telegram_id", meta.get("tg_id"))
        questions_candidate = payload.get("questions")
        if isinstance(questions_candidate, list):
            questions = [entry for entry in questions_candidate if isinstance(entry, dict)]
        summary_text = payload.get("summary_text") or payload.get("summary")
        html_candidate = payload.get("report_html")
        html_content = html_candidate if isinstance(html_candidate, str) else None
        pdf_candidate = payload.get("report_pdf")
        if isinstance(pdf_candidate, str):
            try:
                pdf_bytes = base64.b64decode(pdf_candidate)
            except Exception:
                pdf_bytes = pdf_candidate.encode("utf-8")
        elif isinstance(pdf_candidate, (bytes, bytearray)):
            pdf_bytes = bytes(pdf_candidate)
    elif isinstance(payload, str):
        summary_text = payload

    if not meta:
        meta = {"telegram_id": fallback_label, "fio": user_label, "city": "", "created_at": created_at.isoformat()}
    else:
        meta.setdefault("telegram_id", meta.get("telegram_id") or fallback_label)
        meta.setdefault("fio", meta.get("fio") or user_label)
        meta.setdefault("city", meta.get("city") or "")
        meta.setdefault("created_at", meta.get("created_at") or created_at.isoformat())

    if not summary_text:
        if questions:
            summary_text = _render_survey_summary(meta, questions)
        else:
            summary_text = json.dumps(payload, ensure_ascii=False, indent=2)

    base_label = _normalize_filename_component(user_label, fallback_label)

    if pdf_bytes:
        return BufferedInputFile(pdf_bytes, filename=f"report_{base_label}.pdf")
    if html_content:
        return BufferedInputFile(html_content.encode("utf-8"), filename=f"report_{base_label}.html")

    return BufferedInputFile(summary_text.encode("utf-8"), filename=f"test1_{base_label}.txt")
async def _mark_test1_question_answered(user_id: int, summary: str) -> None:
    state = user_data.get(user_id)
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


async def _save_test1_answer(user_id: int, question: Dict[str, Any], answer: str) -> None:
    state = user_data[user_id]
    state.setdefault("test1_answers", {})
    state["test1_answers"][question["id"]] = answer
    sequence = state.setdefault("t1_sequence", list(test1_questions))

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

@dp.message()
async def free_text_router(message: Message):
    """
    Роутер свободного текста:
      - если ждём ответ для Теста 1 — принимаем;
      - иначе игнорируем (Тест 2 кликается кнопками).
    """
    user_id = message.from_user.id
    state = user_data.get(user_id)
    if not state:
        await send_welcome(user_id)
        return
    if state.get("flow") == "interview":
        idx = state.get("t1_idx")
        if isinstance(idx, int):
            await handle_test1_answer(message)

async def handle_test1_answer(message: Message):
    user_id = message.from_user.id
    state = user_data.get(user_id)
    if not state:
        return

    idx = state.get("t1_current_idx", state.get("t1_idx", 0))
    sequence = state.get("t1_sequence") or list(test1_questions)
    total = len(sequence)
    if idx >= total:
        return

    q = sequence[idx]
    if not state.get("t1_requires_free_text", True):
        await message.reply("Пожалуйста, выберите вариант ответа с помощью кнопок под вопросом.")
        return

    prompt_id = state.get("t1_last_prompt_id")
    if prompt_id:
        if not message.reply_to_message or message.reply_to_message.message_id != prompt_id:
            await message.reply("Нажмите «Ответить» на сообщение с вопросом, чтобы зафиксировать ответ.")
            return

    ans = (message.text or "").strip()
    if not ans:
        await message.reply("Ответ не распознан. Напишите текст или выберите вариант.")
        return

    await _save_test1_answer(user_id, q, ans)
    await _mark_test1_question_answered(user_id, _shorten_answer(ans))

    state["t1_idx"] = idx + 1
    if state["t1_idx"] >= total:
        await finalize_test1(user_id)
    else:
        await send_test1_question(user_id)


@dp.callback_query(F.data.startswith("t1opt:"))
async def handle_test1_option(callback: CallbackQuery):
    user_id = callback.from_user.id
    state = user_data.get(user_id)
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

    sequence = state.get("t1_sequence") or list(test1_questions)
    if idx >= len(sequence):
        await callback.answer("Вопрос недоступен", show_alert=True)
        return

    q = sequence[idx]
    options = q.get("options") or []
    if opt_idx < 0 or opt_idx >= len(options):
        await callback.answer("Вариант недоступен", show_alert=True)
        return

    label = _extract_option_label(options[opt_idx])
    value = _extract_option_value(options[opt_idx])

    await _save_test1_answer(user_id, q, value)
    await _mark_test1_question_answered(user_id, label)

    state["t1_idx"] = idx + 1

    await callback.answer(f"Выбрано: {label}")

    if state["t1_idx"] >= len(sequence):
        await finalize_test1(user_id)
    else:
        await send_test1_question(user_id)

async def finalize_test1(user_id: int):
    """Завершили Тест 1 → отчёт → выбор рекрутёра/слота (видео-интервью)."""
    state = user_data[user_id]
    sequence = state.get("t1_sequence", list(test1_questions))
    answers = state.get("test1_answers") or {}
    created_at = datetime.now(timezone.utc)
    meta = {
        "telegram_id": user_id,
        "fio": state.get("fio") or "",
        "city": state.get("city_name") or "",
        "created_at": created_at.isoformat(),
    }
    question_entries: List[Dict[str, Any]] = []
    for q in sequence:
        qid = q.get("id")
        prompt = q.get("prompt") or str(qid)
        answer_value = answers.get(qid, "—")
        question_entries.append({"id": qid, "prompt": prompt, "answer": answer_value})

    summary_text = _render_survey_summary(meta, question_entries)

    fio_value = state.get("fio") or str(user_id)
    city_value = state.get("city_name") or ""
    user_record = await candidate_services.create_or_update_user(
        telegram_id=user_id,
        fio=fio_value,
        city=city_value,
    )
    state["candidate_db_id"] = user_record.id

    payload = {
        "meta": meta,
        "questions": question_entries,
        "summary_text": summary_text,
    }
    await candidate_services.save_survey_response(user_record.id, payload)

    invite_text = await tpl(
        state.get("city_id"),
        "stage1_invite",
        candidate_fio=state.get("fio") or "",
        city_name=state.get("city_name") or "",
        interview_dt_hint="выберите удобное время из списка ниже",
    )
    await bot.send_message(user_id, invite_text)

    await _show_recruiter_menu(user_id)

    state["t1_idx"] = None
    state["t1_last_prompt_id"] = None
    state["t1_last_question_text"] = ""
    state["t1_requires_free_text"] = False


# =============================
#  Тест 2: множественный выбор
# =============================

async def start_test2(user_id: int):
    state = user_data[user_id]
    state["t2_attempts"] = {
        q_index: {"answers": [], "is_correct": False, "start_time": None}
        for q_index in range(len(test2_questions))
    }
    intro = await tpl(
        state.get("city_id"),
        "t2_intro",
        qcount=len(test2_questions),
        timelimit=TIME_LIMIT // 60,
        attempts=MAX_ATTEMPTS,
    )
    await bot.send_message(user_id, intro)
    await send_test2_question(user_id, 0)

async def send_test2_question(user_id: int, q_index: int):
    user_data[user_id]["t2_attempts"][q_index]["start_time"] = datetime.now()
    question = test2_questions[q_index]
    txt = (
        f"🔹 <b>Вопрос {q_index + 1}/{len(test2_questions)}</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"{question['text']}"
    )
    await bot.send_message(user_id, txt, reply_markup=create_keyboard(question["options"], q_index))

@dp.callback_query(lambda c: c.data.startswith("answer_"))
async def test2_answer_handler(callback: CallbackQuery):
    user_id = callback.from_user.id
    state = user_data.get(user_id)
    if not state or "t2_attempts" not in state or state.get("flow") != "intro":
        await callback.answer()
        return

    _, qidx_s, ans_s = callback.data.split("_")
    q_index = int(qidx_s)
    answer_index = int(ans_s)

    attempt = state["t2_attempts"][q_index]
    question = test2_questions[q_index]

    now = datetime.now()
    time_spent = (now - attempt["start_time"]).seconds if attempt["start_time"] else 0
    overtime = time_spent > TIME_LIMIT

    attempt["answers"].append({"answer": answer_index, "time": now.isoformat(), "overtime": overtime})
    is_correct = (answer_index == question["correct"])
    attempt["is_correct"] = is_correct

    if isinstance(question["feedback"], list):
        feedback_message = question["feedback"][answer_index]
    else:
        feedback_message = question["feedback"] if is_correct else "❌ <i>Неверно.</i>"

    if is_correct:
        final_feedback = f"{feedback_message}"
        if overtime:
            final_feedback += "\n⏰ <i>Превышено время</i>"
        if len(attempt["answers"]) > 1:
            penalty = 10 * (len(attempt["answers"]) - 1)
            final_feedback += f"\n⚠️ <i>Попыток: {len(attempt['answers'])} (-{penalty}%)</i>"
        await callback.message.edit_text(final_feedback)

        if q_index < len(test2_questions) - 1:
            await send_test2_question(user_id, q_index + 1)
        else:
            await finalize_test2(user_id)
    else:
        attempts_left = MAX_ATTEMPTS - len(attempt["answers"])
        final_feedback = f"{feedback_message}"
        if attempts_left > 0:
            final_feedback += f"\nОсталось попыток: {attempts_left}"
            await callback.message.edit_text(final_feedback, reply_markup=create_keyboard(question["options"], q_index))
        else:
            final_feedback += "\n🚫 <i>Лимит попыток исчерпан</i>"
            await callback.message.edit_text(final_feedback)
            if q_index < len(test2_questions) - 1:
                await send_test2_question(user_id, q_index + 1)
            else:
                await finalize_test2(user_id)

async def finalize_test2(user_id: int):
    """Завершили Тест 2 → сразу выбор времени (без выбора рекрутёра)."""
    state = user_data[user_id]
    total_correct = sum(1 for q in state["t2_attempts"] if state["t2_attempts"][q]["is_correct"])
    total_score = calculate_score(state["t2_attempts"])
    pct = total_correct / max(1, len(test2_questions))
    rating_text = get_rating(total_score)

    await bot.send_message(
        user_id,
        await tpl(state.get("city_id"), "t2_result", correct=total_correct, score=total_score, rating=rating_text),
    )

    if pct < PASS_THRESHOLD:
        fail_text = await tpl(state.get("city_id"), "result_fail")
        await bot.send_message(user_id, fail_text)
        user_data.pop(user_id, None)
        return

    await _show_recruiter_menu(user_id)


# =============================
#  Выбор рекрутёра и слота
# =============================


# Start button callback
@dp.callback_query(F.data == "home:start")
async def cb_home_start(callback: CallbackQuery):
    await callback.answer()
    await begin_interview(callback.from_user.id)

@dp.callback_query(F.data.startswith("pick_rec:"))
async def pick_recruiter(callback: CallbackQuery):
    user_id = callback.from_user.id
    rid_s = callback.data.split(":", 1)[1]

    if rid_s == "__again__":
        state = user_data.get(user_id)
        tz_label = (state or {}).get("candidate_tz", DEFAULT_TZ)
        kb = await kb_recruiters(tz_label)
        text = await tpl(state.get("city_id") if state else None, "choose_recruiter")
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
    if not rec or not rec.active:
        await callback.answer("Рекрутёр не найден/не активен", show_alert=True)
        return

    state = user_data.get(user_id)
    if not state:
        await callback.answer("Сессия истекла. Введите /start", show_alert=True)
        return

    state["picked_recruiter_id"] = rid
    tz_label = state.get("candidate_tz", DEFAULT_TZ)
    slots_list = await get_free_slots_by_recruiter(rid)
    kb = await kb_slots_for_recruiter(rid, tz_label, slots=slots_list)
    text = _recruiter_header(rec.name, tz_label)
    if not slots_list:
        text = f"{text}\n\n{await tpl(state.get('city_id'), 'no_slots')}"
    try:
        await callback.message.edit_text(text, reply_markup=kb)
    except TelegramBadRequest:
        await callback.message.edit_text(text)
        await callback.message.edit_reply_markup(reply_markup=kb)
    await callback.answer()


@dp.callback_query(F.data.startswith("refresh_slots:"))
async def refresh_slots(callback: CallbackQuery):
    user_id = callback.from_user.id
    try:
        rid = int(callback.data.split(":", 1)[1])
    except (ValueError, IndexError):
        await callback.answer("Некорректный рекрутёр", show_alert=True)
        return

    state = user_data.get(user_id)
    if not state:
        await callback.answer("Сессия истекла. Введите /start", show_alert=True)
        return

    rec = await get_recruiter(rid)
    if not rec or not rec.active:
        await callback.answer("Рекрутёр недоступен", show_alert=True)
        return

    state["picked_recruiter_id"] = rid
    tz_label = state.get("candidate_tz", DEFAULT_TZ)
    slots_list = await get_free_slots_by_recruiter(rid)
    kb = await kb_slots_for_recruiter(rid, tz_label, slots=slots_list)
    text = _recruiter_header(rec.name, tz_label)
    if not slots_list:
        notice = await tpl(state.get("city_id"), "no_slots")
        text = f"{text}\n\n{notice}"
    try:
        await callback.message.edit_text(text, reply_markup=kb)
    except TelegramBadRequest:
        await callback.message.edit_text(text)
        await callback.message.edit_reply_markup(reply_markup=kb)
    await callback.answer("Обновлено")

@dp.callback_query(F.data.startswith("pick_slot:"))
async def pick_slot(callback: CallbackQuery):
    user_id = callback.from_user.id
    _, rid_s, slot_id_s = callback.data.split(":", 2)

    try:
        slot_id = int(slot_id_s)
    except ValueError:
        await callback.answer("Слот не найден", show_alert=True)
        return

    state = user_data.get(user_id)
    if not state:
        await callback.answer("Сессия истекла. Введите /start", show_alert=True)
        return

    # Резервируем слот в БД (PENDING)
    is_intro = (state.get("flow") == "intro")
    slot = await reserve_slot(
        slot_id,
        candidate_tg_id=user_id,
        candidate_fio=state.get("fio", str(user_id)),
        candidate_tz=state.get("candidate_tz", DEFAULT_TZ),
        candidate_city_id=state.get("city_id"),
        purpose="intro_day" if is_intro else "interview",
    )
    if not slot:
        # если сценарий intro — снова общий выбор времени; иначе — по рекрутёру
        text = await tpl(state.get("city_id"), "slot_taken")
        if is_intro:
            try:
                await callback.message.edit_text(text)
                await callback.message.edit_reply_markup(reply_markup=None)
            except TelegramBadRequest:
                pass
            await _show_recruiter_menu(user_id, notice=text)
        else:
            kb = await kb_slots_for_recruiter(int(rid_s), state.get("candidate_tz", DEFAULT_TZ))
            await callback.message.edit_text(text, reply_markup=kb)

        await callback.answer("Слот уже занят.")
        return

    # Отправим рекрутёру карточку с кнопками + вложим файл (анкета/отчёт), если есть
    rec = await get_recruiter(slot.recruiter_id)
    is_intro = (state.get("flow") == "intro")
    purpose = "ознакомительный день" if is_intro else "видео-интервью"

    caption = (
        f"📥 <b>Новый кандидат на {purpose}</b>\n"
        f"👤 {slot.candidate_fio or user_id}\n"
        f"📍 {state.get('city_name','—')}\n"
        f"🗓 {fmt_dt_local(slot.start_utc, (rec.tz if rec else DEFAULT_TZ) or DEFAULT_TZ)}\n"
    )

    attached = False
    attachment: Optional[BufferedInputFile] = None
    candidate_db_id = state.get("candidate_db_id")
    if not candidate_db_id:
        db_user = await candidate_services.get_user_by_telegram_id(user_id)
        if db_user:
            candidate_db_id = db_user.id
            state["candidate_db_id"] = candidate_db_id
    if candidate_db_id:
        survey_response = await candidate_services.load_survey_summary(candidate_db_id)
        if survey_response:
            try:
                payload = json.loads(survey_response.answers_json)
            except json.JSONDecodeError:
                payload = survey_response.answers_json
            created_at = survey_response.created_at or datetime.now(timezone.utc)
            attachment = _prepare_survey_attachment(
                state.get("fio") or str(user_id),
                payload,
                created_at,
                str(user_id),
            )

    if rec and rec.tg_chat_id and attachment is not None:
        try:
            await bot.send_document(
                rec.tg_chat_id,
                document=attachment,
                caption=caption,
                reply_markup=kb_approve(slot.id),
            )
            attached = True
        except Exception:
            pass

    if rec and rec.tg_chat_id and not attached:
        try:
            await bot.send_message(rec.tg_chat_id, caption, reply_markup=kb_approve(slot.id))
        except Exception:
            pass
    elif not rec or not rec.tg_chat_id:
        await bot.send_message(
            user_id,
            "ℹ️ Рекрутёр ещё не активировал DM с ботом (/iam_mih) или не указан tg_chat_id.\nЗаявка создана, но уведомление не отправлено.",
        )

    await callback.message.edit_text(await tpl(state.get("city_id"), "slot_sent"))
    await callback.answer()


# =============================
#  Согласование/отклонение рекрутёром
# =============================

@dp.callback_query(F.data.startswith("approve:"))
async def approve_slot_cb(callback: CallbackQuery):
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

    # Переводим в BOOKED
    slot = await approve_slot(slot_id)
    if not slot:
        await callback.answer("Не удалось согласовать.", show_alert=True)
        return

    # Уведомляем кандидата
    tz = slot.candidate_tz or DEFAULT_TZ
    labels = slot_local_labels(slot.start_utc, tz)
    template_key = "stage3_intro_invite" if getattr(slot, "purpose", "interview") == "intro_day" else "approved_msg"
    state = user_data.get(slot.candidate_tg_id, {})
    text = await tpl(
        getattr(slot, "candidate_city_id", None),
        template_key,
        candidate_fio=slot.candidate_fio or "",
        city_name=state.get("city_name") or "",
        dt=fmt_dt_local(slot.start_utc, tz),
        **labels,
    )
    await bot.send_message(slot.candidate_tg_id, text)

    # Ставим запрос подтверждения за 2 часа до встречи
    await schedule_confirm_prompt(slot.id, slot.candidate_tg_id)

    # Убираем клавиатуру у рекрутёра
    confirm_text = f"✅ Согласовано: {slot.candidate_fio or slot.candidate_tg_id} — {fmt_dt_local(slot.start_utc, DEFAULT_TZ)}"
    await safe_edit_text_or_caption(callback.message, confirm_text)
    await safe_remove_reply_markup(callback.message)

    await callback.answer("Согласовано")

@dp.callback_query(F.data.startswith("reject:"))
async def reject_slot_cb(callback: CallbackQuery):
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

    # Сообщаем кандидату
    await bot.send_message(slot.candidate_tg_id, "К сожалению, выбранное время недоступно.")

    # Показываем повторный выбор в зависимости от сценария
    st = user_data.get(slot.candidate_tg_id, {})
    if st.get("flow") == "intro":
        await _show_recruiter_menu(slot.candidate_tg_id)
    else:
        kb = await kb_recruiters(st.get("candidate_tz", DEFAULT_TZ))
        await bot.send_message(
            slot.candidate_tg_id,
            await tpl(getattr(slot, "candidate_city_id", None), "choose_recruiter"),
            reply_markup=kb,
        )

    # Снимаем клавиши у рекрутёра
    await safe_edit_text_or_caption(callback.message, "❌ Отказано. Слот освобождён.")
    await safe_remove_reply_markup(callback.message)

    await callback.answer("Отказано")


# =============================
#  Подтверждение явки кандидатом
# =============================

@dp.callback_query(F.data.startswith("att_yes:"))
async def att_yes(callback: CallbackQuery):
    slot_id = int(callback.data.split(":", 1)[1])
    slot = await get_slot(slot_id)
    if not slot or slot.status != SlotStatus.BOOKED:
        await callback.answer("Заявка не найдена или ещё не подтверждена рекрутёром.", show_alert=True)
        return

    # Отменим задачу confirm (если ещё ждёт)
    key: RemKey = (slot_id, callback.from_user.id)
    t = CONFIRM_TASKS.pop(key, None)
    if t and not t.done():
        t.cancel()

    # Отправим ссылку на телемост (из рекрутёра)
    rec = await get_recruiter(slot.recruiter_id)
    link = (rec.telemost_url if rec and rec.telemost_url else "https://telemost.yandex.ru/j/REPLACE_ME")
    tz = slot.candidate_tz or DEFAULT_TZ
    text = await tpl(getattr(slot, "candidate_city_id", None), "att_confirmed_link",
                     link=link, dt=fmt_dt_local(slot.start_utc, tz))
    await bot.send_message(slot.candidate_tg_id, text)

    # Планируем финальное напоминание за 1 час
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

@dp.callback_query(F.data.startswith("att_no:"))
async def att_no(callback: CallbackQuery):
    slot_id = int(callback.data.split(":", 1)[1])
    slot = await get_slot(slot_id)
    if not slot:
        await callback.answer("Заявка уже обработана.")
        await safe_remove_reply_markup(callback.message)
        return

    # Отменим задачи (подтверждение и фин. напоминание)
    key: RemKey = (slot_id, slot.candidate_tg_id)
    t = CONFIRM_TASKS.pop(key, None)
    if t and not t.done():
        t.cancel()
    t2 = REMINDERS.pop(key, None)
    if t2 and not t2.done():
        t2.cancel()

    # Освободим слот
    await reject_slot(slot_id)

    # Рекрутёру (если есть chat_id)
    rec = await get_recruiter(slot.recruiter_id)
    if rec and rec.tg_chat_id:
        try:
            await bot.send_message(
                rec.tg_chat_id,
                f"❌ Кандидат {slot.candidate_fio or slot.candidate_tg_id} отказался от слота "
                f"{fmt_dt_local(slot.start_utc, rec.tz or DEFAULT_TZ)}. Слот освобождён.",
            )
        except Exception:
            pass

    # Кандидату — повторный выбор времени (если «intro»), иначе — рекрутёры
    st = user_data.get(callback.from_user.id, {})
    await bot.send_message(callback.from_user.id, await tpl(getattr(slot, "candidate_city_id", None), "att_declined"))
    if st.get("flow") == "intro":
        await _show_recruiter_menu(callback.from_user.id)
    else:
        kb = await kb_recruiters(st.get("candidate_tz", DEFAULT_TZ))
        await bot.send_message(
            callback.from_user.id,
            await tpl(getattr(slot, "candidate_city_id", None), "choose_recruiter"),
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


# =============================
#  Прочие утилиты
# =============================

def get_rating(score: float) -> str:
    if score >= 6.5:
        return "⭐⭐⭐⭐⭐ "
    elif score >= 5:
        return "⭐⭐⭐⭐ "
    elif score >= 3.5:
        return "⭐⭐⭐ "
    elif score >= 2:
        return "⭐⭐ "
    else:
        return "⭐ (Не рекомендован)"


# =============================
#  Entrypoint
# =============================

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    me = await bot.get_me()
    logging.warning(f"BOOT: using bot id={me.id}, username=@{me.username}")
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped")
