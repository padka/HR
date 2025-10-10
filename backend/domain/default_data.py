"""Shared default datasets used for seeding and migrations."""
from __future__ import annotations

import os
from typing import List, Mapping, Sequence

# Default cities available for fresh installations.  The dataset intentionally
# mirrors what used to live inside the historical migrations so it can be
# reused both by runtime seeders and legacy migration scripts.
DEFAULT_CITIES: Sequence[Mapping[str, str]] = (
    {"name": "Москва", "tz": "Europe/Moscow"},
    {"name": "Санкт-Петербург", "tz": "Europe/Moscow"},
    {"name": "Новосибирск", "tz": "Asia/Novosibirsk"},
    {"name": "Екатеринбург", "tz": "Asia/Yekaterinburg"},
)

# Default recruiters that can be optionally pre-populated for demo purposes.
_DEFAULT_RECRUITERS: Sequence[Mapping[str, object]] = (
    {
        "name": "Михаил Шеншин",
        "tz": "Europe/Moscow",
        "telemost_url": "https://telemost.yandex.ru/j/SMART_ONBOARDING",
        "active": True,
    },
    {
        "name": "Юлия Начауридзе",
        "tz": "Europe/Moscow",
        "telemost_url": "https://telemost.yandex.ru/j/SMART_RECRUIT",
        "active": True,
    },
)

_TRUE_VALUES = {"1", "true", "yes", "on"}


def should_seed_default_recruiters(env: Mapping[str, str] | None = None) -> bool:
    """Return whether demo recruiters should be seeded."""

    source = env or os.environ
    raw = source.get("SEED_DEFAULT_RECRUITERS", "0")
    return raw.strip().lower() in _TRUE_VALUES


def default_recruiters(env: Mapping[str, str] | None = None) -> List[Mapping[str, object]]:
    """Return recruiter payloads that should be inserted."""

    if not should_seed_default_recruiters(env):
        return []
    return [dict(item) for item in _DEFAULT_RECRUITERS]


__all__ = [
    "DEFAULT_CITIES",
    "default_recruiters",
    "should_seed_default_recruiters",
]
