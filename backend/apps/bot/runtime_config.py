"""Persistent runtime configuration used by bot workers and admin UI."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Dict, Tuple

from sqlalchemy import select

from backend.core.db import async_session
from backend.domain.models import BotRuntimeConfig

REMINDER_POLICY_KEY = "reminder_policy"

DEFAULT_REMINDER_POLICY: Dict[str, Any] = {
    "interview": {
        "confirm_6h": {"enabled": True, "offset_hours": 6.0},
        "confirm_3h": {"enabled": True, "offset_hours": 3.0},
        "confirm_2h": {"enabled": True, "offset_hours": 2.0},
    },
    "intro_day": {
        "intro_remind_3h": {"enabled": True, "offset_hours": 3.0},
    },
    "min_time_before_immediate_hours": 2.0,
}

_INTERVIEW_KINDS = ("confirm_6h", "confirm_3h", "confirm_2h")
_INTRO_KINDS = ("intro_remind_3h",)


def _normalize_kind_config(raw: Any, *, default_enabled: bool, default_offset: float) -> Dict[str, Any]:
    if not isinstance(raw, dict):
        return {"enabled": default_enabled, "offset_hours": default_offset}
    enabled = bool(raw.get("enabled", default_enabled))
    offset_raw = raw.get("offset_hours", default_offset)
    try:
        offset = float(offset_raw)
    except (TypeError, ValueError):
        offset = float(default_offset)
    # Keep offsets sane to avoid pathological schedules.
    offset = min(max(offset, 0.25), 72.0)
    return {"enabled": enabled, "offset_hours": round(offset, 2)}


def normalize_reminder_policy(raw: Any) -> Dict[str, Any]:
    default = deepcopy(DEFAULT_REMINDER_POLICY)
    data = raw if isinstance(raw, dict) else {}

    interview_cfg = data.get("interview", {}) if isinstance(data.get("interview"), dict) else {}
    intro_cfg = data.get("intro_day", {}) if isinstance(data.get("intro_day"), dict) else {}

    normalized: Dict[str, Any] = {
        "interview": {},
        "intro_day": {},
    }
    for kind in _INTERVIEW_KINDS:
        defaults = default["interview"][kind]
        normalized["interview"][kind] = _normalize_kind_config(
            interview_cfg.get(kind),
            default_enabled=bool(defaults["enabled"]),
            default_offset=float(defaults["offset_hours"]),
        )
    for kind in _INTRO_KINDS:
        defaults = default["intro_day"][kind]
        normalized["intro_day"][kind] = _normalize_kind_config(
            intro_cfg.get(kind),
            default_enabled=bool(defaults["enabled"]),
            default_offset=float(defaults["offset_hours"]),
        )

    immediate_raw = data.get(
        "min_time_before_immediate_hours",
        default["min_time_before_immediate_hours"],
    )
    try:
        immediate_hours = float(immediate_raw)
    except (TypeError, ValueError):
        immediate_hours = float(default["min_time_before_immediate_hours"])
    immediate_hours = min(max(immediate_hours, 0.0), 24.0)
    normalized["min_time_before_immediate_hours"] = round(immediate_hours, 2)
    return normalized


def _purpose_bucket(purpose: str) -> str:
    return "intro_day" if (purpose or "").strip().lower() == "intro_day" else "interview"


def is_reminder_kind_enabled(policy: Dict[str, Any], *, purpose: str, kind: str) -> bool:
    normalized = normalize_reminder_policy(policy)
    bucket = _purpose_bucket(purpose)
    kind_cfg = normalized.get(bucket, {}).get(kind)
    if not isinstance(kind_cfg, dict):
        return False
    return bool(kind_cfg.get("enabled", False))


def reminder_kind_offset_hours(policy: Dict[str, Any], *, purpose: str, kind: str) -> float:
    normalized = normalize_reminder_policy(policy)
    bucket = _purpose_bucket(purpose)
    kind_cfg = normalized.get(bucket, {}).get(kind)
    if not isinstance(kind_cfg, dict):
        return 0.0
    try:
        return float(kind_cfg.get("offset_hours", 0.0))
    except (TypeError, ValueError):
        return 0.0


def min_time_before_immediate_hours(policy: Dict[str, Any]) -> float:
    normalized = normalize_reminder_policy(policy)
    try:
        return float(normalized.get("min_time_before_immediate_hours", 2.0))
    except (TypeError, ValueError):
        return 2.0


async def get_reminder_policy_config() -> Tuple[Dict[str, Any], datetime | None]:
    async with async_session() as session:
        row = await session.scalar(
            select(BotRuntimeConfig).where(BotRuntimeConfig.key == REMINDER_POLICY_KEY)
        )
        if row is None:
            return deepcopy(DEFAULT_REMINDER_POLICY), None

        normalized = normalize_reminder_policy(row.value_json)
        if normalized != row.value_json:
            row.value_json = normalized
            row.updated_at = datetime.now(timezone.utc)
            await session.commit()
            await session.refresh(row)
        return normalized, row.updated_at


async def save_reminder_policy_config(raw: Any) -> Tuple[Dict[str, Any], datetime]:
    normalized = normalize_reminder_policy(raw)
    now = datetime.now(timezone.utc)
    async with async_session() as session:
        row = await session.scalar(
            select(BotRuntimeConfig).where(BotRuntimeConfig.key == REMINDER_POLICY_KEY)
        )
        if row is None:
            row = BotRuntimeConfig(
                key=REMINDER_POLICY_KEY,
                value_json=normalized,
                updated_at=now,
            )
            session.add(row)
        else:
            row.value_json = normalized
            row.updated_at = now
        await session.commit()
        await session.refresh(row)
        return normalize_reminder_policy(row.value_json), row.updated_at


__all__ = [
    "DEFAULT_REMINDER_POLICY",
    "get_reminder_policy_config",
    "is_reminder_kind_enabled",
    "min_time_before_immediate_hours",
    "normalize_reminder_policy",
    "reminder_kind_offset_hours",
    "save_reminder_policy_config",
]
