"""Utility helpers for working with known recruiter timezones."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Sequence

from zoneinfo import ZoneInfo

DEFAULT_TZ = "Europe/Moscow"


@dataclass(frozen=True)
class TimezoneDescriptor:
    tz: str
    region: str


# Curated list ordered from west to east to cover common recruiter regions.
KNOWN_TIMEZONES: Sequence[TimezoneDescriptor] = (
    TimezoneDescriptor("Europe/Kaliningrad", "Калининград"),
    TimezoneDescriptor("Europe/Moscow", "Москва"),
    TimezoneDescriptor("Europe/Samara", "Самара"),
    TimezoneDescriptor("Asia/Yekaterinburg", "Екатеринбург"),
    TimezoneDescriptor("Asia/Omsk", "Омск"),
    TimezoneDescriptor("Asia/Novosibirsk", "Новосибирск"),
    TimezoneDescriptor("Asia/Barnaul", "Барнаул"),
    TimezoneDescriptor("Asia/Krasnoyarsk", "Красноярск"),
    TimezoneDescriptor("Asia/Irkutsk", "Иркутск"),
    TimezoneDescriptor("Asia/Yakutsk", "Якутск"),
    TimezoneDescriptor("Asia/Vladivostok", "Владивосток"),
    TimezoneDescriptor("Asia/Magadan", "Магадан"),
    TimezoneDescriptor("Asia/Sakhalin", "Южно-Сахалинск"),
    TimezoneDescriptor("Asia/Srednekolymsk", "Среднеколымск"),
    TimezoneDescriptor("Asia/Anadyr", "Анадырь"),
    TimezoneDescriptor("Asia/Kamchatka", "Петропавловск-Камчатский"),
    TimezoneDescriptor("Asia/Almaty", "Алматы"),
    TimezoneDescriptor("Asia/Bishkek", "Бишкек"),
    TimezoneDescriptor("Asia/Tashkent", "Ташкент"),
)


_REGION_MAP: Dict[str, str] = {item.tz: item.region for item in KNOWN_TIMEZONES}


def _tzinfo(tz: str) -> ZoneInfo:
    try:
        return ZoneInfo(tz)
    except Exception:
        return ZoneInfo(DEFAULT_TZ)


def _offset_label(tz: str) -> str:
    now_utc = datetime.now(timezone.utc)
    try:
        offset = now_utc.astimezone(_tzinfo(tz)).utcoffset()
    except Exception:
        offset = None
    if not offset:
        return "+00"
    total_minutes = int(offset.total_seconds() // 60)
    sign = "+" if total_minutes >= 0 else "-"
    minutes_total = abs(total_minutes)
    hours = minutes_total // 60
    minutes = minutes_total % 60
    if minutes:
        return f"{sign}{hours:02d}:{minutes:02d}"
    return f"{sign}{hours:02d}"


def tz_region_name(tz: str) -> str:
    tz_key = (tz or "").strip() or DEFAULT_TZ
    return _REGION_MAP.get(tz_key, tz_key)


def tz_display(tz: str) -> str:
    tz_key = (tz or "").strip() or DEFAULT_TZ
    region = tz_region_name(tz_key)
    offset = _offset_label(tz_key)
    return f"{region} (UTC{offset})"


def timezone_options(include_extra: Iterable[str] | None = None) -> List[Dict[str, str]]:
    """Return list of recruiter timezone options with friendly labels."""

    seen = set()
    options: List[Dict[str, str]] = []

    def _append(tz: str) -> None:
        if tz in seen:
            return
        seen.add(tz)
        options.append(
            {
                "value": tz,
                "region": tz_region_name(tz),
                "offset": _offset_label(tz),
                "label": tz_display(tz),
            }
        )

    for descriptor in KNOWN_TIMEZONES:
        _append(descriptor.tz)

    if include_extra:
        for tz in include_extra:
            if tz:
                _append(tz)

    return options


__all__ = [
    "DEFAULT_TZ",
    "KNOWN_TIMEZONES",
    "tz_display",
    "tz_region_name",
    "timezone_options",
]
