from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Dict, List, Optional, Sequence, Tuple, Iterable, Set

from sqlalchemy import Select, select, update
from sqlalchemy.exc import IntegrityError

from backend.core.db import async_session
from backend.core.settings import get_settings
from backend.domain.models import City, MessageTemplate, MessageTemplateHistory

logger = logging.getLogger(__name__)


ALLOWED_CHANNELS: Sequence[str] = ("tg", "email", "whatsapp")
DEFAULT_CHANNEL = "tg"
DEFAULT_LOCALE = "ru"
DEFAULT_VERSION = 1


REQUIRED_TG_TEMPLATE_KEYS: Sequence[str] = (
    "interview_confirmed_candidate",
    "candidate_reschedule_prompt",
    "candidate_rejection",
    "recruiter_candidate_confirmed_notice",
    "confirm_6h",
    "confirm_2h",
)


KNOWN_TEMPLATE_HINTS: Dict[str, str] = {
    "interview_confirmed_candidate": "Сообщение кандидату после подтверждения слота рекрутёром.",
    "candidate_reschedule_prompt": "Уведомление кандидату, когда слот освобождён и требуется выбрать новое время.",
    "candidate_rejection": "Итоговое сообщение при отказе кандидату.",
    "recruiter_candidate_confirmed_notice": "Уведомление рекрутёру, когда кандидат подтвердил участие.",
    "confirm_6h": "Напоминание кандидату за 6 часов до встречи с кнопками подтверждения.",
    "confirm_2h": "Напоминание/подтверждение за 2 часа до встречи.",
    "interview_invite_details": "Приглашение на собеседование с деталями встречи и подготовкой.",
    "interview_remind_confirm_2h": "Напоминание за 2 часа до интервью с подтверждением/переносом и ссылкой.",
    "intro_day_invite_city": "Приглашение на ознакомительный день с адресом офиса для выбранного города.",
    "intro_day_remind_2h": "Напоминание за 2 часа до ознакомительного дня с подтверждением/переносом.",
}

AVAILABLE_VARIABLES: Sequence[Dict[str, str]] = (
    {"name": "candidate_name", "label": "Имя кандидата"},
    {"name": "candidate_fio", "label": "ФИО кандидата"},
    {"name": "candidate_city", "label": "Город кандидата"},
    {"name": "city_name", "label": "Название города"},
    {"name": "dt_local", "label": "Дата и время (локально)"},
    {"name": "slot_date_local", "label": "Дата слота"},
    {"name": "slot_time_local", "label": "Время слота"},
    {"name": "slot_datetime_local", "label": "Дата и время"},
    {"name": "slot_day_name_local", "label": "День недели"},
    {"name": "recruiter_name", "label": "Имя рекрутёра"},
    {"name": "join_link", "label": "Ссылка на видеочат"},
    {"name": "intro_address", "label": "Адрес ОД"},
    {"name": "intro_contact", "label": "Контакт для ОД"},
    {"name": "address", "label": "Адрес (синоним)"},
    {"name": "recruiter_contact", "label": "Контакт рекрутёра"},
    {"name": "city_address", "label": "Адрес города/офиса"},
)

MOCK_CONTEXT: Dict[str, str] = {
    "candidate_name": "Иван",
    "candidate_fio": "Иван Петров",
    "candidate_city": "Москва",
    "city_name": "Москва",
    "dt_local": "12.08 10:00 (МСК)",
    "slot_date_local": "12.08",
    "slot_time_local": "10:00",
    "slot_datetime_local": "12.08 10:00",
    "slot_day_name_local": "понедельник",
    "recruiter_name": "Анна Смарт",
    "join_link": "https://yandex.ru/telemost/example",
    "intro_address": "ул. Пример, 1",
    "intro_contact": "+7 900 123-45-67",
    "address": "ул. Пример, 1",
    "recruiter_contact": "+7 900 123-45-67",
    "city_address": "ул. Пример, 1",
}


@dataclass(frozen=True)
class MessageTemplateSummary:
    id: int
    key: str
    locale: str
    channel: str
    city_id: Optional[int]
    city_name: str
    version: int
    is_active: bool
    updated_by: Optional[str]
    created_at: datetime
    updated_at: datetime
    length: int
    preview: str
    body: str
    stage: str


def _infer_stage(key: str) -> str:
    lk = (key or "").lower()
    if "intro" in lk:
        return "intro"
    if "interview" in lk:
        return "interview"
    if "remind" in lk or "confirm" in lk:
        return "reminder"
    if "resched" in lk:
        return "interview"
    return "other"


