"""Inline keyboard builders for the bot."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, List, Optional
from zoneinfo import ZoneInfo

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from backend.domain.repositories import (
    get_active_recruiters,
    get_active_recruiters_for_city,
    get_free_slots_by_recruiter,
    get_recruiters_free_slots_summary,
)

from .config import DEFAULT_TZ
from .security import sign_callback_data


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


async def kb_recruiters(
    candidate_tz: str = DEFAULT_TZ,
    *,
    city_id: Optional[int] = None,
) -> InlineKeyboardMarkup:
    if city_id is not None:
        recs = await get_active_recruiters_for_city(city_id)
    else:
        recs = await get_active_recruiters()
    if not recs:
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="✉️ Связаться вручную", callback_data="contact:manual")]
            ]
        )

    slots_summary = await get_recruiters_free_slots_summary((r.id for r in recs), city_id=city_id)

    seen_names: set[str] = set()
    rows: List[List[InlineKeyboardButton]] = []
    for recruiter in recs:
        key = recruiter.name.strip().lower()
        if key in seen_names:
            continue
        summary = slots_summary.get(recruiter.id)
        if not summary:
            continue

        seen_names.add(key)

        next_start_utc, total_slots = summary
        next_local = fmt_dt_local(next_start_utc, candidate_tz)
        label_suffix = f"{next_local} • {min(total_slots, 99)} сл."
        text = f"👤 {_short_name(recruiter.name)} — {label_suffix}"
        rows.append(
            [InlineKeyboardButton(text=text, callback_data=sign_callback_data(f"pick_rec:{recruiter.id}"))]
        )

    if not rows:
        return InlineKeyboardMarkup(inline_keyboard=[])

    return InlineKeyboardMarkup(inline_keyboard=rows)


async def kb_slots_for_recruiter(
    recruiter_id: int,
    candidate_tz: str,
    *,
    slots: Optional[List[Any]] = None,
    city_id: Optional[int] = None,
) -> InlineKeyboardMarkup:
    if slots is None:
        slots = await get_free_slots_by_recruiter(recruiter_id, city_id=city_id)
    if not slots:
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Обновить", callback_data=sign_callback_data(f"refresh_slots:{recruiter_id}"))],
                [InlineKeyboardButton(text="👤 К рекрутёрам", callback_data=sign_callback_data("pick_rec:__again__"))],
            ]
        )
    buttons = [
        InlineKeyboardButton(
            text=_slot_button_label(s.start_utc, s.duration_min, candidate_tz),
            callback_data=sign_callback_data(f"pick_slot:{recruiter_id}:{s.id}"),
        )
        for s in slots[:12]
    ]
    rows: List[List[InlineKeyboardButton]] = []
    for i in range(0, len(buttons), 2):
        rows.append(buttons[i : i + 2])
    rows.append(
        [
            InlineKeyboardButton(text="🔄 Обновить", callback_data=sign_callback_data(f"refresh_slots:{recruiter_id}")),
            InlineKeyboardButton(text="👤 Другой рекрутёр", callback_data=sign_callback_data("pick_rec:__again__")),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_approve(slot_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Согласовано", callback_data=f"approve:{slot_id}")],
            [
                InlineKeyboardButton(text="🔁 Перенести", callback_data=f"reschedule:{slot_id}"),
                InlineKeyboardButton(text="⛔️ Отказать", callback_data=f"reject:{slot_id}"),
            ],
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


def _slot_assignment_payload(action: str, assignment_id: int, token: str) -> str:
    # Compact JSON to stay within Telegram 64-byte callback limit.
    payload = {"a": action, "i": assignment_id, "t": token}
    return json.dumps(payload, separators=(",", ":"))


def kb_slot_assignment_offer(
    assignment_id: int,
    *,
    confirm_token: str,
    reschedule_token: str,
    decline_token: str | None = None,
) -> InlineKeyboardMarkup:
    rows: List[List[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(
                text="✅ Подтвердить",
                callback_data=_slot_assignment_payload("confirm", assignment_id, confirm_token),
            )
        ],
        [
            InlineKeyboardButton(
                text="🔁 Другое время",
                callback_data=_slot_assignment_payload("reschedule", assignment_id, reschedule_token),
            )
        ],
    ]
    if decline_token:
        rows.append(
            [
                InlineKeyboardButton(
                    text="⛔️ Отказ",
                    callback_data=_slot_assignment_payload("decline", assignment_id, decline_token),
                )
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


__all__ = [
    "create_keyboard",
    "fmt_dt_local",
    "kb_approve",
    "kb_attendance_confirm",
    "kb_recruiters",
    "kb_slots_for_recruiter",
    "kb_slot_assignment_offer",
    "kb_start",
]
