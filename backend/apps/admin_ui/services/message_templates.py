from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional, Sequence, Tuple

from sqlalchemy import Select, select
from sqlalchemy.exc import IntegrityError

from backend.core.db import async_session
from backend.domain.models import MessageTemplate

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
    "reminder_24h",
)


KNOWN_TEMPLATE_HINTS: Dict[str, str] = {
    "interview_confirmed_candidate": "Сообщение кандидату после подтверждения слота рекрутёром.",
    "candidate_reschedule_prompt": "Уведомление кандидату, когда слот освобождён и требуется выбрать новое время.",
    "candidate_rejection": "Итоговое сообщение при отказе кандидату.",
    "recruiter_candidate_confirmed_notice": "Уведомление рекрутёру, когда кандидат подтвердил участие.",
    "confirm_6h": "Напоминание кандидату за 6 часов до встречи с кнопками подтверждения.",
    "confirm_2h": "Напоминание/подтверждение за 2 часа до встречи.",
    "reminder_24h": "Напоминание кандидату за сутки до встречи.",
}


@dataclass(frozen=True)
class MessageTemplateSummary:
    id: int
    key: str
    locale: str
    channel: str
    version: int
    is_active: bool
    updated_at: datetime
    length: int
    preview: str
    body: str


def _preview_text(text: str, limit: int = 140) -> str:
    cleaned = " ".join((text or "").split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1].rstrip() + "…"


async def list_message_templates() -> Dict[str, object]:
    async with async_session() as session:
        query: Select[Tuple[MessageTemplate]] = select(MessageTemplate).order_by(
            MessageTemplate.key.asc(),
            MessageTemplate.locale.asc(),
            MessageTemplate.channel.asc(),
            MessageTemplate.version.desc(),
        )
        items = (await session.scalars(query)).all()

    summaries: List[MessageTemplateSummary] = []
    active_tg_keys: set[str] = set()
    for item in items:
        summaries.append(
            MessageTemplateSummary(
                id=item.id,
                key=item.key,
                locale=item.locale,
                channel=item.channel,
                version=item.version,
                is_active=item.is_active,
                updated_at=item.updated_at,
                length=len(item.body_md or ""),
                preview=_preview_text(item.body_md or ""),
                body=item.body_md or "",
            )
        )
        if item.channel == DEFAULT_CHANNEL and item.locale == DEFAULT_LOCALE and item.is_active:
            active_tg_keys.add(item.key)

    missing_required = sorted(set(REQUIRED_TG_TEMPLATE_KEYS) - active_tg_keys)

    return {
        "templates": summaries,
        "missing_required": missing_required,
        "known_hints": KNOWN_TEMPLATE_HINTS,
    }


async def get_message_template(template_id: int) -> Optional[MessageTemplate]:
    async with async_session() as session:
        return await session.get(MessageTemplate, template_id)


async def create_message_template(
    *,
    key: str,
    locale: str,
    channel: str,
    body: str,
    is_active: bool,
    version: Optional[int] = None,
) -> Tuple[bool, List[str], Optional[MessageTemplate]]:
    errors: List[str] = []
    key_value = (key or "").strip()
    locale_value = (locale or DEFAULT_LOCALE).strip() or DEFAULT_LOCALE
    channel_value = (channel or DEFAULT_CHANNEL).strip() or DEFAULT_CHANNEL
    body_value = (body or "").strip()

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
    async with async_session() as session:
        template = MessageTemplate(
            key=key_value,
            locale=locale_value,
            channel=channel_value,
            body_md=body_value,
            version=version_value,
            is_active=bool(is_active),
            updated_at=now,
        )
        session.add(template)
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            errors.append(
                "Шаблон с таким ключом, локалью, каналом и версией уже существует. "
                "Повысите версию или отредактируйте существующий шаблон."
            )
            return False, errors, None

        await _invalidate_cache(template.key, template.locale, template.channel)
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
) -> Tuple[bool, List[str]]:
    errors: List[str] = []
    key_value = (key or "").strip()
    locale_value = (locale or DEFAULT_LOCALE).strip() or DEFAULT_LOCALE
    channel_value = (channel or DEFAULT_CHANNEL).strip() or DEFAULT_CHANNEL
    body_value = (body or "").strip()

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

    if errors:
        return False, errors

    now = datetime.now(timezone.utc)
    async with async_session() as session:
        template = await session.get(MessageTemplate, template_id)
        if template is None:
            errors.append("Шаблон не найден или был удалён.")
            return False, errors

        template.key = key_value
        template.locale = locale_value
        template.channel = channel_value
        template.body_md = body_value
        template.is_active = bool(is_active)
        if bump_version:
            template.version = (template.version or 0) + 1
        template.updated_at = now

        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            errors.append(
                "Невозможно сохранить: комбинация ключа, локали, канала и версии уже используется."
            )
            return False, errors

        await _invalidate_cache(template.key, template.locale, template.channel)
        return True, []


async def delete_message_template(template_id: int) -> None:
    async with async_session() as session:
        template = await session.get(MessageTemplate, template_id)
        if template is None:
            return
        key = template.key
        locale = template.locale
        channel = template.channel
        await session.delete(template)
        await session.commit()
    await _invalidate_cache(key, locale, channel)


async def _invalidate_cache(key: str, locale: str, channel: str) -> None:
    try:
        from backend.apps.bot.services import get_template_provider
    except Exception:
        return

    try:
        provider = get_template_provider()
        await provider.invalidate(key=key, locale=locale, channel=channel)
    except Exception:  # pragma: no cover - defensive logging
        logger.exception(
            "Failed to invalidate template cache",
            extra={"key": key, "locale": locale, "channel": channel},
        )


__all__ = [
    "ALLOWED_CHANNELS",
    "DEFAULT_CHANNEL",
    "DEFAULT_LOCALE",
    "KNOWN_TEMPLATE_HINTS",
    "REQUIRED_TG_TEMPLATE_KEYS",
    "MessageTemplateSummary",
    "create_message_template",
    "delete_message_template",
    "get_message_template",
    "list_message_templates",
    "update_message_template",
]