def _preview_text(text: str, limit: int = 140) -> str:
    cleaned = " ".join((text or "").split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1].rstrip() + "…"


def _coverage_gaps(
    active_templates: Sequence[MessageTemplate],
    city_map: Dict[Optional[int], str],
) -> List[Dict[str, object]]:
    """Return list of keys lacking city-specific or default templates."""

    available_city_ids: List[int] = [cid for cid in city_map.keys() if cid is not None]  # type: ignore[arg-type]
    active_lookup: Set[Tuple[str, Optional[int]]] = {
        (tpl.key, tpl.city_id) for tpl in active_templates if tpl.is_active
    }
    keys = sorted({tpl.key for tpl in active_templates})
    coverage: List[Dict[str, object]] = []
    for key in keys:
        default_missing = (key, None) not in active_lookup
        missing_cities = []
        for cid in available_city_ids:
            if (key, cid) in active_lookup:
                continue
            if not default_missing:
                # Default template covers the city, don't mark as missing override.
                continue
            missing_cities.append({"id": cid, "name": city_map.get(cid) or f"Город #{cid}"})
        if default_missing or missing_cities:
            coverage.append(
                {
                    "key": key,
                    "missing_default": default_missing,
                    "missing_cities": missing_cities,
                }
            )
    return coverage


async def list_message_templates(
    *,
    city: Optional[str] = None,
    key_query: Optional[str] = None,
    channel: Optional[str] = None,
    status: Optional[str] = None,
) -> Dict[str, object]:
    city_filter_value: Optional[int] = None
    default_only = False
    if city:
        if city == "default":
            default_only = True
        else:
            try:
                city_filter_value = int(city)
            except (TypeError, ValueError):
                city_filter_value = None

    async with async_session() as session:
        city_map: Dict[Optional[int], str] = {None: "Общий"}
        city_rows = await session.execute(
            select(City.id, City.name).where(City.active.is_(True)).order_by(City.name.asc())
        )
        for cid, name in city_rows:
            city_map[cid] = name

        filters = []
        if default_only:
            filters.append(MessageTemplate.city_id.is_(None))
        elif city_filter_value is not None:
            filters.append(MessageTemplate.city_id == city_filter_value)
        if key_query:
            filters.append(MessageTemplate.key.ilike(f"%{key_query.strip()}%"))
        if channel:
            filters.append(MessageTemplate.channel == channel)
        if status == "active":
            filters.append(MessageTemplate.is_active.is_(True))
        elif status == "draft":
            filters.append(MessageTemplate.is_active.is_(False))

        base_query: Select[Tuple[MessageTemplate, Optional[str]]] = (
            select(MessageTemplate, City.name)
            .select_from(MessageTemplate)
            .outerjoin(City, City.id == MessageTemplate.city_id)
            .order_by(
                MessageTemplate.key.asc(),
                MessageTemplate.locale.asc(),
                MessageTemplate.channel.asc(),
                MessageTemplate.city_id.is_(None).desc(),
                MessageTemplate.city_id.asc(),
                MessageTemplate.version.desc(),
            )
        )
        if filters:
            base_query = base_query.where(*filters)

        rows = (await session.execute(base_query)).all()
        active_templates = (
            await session.scalars(select(MessageTemplate).where(MessageTemplate.is_active.is_(True)))
        ).all()

    summaries: List[MessageTemplateSummary] = []
    active_tg_keys: set[str] = set()
    for item, city_name in rows:
        stage_code = _infer_stage(item.key)
        summaries.append(
            MessageTemplateSummary(
                id=item.id,
                key=item.key,
                locale=item.locale,
                channel=item.channel,
                city_id=item.city_id,
                city_name=city_name or city_map.get(item.city_id) or "Общий",
                version=item.version,
                is_active=item.is_active,
                updated_by=item.updated_by,
                created_at=item.created_at,
                updated_at=item.updated_at,
                length=len(item.body_md or ""),
                preview=_preview_text(item.body_md or ""),
                body=item.body_md or "",
                stage=stage_code,
            )
        )
        if item.channel == DEFAULT_CHANNEL and item.locale == DEFAULT_LOCALE and item.is_active:
            active_tg_keys.add(item.key)

    missing_required = sorted(set(REQUIRED_TG_TEMPLATE_KEYS) - active_tg_keys)

    coverage = _coverage_gaps(active_templates, city_map)

    return {
        "templates": summaries,
        "missing_required": missing_required,
        "known_hints": KNOWN_TEMPLATE_HINTS,
        "cities": [{"id": key, "name": value} for key, value in city_map.items()],
        "filters": {
            "city": "default" if default_only else city_filter_value,
            "key": key_query or "",
            "channel": channel or "",
            "status": status or "",
        },
        "variables": list(AVAILABLE_VARIABLES),
        "mock_context": dict(MOCK_CONTEXT),
        "coverage": coverage,
    }


