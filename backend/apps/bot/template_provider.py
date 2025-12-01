"""Database-backed message template provider with caching and metrics."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Tuple
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from jinja2 import TemplateNotFound

from backend.domain.repositories import get_message_template
from backend.apps.bot.templates import DEFAULT_TEMPLATES
from backend.apps.bot.metrics import record_template_fallback
from backend.apps.bot.jinja_renderer import get_renderer as get_jinja_renderer

logger = logging.getLogger(__name__)


@dataclass
class TemplateRecord:
    """Message template record from database.

    Attributes:
        key: Template identifier (e.g., "interview_confirmed")
        locale: Language code (e.g., "ru", "en")
        channel: Delivery channel (e.g., "tg" for Telegram)
        version: Template version number
        city_id: Optional city-specific template
        body: Template content (interpretation depends on use_jinja flag)
        use_jinja: If True, body contains a Jinja2 template path (e.g., "messages/interview_confirmed")
                   If False, body contains a Python format string (e.g., "Hello {name}")

    Important: When use_jinja=True, the body field MUST contain a file path relative
    to the templates_jinja/ directory, NOT inline template content. Inline Jinja2
    templates are not supported - use use_jinja=False with .format() syntax instead.
    """

    key: str
    locale: str
    channel: str
    version: int
    city_id: Optional[int]
    body: str
    use_jinja: bool = False


@dataclass
class RenderedTemplate:
    key: str
    version: int
    city_id: Optional[int]
    text: str


class TemplateResolutionError(RuntimeError):
    """Raised when a template cannot be resolved even after fallback attempts."""

    def __init__(self, key: str, *, locale: str, channel: str, city_id: Optional[int]) -> None:
        self.key = key
        self.locale = locale
        self.channel = channel
        self.city_id = city_id
        city_part = f" для города #{city_id}" if city_id is not None else ""
        message = (
            f"Активный шаблон '{key}'{city_part} не найден для канала '{channel}' (locale={locale}). "
            "Добавьте городской или общий шаблон в разделе «Шаблоны сообщений»."
        )
        super().__init__(message)


class TemplateProvider:
    """Resolve messaging templates from the database with short-term caching."""

    def __init__(self, *, cache_ttl: int = 60) -> None:
        self._cache_ttl = timedelta(seconds=max(1, cache_ttl))
        self._cache: Dict[
            Tuple[str, str, str, Optional[int]], Tuple[Optional[TemplateRecord], datetime]
        ] = {}
        self._lock = asyncio.Lock()

    async def get(
        self,
        key: str,
        *,
        locale: str = "ru",
        channel: str = "tg",
        city_id: Optional[int] = None,
        strict: bool = False,
    ) -> Optional[TemplateRecord]:
        cache_key = (key, locale, channel, city_id)
        now = datetime.now(timezone.utc)
        async with self._lock:
            cached = self._cache.get(cache_key)
            if cached and cached[1] > now:
                return cached[0]

        template = await get_message_template(key, locale=locale, channel=channel, city_id=city_id)
        if template is None:
            await record_template_fallback(key)
            record = _fallback_template_record(key, locale, channel, city_id=city_id, strict=strict)
            if record is None and strict:
                raise TemplateResolutionError(key, locale=locale, channel=channel, city_id=city_id)
            async with self._lock:
                self._cache[cache_key] = (record, now + self._cache_ttl)
            return record

        record = TemplateRecord(
            key=template.key,
            locale=template.locale,
            channel=template.channel,
            version=template.version,
            city_id=getattr(template, "city_id", None),
            body=template.body_md,
            use_jinja=getattr(template, "use_jinja", False),
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
        city_id: Optional[int] = None,
        strict: bool = False,
    ) -> Optional[RenderedTemplate]:
        template = await self.get(key, locale=locale, channel=channel, city_id=city_id, strict=strict)
        if template is None:
            return None

        # Choose renderer based on use_jinja flag
        if template.use_jinja:
            # Use Jinja2 renderer for modern file-based templates
            # When use_jinja=True, template.body MUST contain a template path
            # (e.g., "messages/interview_confirmed"), not inline template content.
            # Inline Jinja2 templates are not yet supported - for that use case,
            # keep use_jinja=False and the template will use .format() instead.
            try:
                jinja_renderer = get_jinja_renderer()
                # Render file-based template from path in body field
                text = jinja_renderer.render(template.body, context)
            except TemplateNotFound:
                logger.exception(
                    "Jinja2 template file not found: %s (key=%s). "
                    "Check that template exists in templates_jinja/ directory.",
                    template.body,
                    key,
                )
                # Fallback: treat as format string
                text = template.body.format_map(_SafeDict(context))
            except Exception:
                logger.exception("Failed to render Jinja2 template %s (path=%s)", key, template.body)
                text = template.body
        else:
            # Use legacy .format() renderer
            try:
                text = template.body.format_map(_SafeDict(context))
            except Exception:
                logger.exception("Failed to format template %s", key)
                text = template.body

        return RenderedTemplate(
            key=template.key,
            version=template.version,
            city_id=template.city_id,
            text=text,
        )

    async def invalidate(
        self,
        *,
        key: Optional[str] = None,
        locale: str = "ru",
        channel: str = "tg",
        city_id: Optional[int] = None,
    ) -> None:
        async with self._lock:
            if key is None:
                self._cache.clear()
                return
            targets = []
            for cache_key in list(self._cache.keys()):
                same_key = cache_key[0] == key and cache_key[1] == locale and cache_key[2] == channel
                if not same_key:
                    continue
                if city_id is None or cache_key[3] == city_id:
                    targets.append(cache_key)
            for cache_key in targets:
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
    "TemplateResolutionError",
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
    ("intro_day_reminder", "ru", "tg"): DEFAULT_TEMPLATES.get(
        "intro_day_reminder",
        "📅 Ознакомительный день через 3 часа ({slot_datetime_local}). Подтвердите участие кнопкой ниже.",
    ),
    ("intro_day_invitation", "ru", "tg"): DEFAULT_TEMPLATES.get(
        "intro_day_invitation",
        "Вы успешно прошли видеоинтервью в компанию <b>SMART</b>! 🎉\n\n"
        "Встреча назначена на <b>{slot_datetime_local}</b>.\n"
        "📍 Адрес: <b>{intro_address}</b>\n\n"
        "Пожалуйста, приходите в презентабельном виде и с отличным настроением — это не собеседование, "
        "а <b>ознакомительный день</b> (~2 часа).\n\n"
        "✨ <b>Прежде всего:</b>\n"
        "• проявите себя — заинтересованность и активность важны;\n"
        "• используйте шанс задать вопросы и почувствовать команду.\n\n"
        "💼 <b>Контакт руководителя региона:</b>\n"
        "{intro_contact}\n\n"
        "Нажмите кнопку ниже, чтобы подтвердить участие. Если планы меняются — сообщите заранее.\n\n"
        "С уважением,\n"
        "Шеншин Михаил Алексеевич\n"
        "<b>Руководитель HR-департамента SMART</b>",
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


def _fallback_template_record(
    key: str, locale: str, channel: str, *, city_id: Optional[int], strict: bool
) -> Optional[TemplateRecord]:
    if strict:
        return None
    candidates = [
        (key, locale, channel),
        (key, "ru", channel),
        (key, locale, "tg"),
        (key, "ru", "tg"),
    ]
    for candidate in candidates:
        body = _DEFAULT_FALLBACK_MESSAGES.get(candidate)
        if body:
            return TemplateRecord(
                key=key, locale=locale, channel=channel, version=0, city_id=city_id, body=body
            )
    if channel == "tg":
        return TemplateRecord(
            key=key,
            locale=locale,
            channel=channel,
            version=0,
            city_id=city_id,
            body=_GENERIC_FALLBACK_TEXT,
        )
    return None
