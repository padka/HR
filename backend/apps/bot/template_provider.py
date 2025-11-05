"""Database-backed message template provider with caching and metrics."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Tuple
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from backend.domain.repositories import get_message_template
from backend.apps.bot.templates import DEFAULT_TEMPLATES
from backend.apps.bot.metrics import record_template_fallback

logger = logging.getLogger(__name__)


@dataclass
class TemplateRecord:
    key: str
    locale: str
    channel: str
    version: int
    body: str


@dataclass
class RenderedTemplate:
    key: str
    version: int
    text: str


class TemplateProvider:
    """Resolve messaging templates from the database with short-term caching."""

    def __init__(self, *, cache_ttl: int = 60) -> None:
        self._cache_ttl = timedelta(seconds=max(1, cache_ttl))
        self._cache: Dict[
            Tuple[str, str, str], Tuple[Optional[TemplateRecord], datetime]
        ] = {}
        self._lock = asyncio.Lock()

    async def get(
        self,
        key: str,
        *,
        locale: str = "ru",
        channel: str = "tg",
    ) -> Optional[TemplateRecord]:
        cache_key = (key, locale, channel)
        now = datetime.now(timezone.utc)
        async with self._lock:
            cached = self._cache.get(cache_key)
            if cached and cached[1] > now:
                return cached[0]

        template = await get_message_template(key, locale=locale, channel=channel)
        if template is None:
            await record_template_fallback(key)
            record = _fallback_template_record(key, locale, channel)
            if record is None:
                logger.warning(
                    "Template lookup failed for key=%s locale=%s channel=%s (no fallback)",
                    key,
                    locale,
                    channel,
                )
                async with self._lock:
                    self._cache[cache_key] = (None, now + self._cache_ttl)
                return None
            logger.warning(
                "Template lookup failed for key=%s locale=%s channel=%s; using fallback text",
                key,
                locale,
                channel,
            )
            async with self._lock:
                self._cache[cache_key] = (record, now + self._cache_ttl)
            return record

        record = TemplateRecord(
            key=template.key,
            locale=template.locale,
            channel=template.channel,
            version=template.version,
            body=template.body_md,
        )
        async with self._lock:
            self._cache[cache_key] = (record, now + self._cache_ttl)
        return record

    async def render(
        self,
        key: str,
        context: Dict[str, object],
        *,
        locale: str = "ru",
        channel: str = "tg",
    ) -> Optional[RenderedTemplate]:
        template = await self.get(key, locale=locale, channel=channel)
        if template is None:
            return None
        try:
            text = template.body.format_map(_SafeDict(context))
        except Exception:
            logger.exception("Failed to format template %s", key)
            text = template.body
        return RenderedTemplate(key=template.key, version=template.version, text=text)

    async def invalidate(
        self,
        *,
        key: Optional[str] = None,
        locale: str = "ru",
        channel: str = "tg",
    ) -> None:
        async with self._lock:
            if key is None:
                self._cache.clear()
                return
            cache_key = (key, locale, channel)
            self._cache.pop(cache_key, None)

    @staticmethod
    def format_local_dt(dt_utc: datetime, tz_name: Optional[str]) -> str:
        zone = _safe_zone(tz_name)
        return dt_utc.astimezone(zone).strftime("%d.%m %H:%M (по вашему времени)")

    @staticmethod
    def format_short_dt(dt_utc: datetime, tz_name: Optional[str]) -> str:
        zone = _safe_zone(tz_name)
        return dt_utc.astimezone(zone).strftime("%d.%m %H:%M")


class _SafeDict(dict):
    """Formatting helper that returns placeholders unchanged when missing."""

    def __missing__(self, key: str) -> str:  # pragma: no cover - defensive fallback
        return "{" + key + "}"


def _safe_zone(name: Optional[str]) -> ZoneInfo:
    if not name:
        return ZoneInfo("UTC")
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError:
        logger.warning("Unknown timezone '%s', falling back to UTC", name)
        return ZoneInfo("UTC")


__all__ = [
    "TemplateProvider",
    "TemplateRecord",
    "RenderedTemplate",
]


_GENERIC_FALLBACK_TEXT = (
    "Статус вашей заявки обновлён. Свяжитесь с рекрутером, если остались вопросы."
)


_DEFAULT_FALLBACK_MESSAGES: Dict[Tuple[str, str, str], str] = {
    ("interview_confirmed_candidate", "ru", "tg"): (
        "{candidate_name} 👋\n"
        "Поздравляем — вы шаг ближе к команде SMART SERVICE!\n\n"
        "🗓 {dt_local}\n"
        "💬 Формат: видеочат | 15–20 мин\n\n"
        "⚡ Подготовьтесь заранее:\n"
        "• стабильный интернет\n"
        "• 2–3 вопроса о вакансии\n"
        "• тихое место для разговора\n\n"
        "🔔 Поставьте напоминание на телефон."
    ),
    ("candidate_reschedule_prompt", "ru", "tg"): (
        "🔁 Мы освободили ваше бронирование.\n"
        "Пожалуйста, выберите новое время в расписании — нажмите «Выбрать слот»."
    ),
    ("candidate_rejection", "ru", "tg"): DEFAULT_TEMPLATES.get(
        "result_fail",
        "Спасибо за интерес к SMART SERVICE. На текущем этапе мы не можем продолжить процесс, "
        "но сохраним контакты и вернёмся при появлении подходящих возможностей.",
    ),
    ("recruiter_candidate_confirmed_notice", "ru", "tg"): (
        "✅ Кандидат {candidate_name} подтвердил участие.\n"
        "📅 {dt_local}\n"
        "💬 Ответственный рекрутёр: {recruiter_name}"
    ),
    ("confirm_6h", "ru", "tg"): DEFAULT_TEMPLATES.get(
        "confirm_6h",
        "⏰ Собеседование сегодня в {slot_datetime_local}. Подтвердите участие, пожалуйста.",
    ),
    ("confirm_2h", "ru", "tg"): DEFAULT_TEMPLATES.get(
        "confirm_2h",
        "⏰ Напоминание: собеседование через 2 часа — {dt_local}. Подтвердите участие, пожалуйста.",
    ),
    ("reminder_24h", "ru", "tg"): DEFAULT_TEMPLATES.get(
        "reminder_24h",
        "Напоминаем: собеседование назначено на {slot_datetime_local}. "
        "Отметьте время и убедитесь, что сможете подключиться вовремя.",
    ),
    ("interview_reminder_2h", "ru", "tg"): (
        "Напоминаем: интервью начнётся через 2 часа.\n\n"
        "🗓 {dt_local}\n"
        "🔗 Ссылка на встречу: {join_link}\n\n"
        "Если планы меняются — сообщите нам, и мы подберём другое время."
    ),
    ("no_slots_fallback", "ru", "tg"): (
        "Свободных слотов пока нет. Оставьте сообщение рекрутёру — мы вернёмся с предложением времени."
    ),
}


def _fallback_template_record(key: str, locale: str, channel: str) -> Optional[TemplateRecord]:
    candidates = [
        (key, locale, channel),
        (key, "ru", channel),
        (key, locale, "tg"),
        (key, "ru", "tg"),
    ]
    for candidate in candidates:
        body = _DEFAULT_FALLBACK_MESSAGES.get(candidate)
        if body:
            return TemplateRecord(key=key, locale=locale, channel=channel, version=0, body=body)
    if channel == "tg":
        return TemplateRecord(
            key=key,
            locale=locale,
            channel=channel,
            version=0,
            body=_GENERIC_FALLBACK_TEXT,
        )
    return None