async def get_message_template(template_id: int) -> Optional[MessageTemplate]:
    async with async_session() as session:
        return await session.get(MessageTemplate, template_id)


async def get_template_history(template_id: int, limit: int = 15) -> List[MessageTemplateHistory]:
    async with async_session() as session:
        rows = await session.scalars(
            select(MessageTemplateHistory)
            .where(MessageTemplateHistory.template_id == template_id)
            .order_by(MessageTemplateHistory.updated_at.desc(), MessageTemplateHistory.id.desc())
            .limit(limit)
        )
        return list(rows)


async def create_message_template(
    *,
    key: str,
    locale: str,
    channel: str,
    body: str,
    is_active: bool,
    city_id: Optional[int] = None,
    updated_by: Optional[str] = None,
    version: Optional[int] = None,
) -> Tuple[bool, List[str], Optional[MessageTemplate]]:
    errors: List[str] = []
    key_value = (key or "").strip()
    locale_value = (locale or DEFAULT_LOCALE).strip() or DEFAULT_LOCALE
    channel_value = (channel or DEFAULT_CHANNEL).strip() or DEFAULT_CHANNEL
    body_value = (body or "").strip()
    city_value: Optional[int] = city_id

    if not key_value:
        errors.append("Укажите ключ шаблона (например, candidate_rejection).")
    if not locale_value:
        errors.append("Укажите локаль (например, ru).")
    if not channel_value:
        errors.append("Укажите канал (например, tg).")
    elif channel_value not in ALLOWED_CHANNELS:
        errors.append(f"Канал {channel_value!r} не поддерживается. Допустимые значения: {', '.join(ALLOWED_CHANNELS)}.")
    if not body_value:
        errors.append("Введите текст шаблона.")

    if city_value is not None:
        try:
            city_value = int(city_value)
        except (TypeError, ValueError):
            errors.append("Некорректный идентификатор города.")
            city_value = None

    unknown_placeholders = _find_unknown_placeholders(body_value)
    if unknown_placeholders and is_active:
        errors.append(
            "Неизвестные переменные: "
            + ", ".join(unknown_placeholders)
            + ". Используйте список доступных переменных справа."
        )

    errors.extend(_validate_template_markup(body_value))

    if version is None:
        version_value = DEFAULT_VERSION
    else:
        try:
            version_value = int(version)
        except (TypeError, ValueError):
            errors.append("Версия должна быть целым числом.")
            version_value = DEFAULT_VERSION
        else:
            if version_value <= 0:
                errors.append("Версия должна быть положительным числом.")
                version_value = DEFAULT_VERSION

    if errors:
        return False, errors, None

    now = datetime.now(timezone.utc)
    actor = _normalize_actor(updated_by)
    async with async_session() as session:
        if city_value is not None:
            city_obj = await session.get(City, city_value)
            if city_obj is None:
                errors.append("Указанный город не найден.")
                return False, errors, None

        # Prevent silent integrity errors: check versions for this combination in advance
        existing_versions = await session.scalars(
            select(MessageTemplate.version).where(
                MessageTemplate.key == key_value,
                MessageTemplate.locale == locale_value,
                MessageTemplate.channel == channel_value,
                MessageTemplate.city_id.is_(city_value) if city_value is None else MessageTemplate.city_id == city_value,
            )
        )
        versions_list = [v for v in existing_versions if v is not None]
        if version_value in versions_list:
            next_ver = (max(versions_list) + 1) if versions_list else version_value + 1
            errors.append(
                f"Версия v{version_value} уже существует для выбранного города/канала. "
                f"Свободная следующая версия: v{next_ver}."
            )
            return False, errors, None

        if is_active:
            existing_active = await session.scalar(
                select(MessageTemplate.id).where(
                    MessageTemplate.key == key_value,
                    MessageTemplate.locale == locale_value,
                    MessageTemplate.channel == channel_value,
                    MessageTemplate.city_id.is_(city_value) if city_value is None else MessageTemplate.city_id == city_value,
                    MessageTemplate.is_active.is_(True),
                )
            )
            if existing_active:
                errors.append("Активный шаблон для этой комбинации города, ключа и канала уже существует.")
                return False, errors, None

        template = MessageTemplate(
            key=key_value,
            locale=locale_value,
            channel=channel_value,
            city_id=city_value,
            body_md=body_value,
            version=version_value,
            is_active=bool(is_active),
            updated_by=actor,
            created_at=now,
            updated_at=now,
        )
        session.add(template)
        try:
            await session.flush()
            await _append_history(session, template)
            await session.commit()
        except IntegrityError:
            await session.rollback()
            errors.append(
                "Шаблон с таким ключом, локалью, каналом, городом и версией уже существует. "
                "Повысите версию или отредактируйте существующий шаблон."
            )
            return False, errors, None

        await _invalidate_cache(template.key, template.locale, template.channel, city_id=template.city_id)
        return True, [], template


