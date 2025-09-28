"""Inline keyboard builders for the bot."""

from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional
from zoneinfo import ZoneInfo

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from backend.domain.repositories import get_active_recruiters, get_free_slots_by_recruiter

from .config import DEFAULT_TZ


def _safe_zone(tz: Optional[str]) -> ZoneInfo:
    try:
        return ZoneInfo(tz or DEFAULT_TZ)
    except Exception:
        return ZoneInfo(DEFAULT_TZ)


def fmt_dt_local(dt_utc: datetime, tz: str) -> str:
    return dt_utc.astimezone(_safe_zone(tz)).strftime("%d.%m %H:%M")


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


def _slot_button_label(
    dt_utc: datetime, duration_min: int, tz: str, recruiter_name: Optional[str] = None
) -> str:
    local_dt = dt_utc.astimezone(_safe_zone(tz))
    label = local_dt.strftime("%d %b • %H:%M")
    label += f" • {duration_min}м"
    if recruiter_name:
        label += f" • {recruiter_name}"
    return label


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
        rows.append(
            [InlineKeyboardButton(text=text, callback_data=f"pick_rec:{recruiter.id}")]
        )

    if not rows:
        no_rows = [
            [InlineKeyboardButton(text="Временно нет свободных рекрутёров", callback_data="noop")]
        ]
        return InlineKeyboardMarkup(inline_keyboard=no_rows)

    return InlineKeyboardMarkup(inline_keyboard=rows)


async def kb_slots_for_recruiter(
    recruiter_id: int, candidate_tz: str, *, slots: Optional[List[Any]] = None
) -> InlineKeyboardMarkup:
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
        rows.append(buttons[i : i + 2])
    rows.append(
        [
            InlineKeyboardButton(text="🔄 Обновить", callback_data=f"refresh_slots:{recruiter_id}"),
            InlineKeyboardButton(text="👤 Другой рекрутёр", callback_data="pick_rec:__again__"),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_approve(slot_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Согласовано", callback_data=f"approve:{slot_id}")],
            [InlineKeyboardButton(text="❌ Отказать", callback_data=f"reject:{slot_id}")],
        ]
    )


def kb_attendance_confirm(slot_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Подтверждаю", callback_data=f"att_yes:{slot_id}"),
                InlineKeyboardButton(text="❌ Не смогу", callback_data=f"att_no:{slot_id}"),
            ]
        ]
    )


__all__ = [
    "create_keyboard",
    "fmt_dt_local",
    "kb_approve",
    "kb_attendance_confirm",
    "kb_recruiters",
    "kb_slots_for_recruiter",
    "kb_start",
]