async def update_message_template(
    template_id: int,
    *,
    key: str,
    locale: str,
    channel: str,
    body: str,
    is_active: bool,
    bump_version: bool,
    city_id: Optional[int] = None,
    updated_by: Optional[str] = None,
) -> Tuple[bool, List[str]]:
    errors: List[str] = []
    key_value = (key or "").strip()
    locale_value = (locale or DEFAULT_LOCALE).strip() or DEFAULT_LOCALE
    channel_value = (channel or DEFAULT_CHANNEL).strip() or DEFAULT_CHANNEL
    body_value = (body or "").strip()
    city_value: Optional[int] = city_id

    if not key_value:
        errors.append("Укажите ключ шаблона.")
    if not locale_value:
        errors.append("Укажите локаль.")
    if not channel_value:
        errors.append("Укажите канал.")
    elif channel_value not in ALLOWED_CHANNELS:
        errors.append(f"Канал {channel_value!r} не поддерживается.")
    if not body_value:
        errors.append("Введите текст шаблона.")

    if city_value is not None:
        try:
            city_value = int(city_value)
        except (TypeError, ValueError):
            errors.append("Некорректный идентификатор города.")
            city_value = None

    unknown_placeholders = _find_unknown_placeholders(body_value)
    if unknown_placeholders and is_active:
        errors.append(
            "Неизвестные переменные: "
            + ", ".join(unknown_placeholders)
            + ". Используйте список доступных переменных справа."
        )

    errors.extend(_validate_template_markup(body_value))

    if errors:
        return False, errors

    now = datetime.now(timezone.utc)
    actor = _normalize_actor(updated_by)
    async with async_session() as session:
        template = await session.get(MessageTemplate, template_id)
        if template is None:
            errors.append("Шаблон не найден или был удалён.")
            return False, errors

        if city_value is not None:
            city_obj = await session.get(City, city_value)
            if city_obj is None:
                errors.append("Указанный город не найден.")
                return False, errors

        previous_city_id = template.city_id
        template.key = key_value
        template.locale = locale_value
        template.channel = channel_value
        template.body_md = body_value
        template.is_active = bool(is_active)
        template.city_id = city_value
        template.updated_by = actor
        if bump_version:
            template.version = (template.version or 0) + 1
        template.updated_at = now

        if is_active:
            existing_active = await session.scalar(
                select(MessageTemplate.id).where(
                    MessageTemplate.key == key_value,
                    MessageTemplate.locale == locale_value,
                    MessageTemplate.channel == channel_value,
                    MessageTemplate.city_id.is_(city_value) if city_value is None else MessageTemplate.city_id == city_value,
                    MessageTemplate.is_active.is_(True),
                    MessageTemplate.id != template_id,
                )
            )
            if existing_active:
                await session.rollback()
                errors.append(
                    "Уже есть активный шаблон для этой комбинации города, ключа и канала. "
                    "Выключите или обновите существующий шаблон."
                )
                return False, errors

        try:
            await session.flush()
            await _append_history(session, template)
            await session.commit()
        except IntegrityError:
            await session.rollback()
            errors.append(
                "Невозможно сохранить: комбинация ключа, локали, канала, города и версии уже используется."
            )
            return False, errors

        await _invalidate_cache(template.key, template.locale, template.channel, city_id=template.city_id)
        if previous_city_id != template.city_id:
            await _invalidate_cache(template.key, template.locale, template.channel, city_id=previous_city_id)
        return True, []


async def delete_message_template(template_id: int) -> None:
    async with async_session() as session:
        template = await session.get(MessageTemplate, template_id)
        if template is None:
            return
        key = template.key
        locale = template.locale
        channel = template.channel
        city_id = template.city_id
        await session.delete(template)
        await session.commit()
    await _invalidate_cache(key, locale, channel, city_id=city_id)


async def _invalidate_cache(key: str, locale: str, channel: str, *, city_id: Optional[int] = None) -> None:
    try:
        from backend.apps.bot.services import get_template_provider
    except Exception:
        return

    try:
        provider = get_template_provider()
        await provider.invalidate(key=key, locale=locale, channel=channel, city_id=city_id)
    except Exception:  # pragma: no cover - defensive logging
        logger.exception(
            "Failed to invalidate template cache",
            extra={"key": key, "locale": locale, "channel": channel},
        )


class _TelegramHTMLValidator(HTMLParser):
    _ALLOWED_TAGS = {"b", "strong", "i", "em", "u", "s", "code", "pre", "a", "span"}
    _SELF_CLOSING = {"br"}
    _ALLOWED_ATTRS = {
        "a": {"href"},
        "span": {"class"},
    }

    def __init__(self) -> None:
        super().__init__()
        self._stack: List[str] = []
        self.errors: List[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:  # type: ignore[override]
        tag = tag.lower()
        if tag not in self._ALLOWED_TAGS and tag not in self._SELF_CLOSING:
            self.errors.append(f"Тег <{tag}> не поддерживается Telegram.")
            return
        allowed_attrs = self._ALLOWED_ATTRS.get(tag, set())
        for attr, _value in attrs:
            if attr not in allowed_attrs:
                self.errors.append(f"Атрибут '{attr}' не разрешён в теге <{tag}>.")
        if tag in self._SELF_CLOSING:
            return
        self._stack.append(tag)

    def handle_endtag(self, tag: str) -> None:  # type: ignore[override]
        tag = tag.lower()
        if tag in self._SELF_CLOSING:
            return
        if tag not in self._ALLOWED_TAGS:
            self.errors.append(f"Тег </{tag}> не поддерживается Telegram.")
            return
        if not self._stack:
            self.errors.append(f"Лишний закрывающий тег </{tag}>.")
            return
        expected = self._stack.pop()
        if expected != tag:
            self.errors.append(f"Ожидался закрывающий тег </{expected}>, но найден </{tag}>.")

    def close(self) -> None:  # type: ignore[override]
        super().close()
        while self._stack:
            tag = self._stack.pop()
            self.errors.append(f"Тег <{tag}> не закрыт.")


def _validate_template_markup(text: str) -> List[str]:
    validator = _TelegramHTMLValidator()
    try:
        validator.feed(text)
    except Exception as exc:
        return [f"Не удалось разобрать HTML: {exc}"]
    validator.close()
    return validator.errors


def _find_unknown_placeholders(text: str) -> List[str]:
    allowed = {item["name"] for item in AVAILABLE_VARIABLES}
    found = set(re.findall(r"{([a-zA-Z0-9_]+)}", text or ""))
    return sorted(name for name in found if name not in allowed)


def _normalize_actor(updated_by: Optional[str]) -> Optional[str]:
    if updated_by:
        return updated_by.strip() or None
    try:
        return get_settings().admin_username or None
    except Exception:
        return None


async def _append_history(session, template: MessageTemplate) -> None:
    session.add(
        MessageTemplateHistory(
            template_id=template.id,
            key=template.key,
            locale=template.locale,
            channel=template.channel,
            city_id=template.city_id,
            body_md=template.body_md,
            version=template.version,
            is_active=template.is_active,
            updated_by=template.updated_by,
            created_at=template.created_at,
            updated_at=template.updated_at,
        )
    )


async def set_active_state(template_id: int, is_active: bool) -> Tuple[bool, List[str]]:
    errors: List[str] = []
    async with async_session() as session:
        template = await session.get(MessageTemplate, template_id)
        if template is None:
            return False, ["Шаблон не найден"]

        if is_active:
            # выключаем остальные шаблоны с тем же ключом/городом/каналом/локалью
            await session.execute(
                update(MessageTemplate)
                .where(
                    MessageTemplate.id != template.id,
                    MessageTemplate.key == template.key,
                    MessageTemplate.locale == template.locale,
                    MessageTemplate.channel == template.channel,
                    MessageTemplate.city_id == template.city_id,
                )
                .values(is_active=False)
            )

        template.is_active = is_active
        await session.commit()
    return True, errors


__all__ = [
    "ALLOWED_CHANNELS",
    "DEFAULT_CHANNEL",
    "DEFAULT_LOCALE",
    "AVAILABLE_VARIABLES",
    "KNOWN_TEMPLATE_HINTS",
    "REQUIRED_TG_TEMPLATE_KEYS",
    "MessageTemplateSummary",
    "create_message_template",
    "delete_message_template",
    "get_message_template",
    "get_template_history",
    "list_message_templates",
    "update_message_template",
    "set_active_state",
]
