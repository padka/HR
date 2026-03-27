"""Channel-agnostic candidate portal helpers."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import re
import time
from urllib.parse import quote, urlparse
from typing import Any, Optional

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.apps.bot.config import DEFAULT_TZ, TEST1_QUESTIONS, refresh_questions_bank
from backend.apps.bot.test1_validation import apply_partial_validation, convert_age
from backend.core.messenger.max_adapter import MaxAdapterAuthError, MaxAdapterRequestError
from backend.core.messenger.protocol import MessengerPlatform
from backend.core.messenger.registry import get_registry
from backend.core.settings import get_settings
from backend.domain import analytics
from backend.domain.candidate_status_service import CandidateStatusService
from backend.domain.candidates.models import (
    CandidateJourneySession,
    CandidateJourneySessionStatus,
    CandidateJourneyStepState,
    CandidateJourneyStepStatus,
    ChatMessage,
    ChatMessageDirection,
    ChatMessageStatus,
    QuestionAnswer,
    TestResult,
    User,
)
from backend.domain.candidates.status import CandidateStatus, STATUS_LABELS
from backend.domain.models import City, Slot, SlotStatus
from backend.domain.repositories import find_city_by_plain_name
from backend.domain.slot_service import confirm_slot_by_candidate, reject_slot, reserve_slot
from backend.domain.candidates.services import ensure_candidate_invite_token

PORTAL_JOURNEY_KEY = "candidate_portal"
PORTAL_JOURNEY_VERSION = "v1"
PORTAL_SESSION_KEY = "candidate_portal"
PORTAL_TOKEN_SALT = "candidate-portal-link"
HH_ENTRY_TOKEN_PREFIX = "hh1"
MAX_PORTAL_LAUNCH_TOKEN_PREFIX = "mx1"
PORTAL_DEFAULT_ENTRY_CHANNEL = "web"
HH_ENTRY_TOKEN_MAX_AGE_SECONDS = 30 * 24 * 60 * 60
PORTAL_STEP_LABELS = {
    "profile": "Профиль",
    "screening": "Анкета",
    "slot_selection": "Собеседование",
    "status": "Статус",
}
PORTAL_ACTIVE_SLOT_STATUSES = {
    SlotStatus.PENDING,
    SlotStatus.BOOKED,
    SlotStatus.CONFIRMED,
    SlotStatus.CONFIRMED_BY_CANDIDATE,
}
MAX_BOT_PROFILE_CACHE_TTL_SECONDS = 60
TELEGRAM_BOT_PROFILE_CACHE_TTL_SECONDS = 60
_max_bot_profile_cache: dict[str, Any] = {
    "key": None,
    "fetched_at": 0.0,
    "payload": None,
}
_telegram_bot_profile_cache: dict[str, Any] = {
    "key": None,
    "fetched_at": 0.0,
    "payload": None,
}

_status_service = CandidateStatusService()


class CandidatePortalError(ValueError):
    """Base class for candidate portal validation errors."""


class CandidatePortalAuthError(CandidatePortalError):
    """Raised when a portal access token or session is invalid."""


@dataclass(frozen=True)
class CandidatePortalAccess:
    candidate_uuid: str | None
    telegram_id: int | None
    entry_channel: str
    source_channel: str
    journey_session_id: int | None = None
    session_version: int | None = None


def _serializer() -> URLSafeTimedSerializer:
    settings = get_settings()
    return URLSafeTimedSerializer(settings.session_secret, salt=PORTAL_TOKEN_SALT)


def _urlsafe_b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _urlsafe_b64decode(value: str) -> bytes:
    raw = str(value or "").strip()
    if not raw:
        raise CandidatePortalAuthError("Ссылка для входа недействительна.")
    padding = "=" * (-len(raw) % 4)
    try:
        return base64.urlsafe_b64decode(f"{raw}{padding}".encode("ascii"))
    except Exception as exc:
        raise CandidatePortalAuthError("Ссылка для входа недействительна.") from exc


def _is_loopback_host(hostname: str | None) -> bool:
    normalized = str(hostname or "").strip().lower().strip("[]")
    return normalized in {"localhost", "127.0.0.1", "::1", "0.0.0.0"}


def get_candidate_portal_public_base_url() -> str:
    settings = get_settings()
    return (
        settings.candidate_portal_public_url
        or settings.crm_public_url
        or settings.bot_backend_url
        or ""
    ).strip().rstrip("/")


def get_candidate_portal_public_status() -> dict[str, Any]:
    base_url = get_candidate_portal_public_base_url()
    if not base_url:
        return {
            "ready": False,
            "url": None,
            "error": "candidate_portal_public_url_missing",
            "message": "CANDIDATE_PORTAL_PUBLIC_URL не настроен.",
        }
    parsed = urlparse(base_url)
    if parsed.scheme.lower() != "https":
        return {
            "ready": False,
            "url": base_url,
            "error": "candidate_portal_public_url_not_https",
            "message": "CANDIDATE_PORTAL_PUBLIC_URL должен использовать HTTPS.",
        }
    if _is_loopback_host(parsed.hostname):
        return {
            "ready": False,
            "url": base_url,
            "error": "candidate_portal_public_url_loopback",
            "message": "CANDIDATE_PORTAL_PUBLIC_URL не может указывать на localhost или loopback.",
        }
    return {
        "ready": True,
        "url": base_url,
        "error": None,
        "message": None,
    }


def get_candidate_portal_max_entry_status() -> dict[str, Any]:
    portal_status = get_candidate_portal_public_status()
    settings = get_settings()
    link_base = str(settings.max_bot_link_base or "").strip().rstrip("/")
    if not link_base:
        return {
            "ready": False,
            "url": None,
            "error": "max_bot_link_base_missing",
            "message": "MAX_BOT_LINK_BASE не настроен.",
            "portal": portal_status,
        }
    parsed = urlparse(link_base)
    if parsed.scheme.lower() != "https":
        return {
            "ready": False,
            "url": link_base,
            "error": "max_bot_link_base_not_https",
            "message": "MAX_BOT_LINK_BASE должен использовать HTTPS.",
            "portal": portal_status,
        }
    if not portal_status["ready"]:
        return {
            "ready": False,
            "url": link_base,
            "error": str(portal_status["error"] or "candidate_portal_public_url_invalid"),
            "message": str(portal_status["message"] or "Публичный URL кабинета кандидата не готов."),
            "portal": portal_status,
        }
    return {
        "ready": True,
        "url": link_base,
        "error": None,
        "message": None,
        "portal": portal_status,
    }


def _max_bot_profile_cache_key() -> str:
    settings = get_settings()
    source = "\n".join(
        [
            str(settings.max_bot_enabled),
            str(settings.max_bot_token or ""),
            str(settings.max_bot_link_base or ""),
        ]
    )
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def _get_cached_max_profile_probe() -> dict[str, Any] | None:
    cache_key = _max_bot_profile_cache_key()
    if _max_bot_profile_cache.get("key") != cache_key:
        return None
    fetched_at = float(_max_bot_profile_cache.get("fetched_at") or 0.0)
    if fetched_at <= 0 or (time.monotonic() - fetched_at) > MAX_BOT_PROFILE_CACHE_TTL_SECONDS:
        return None
    payload = _max_bot_profile_cache.get("payload")
    return dict(payload) if isinstance(payload, dict) else None


def _store_max_profile_probe(payload: dict[str, Any]) -> dict[str, Any]:
    cached = dict(payload)
    _max_bot_profile_cache["key"] = _max_bot_profile_cache_key()
    _max_bot_profile_cache["fetched_at"] = time.monotonic()
    _max_bot_profile_cache["payload"] = cached
    return dict(cached)


def _extract_max_profile_root(payload: dict[str, Any]) -> dict[str, Any]:
    nested = payload.get("user")
    if isinstance(nested, dict):
        return nested
    return payload


def _extract_max_profile_name(payload: dict[str, Any]) -> str | None:
    profile = _extract_max_profile_root(payload)
    for key in ("name", "display_name", "full_name", "title", "username"):
        value = str(profile.get(key) or "").strip()
        if value:
            return value
    return None


def _extract_max_profile_link_base(payload: dict[str, Any]) -> str | None:
    profile = _extract_max_profile_root(payload)
    for key in ("link", "url", "public_url"):
        value = str(profile.get(key) or "").strip().rstrip("/")
        parsed = urlparse(value)
        if parsed.scheme.lower() == "https" and str(parsed.netloc or "").strip():
            return value

    for key in ("username", "slug", "handle", "public_name", "login"):
        value = str(profile.get(key) or "").strip().lstrip("@")
        if re.fullmatch(r"[A-Za-z0-9._-]{1,120}", value):
            return f"https://max.ru/{value}"

    for key in ("user_id", "id", "uid"):
        value = str(profile.get(key) or "").strip()
        digits = "".join(ch for ch in value if ch.isdigit())
        if digits:
            return f"https://max.ru/id{digits}_bot"
    return None


async def _ensure_max_bot_profile_adapter():
    adapter = get_registry().get(MessengerPlatform.MAX)
    if adapter is not None:
        return adapter

    settings = get_settings()
    if not settings.max_bot_enabled or not settings.max_bot_token:
        return None

    try:
        from backend.core.messenger.bootstrap import bootstrap_messenger_adapters

        await bootstrap_messenger_adapters(
            bot=None,
            max_bot_enabled=settings.max_bot_enabled,
            max_bot_token=settings.max_bot_token,
        )
    except Exception:
        return None
    return get_registry().get(MessengerPlatform.MAX)


async def inspect_max_bot_profile_probe() -> dict[str, Any]:
    cached = _get_cached_max_profile_probe()
    if cached is not None:
        return cached

    settings = get_settings()
    explicit_link_base = str(settings.max_bot_link_base or "").strip().rstrip("/")
    payload: dict[str, Any] = {
        "token_valid": None,
        "bot_profile_resolved": False,
        "bot_profile_name": None,
        "max_link_base_resolved": False,
        "max_link_base_source": "env" if explicit_link_base else "missing",
        "max_link_base": explicit_link_base or None,
        "error": None,
        "message": None,
    }

    if not settings.max_bot_enabled:
        payload.update(
            {
                "token_valid": False,
                "error": "max_bot_disabled",
                "message": "MAX_BOT_ENABLED должен быть включен.",
            }
        )
        return _store_max_profile_probe(payload)
    if not settings.max_bot_token:
        payload.update(
            {
                "token_valid": False,
                "error": "max_token_missing",
                "message": "MAX_BOT_TOKEN не настроен.",
            }
        )
        return _store_max_profile_probe(payload)

    adapter = await _ensure_max_bot_profile_adapter()
    if adapter is None or not (hasattr(adapter, "get_bot_profile") or hasattr(adapter, "get_me")):
        payload.update(
            {
                "error": "max_profile_unavailable",
                "message": "MAX adapter не инициализирован.",
            }
        )
        return _store_max_profile_probe(payload)

    try:
        profile_loader = getattr(adapter, "get_bot_profile", None) or getattr(adapter, "get_me")
        profile_payload = await profile_loader()
    except MaxAdapterAuthError:
        payload.update(
            {
                "token_valid": False,
                "error": "max_token_invalid",
                "message": "MAX_BOT_TOKEN отклонён провайдером.",
            }
        )
        return _store_max_profile_probe(payload)
    except MaxAdapterRequestError as exc:
        payload.update(
            {
                "token_valid": None,
                "error": "max_profile_unavailable",
                "message": str(exc),
            }
        )
        return _store_max_profile_probe(payload)
    except Exception as exc:
        payload.update(
            {
                "token_valid": None,
                "error": "max_profile_unavailable",
                "message": str(exc),
            }
        )
        return _store_max_profile_probe(payload)

    resolved_link_base = explicit_link_base or _extract_max_profile_link_base(profile_payload)
    payload.update(
        {
            "token_valid": True,
            "bot_profile_resolved": True,
            "bot_profile_name": _extract_max_profile_name(profile_payload),
            "max_link_base_resolved": bool(resolved_link_base),
            "max_link_base_source": "env" if explicit_link_base else ("provider" if resolved_link_base else "missing"),
            "max_link_base": resolved_link_base or None,
        }
    )
    if not resolved_link_base:
        payload.update(
            {
                "error": "max_bot_link_base_unresolved",
                "message": "Не удалось определить публичную ссылку бота MAX.",
            }
        )
    return _store_max_profile_probe(payload)


async def get_candidate_portal_max_entry_status_async() -> dict[str, Any]:
    portal_status = get_candidate_portal_public_status()
    profile_probe = await inspect_max_bot_profile_probe()
    link_base = str(profile_probe.get("max_link_base") or "").strip().rstrip("/")
    token_valid = profile_probe.get("token_valid")
    if token_valid is False:
        return {
            "ready": False,
            "url": link_base or None,
            "error": str(profile_probe.get("error") or "max_token_invalid"),
            "message": str(profile_probe.get("message") or "MAX токен недействителен."),
            "portal": portal_status,
            **profile_probe,
        }
    if not profile_probe.get("bot_profile_resolved"):
        return {
            "ready": False,
            "url": link_base or None,
            "error": str(profile_probe.get("error") or "max_profile_unavailable"),
            "message": str(profile_probe.get("message") or "Профиль MAX бота недоступен."),
            "portal": portal_status,
            **profile_probe,
        }
    if not link_base:
        return {
            "ready": False,
            "url": None,
            "error": str(profile_probe.get("error") or "max_bot_link_base_unresolved"),
            "message": str(profile_probe.get("message") or "Не удалось определить публичную ссылку бота MAX."),
            "portal": portal_status,
            **profile_probe,
        }

    parsed = urlparse(link_base)
    if parsed.scheme.lower() != "https":
        return {
            "ready": False,
            "url": link_base,
            "error": "max_bot_link_base_not_https",
            "message": "MAX_BOT_LINK_BASE должен использовать HTTPS.",
            "portal": portal_status,
            **profile_probe,
        }
    if not portal_status["ready"]:
        return {
            "ready": False,
            "url": link_base,
            "error": str(portal_status["error"] or "candidate_portal_public_url_invalid"),
            "message": str(portal_status["message"] or "Публичный URL кабинета кандидата не готов."),
            "portal": portal_status,
            **profile_probe,
        }
    return {
        "ready": True,
        "url": link_base,
        "error": None,
        "message": None,
        "portal": portal_status,
        **profile_probe,
    }


def _telegram_bot_profile_cache_key() -> str:
    settings = get_settings()
    source = "\n".join(
        [
            str(settings.bot_enabled),
            str(settings.bot_token or ""),
        ]
    )
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def _get_cached_telegram_profile_probe() -> dict[str, Any] | None:
    cache_key = _telegram_bot_profile_cache_key()
    if _telegram_bot_profile_cache.get("key") != cache_key:
        return None
    fetched_at = float(_telegram_bot_profile_cache.get("fetched_at") or 0.0)
    if fetched_at <= 0 or (time.monotonic() - fetched_at) > TELEGRAM_BOT_PROFILE_CACHE_TTL_SECONDS:
        return None
    payload = _telegram_bot_profile_cache.get("payload")
    return dict(payload) if isinstance(payload, dict) else None


def _store_telegram_profile_probe(payload: dict[str, Any]) -> dict[str, Any]:
    cached = dict(payload)
    _telegram_bot_profile_cache["key"] = _telegram_bot_profile_cache_key()
    _telegram_bot_profile_cache["fetched_at"] = time.monotonic()
    _telegram_bot_profile_cache["payload"] = cached
    return dict(cached)


def _extract_telegram_profile_name(payload: dict[str, Any]) -> str | None:
    for key in ("full_name", "first_name", "name", "username"):
        value = str(payload.get(key) or "").strip()
        if value:
            return value
    return None


def _extract_telegram_profile_link_base(payload: dict[str, Any]) -> str | None:
    username = str(payload.get("username") or "").strip().lstrip("@")
    if re.fullmatch(r"[A-Za-z0-9_]{4,64}", username):
        return f"https://t.me/{username}"
    return None


async def _ensure_telegram_bot_profile_adapter():
    adapter = get_registry().get(MessengerPlatform.TELEGRAM)
    if adapter is not None:
        return adapter

    settings = get_settings()
    if not settings.bot_token:
        return None

    try:
        from backend.core.messenger.bootstrap import bootstrap_messenger_adapters

        await bootstrap_messenger_adapters(
            bot=None,
            max_bot_enabled=settings.max_bot_enabled,
            max_bot_token=settings.max_bot_token,
        )
    except Exception:
        return None
    return get_registry().get(MessengerPlatform.TELEGRAM)


async def inspect_telegram_bot_profile_probe() -> dict[str, Any]:
    cached = _get_cached_telegram_profile_probe()
    if cached is not None:
        return cached

    settings = get_settings()
    payload: dict[str, Any] = {
        "token_valid": None,
        "bot_profile_resolved": False,
        "bot_profile_name": None,
        "telegram_link_base_resolved": False,
        "telegram_link_base_source": "provider",
        "telegram_link_base": None,
        "error": None,
        "message": None,
    }

    if not settings.bot_enabled:
        payload.update(
            {
                "token_valid": False,
                "telegram_link_base_source": "missing",
                "error": "telegram_bot_disabled",
                "message": "BOT_ENABLED должен быть включен для Telegram entry.",
            }
        )
        return _store_telegram_profile_probe(payload)
    if not settings.bot_token:
        payload.update(
            {
                "token_valid": False,
                "telegram_link_base_source": "missing",
                "error": "telegram_token_missing",
                "message": "BOT_TOKEN не настроен.",
            }
        )
        return _store_telegram_profile_probe(payload)

    adapter = await _ensure_telegram_bot_profile_adapter()
    if adapter is None or not (hasattr(adapter, "get_bot_profile") or hasattr(adapter, "get_me")):
        payload.update(
            {
                "error": "telegram_profile_unavailable",
                "message": "Telegram adapter не инициализирован.",
            }
        )
        return _store_telegram_profile_probe(payload)

    try:
        profile_loader = getattr(adapter, "get_bot_profile", None) or getattr(adapter, "get_me")
        profile_payload = await profile_loader()
    except Exception as exc:
        message = str(exc)
        payload.update(
            {
                "token_valid": False if "token" in message.lower() or "unauthorized" in message.lower() else None,
                "error": "telegram_profile_unavailable",
                "message": message or "Профиль Telegram бота недоступен.",
            }
        )
        return _store_telegram_profile_probe(payload)

    resolved_link_base = _extract_telegram_profile_link_base(profile_payload)
    payload.update(
        {
            "token_valid": True,
            "bot_profile_resolved": True,
            "bot_profile_name": _extract_telegram_profile_name(profile_payload),
            "telegram_link_base_resolved": bool(resolved_link_base),
            "telegram_link_base_source": "provider" if resolved_link_base else "missing",
            "telegram_link_base": resolved_link_base or None,
        }
    )
    if not resolved_link_base:
        payload.update(
            {
                "error": "telegram_link_base_unresolved",
                "message": "Не удалось определить публичную ссылку Telegram бота.",
            }
        )
    return _store_telegram_profile_probe(payload)


async def get_candidate_portal_telegram_entry_status_async() -> dict[str, Any]:
    portal_status = get_candidate_portal_public_status()
    profile_probe = await inspect_telegram_bot_profile_probe()
    link_base = str(profile_probe.get("telegram_link_base") or "").strip().rstrip("/")
    token_valid = profile_probe.get("token_valid")
    if token_valid is False:
        return {
            "ready": False,
            "url": link_base or None,
            "error": str(profile_probe.get("error") or "telegram_token_invalid"),
            "message": str(profile_probe.get("message") or "Telegram токен недействителен."),
            "portal": portal_status,
            **profile_probe,
        }
    if not profile_probe.get("bot_profile_resolved"):
        return {
            "ready": False,
            "url": link_base or None,
            "error": str(profile_probe.get("error") or "telegram_profile_unavailable"),
            "message": str(profile_probe.get("message") or "Профиль Telegram бота недоступен."),
            "portal": portal_status,
            **profile_probe,
        }
    if not link_base:
        return {
            "ready": False,
            "url": None,
            "error": str(profile_probe.get("error") or "telegram_link_base_unresolved"),
            "message": str(profile_probe.get("message") or "Не удалось определить публичную ссылку Telegram бота."),
            "portal": portal_status,
            **profile_probe,
        }
    if not portal_status["ready"]:
        return {
            "ready": False,
            "url": link_base,
            "error": str(portal_status["error"] or "candidate_portal_public_url_invalid"),
            "message": str(portal_status["message"] or "Публичный URL кабинета кандидата не готов."),
            "portal": portal_status,
            **profile_probe,
        }
    return {
        "ready": True,
        "url": link_base,
        "error": None,
        "message": None,
        "portal": portal_status,
        **profile_probe,
    }


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def invalidate_max_bot_profile_probe_cache() -> None:
    _max_bot_profile_cache["key"] = None
    _max_bot_profile_cache["fetched_at"] = 0.0
    _max_bot_profile_cache["payload"] = None


def invalidate_telegram_bot_profile_probe_cache() -> None:
    _telegram_bot_profile_cache["key"] = None
    _telegram_bot_profile_cache["fetched_at"] = 0.0
    _telegram_bot_profile_cache["payload"] = None


def _portal_vacancy_label(candidate: User) -> str:
    desired_position = str(candidate.desired_position or "").strip()
    if desired_position:
        return desired_position
    vacancy_id = str(candidate.hh_vacancy_id or "").strip()
    if vacancy_id:
        return f"HH вакансия {vacancy_id}"
    return "Вакансия уточняется"


def _portal_company_name() -> str:
    settings = get_settings()
    company_name = str(getattr(settings, "default_company_name", "") or "").strip()
    return company_name or "Компания"


def _portal_company_summary(candidate: User) -> str:
    company_name = _portal_company_name()
    vacancy_label = _portal_vacancy_label(candidate)
    return (
        f"Вы проходите отбор в {company_name} по вакансии «{vacancy_label}». "
        "Здесь можно пройти анкету, увидеть текущий этап и время следующего шага, "
        "а после screening выбрать удобный слот без потери прогресса."
    )


def _portal_company_highlights() -> list[str]:
    return [
        "Анкета и прогресс сохраняются автоматически",
        "Статус и следующий шаг видны в одном месте",
        "Запись на собеседование доступна из кабинета",
    ]


def _portal_company_faq() -> list[dict[str, str]]:
    return [
        {
            "question": "Как проходит отбор?",
            "answer": "Сначала вы заполняете профиль и короткую анкету, затем выбираете удобный слот собеседования и получаете обновления в кабинете.",
        },
        {
            "question": "Нужно ли постоянно сидеть в мессенджере?",
            "answer": "Нет. Личный кабинет остается основным местом, где видны этапы, сообщения, материалы и запись на собеседование.",
        },
        {
            "question": "Что делать, если нет слотов?",
            "answer": "Прогресс сохранится автоматически. Как только рекрутер откроет слот, кабинет покажет следующий шаг и актуальный статус.",
        },
    ]


def _portal_company_documents(candidate: User) -> list[dict[str, str]]:
    vacancy_label = _portal_vacancy_label(candidate)
    return [
        {
            "key": "process",
            "title": "Как устроен отбор",
            "summary": f"Пошаговый путь по вакансии «{vacancy_label}»: профиль, анкета, собеседование и обратная связь.",
        },
        {
            "key": "interview_prep",
            "title": "Как подготовиться к собеседованию",
            "summary": "Проверьте контакты, выберите удобный слот и держите кабинет под рукой: все изменения и сообщения появятся здесь.",
        },
        {
            "key": "cabinet",
            "title": "Как работает кабинет кандидата",
            "summary": "Черновики, сообщения рекрутеру, статусы и слот сохраняются автоматически и доступны по той же ссылке.",
        },
    ]


def _portal_company_contacts(
    *,
    candidate: User,
    active_slot: Slot | None,
) -> list[dict[str, str]]:
    contacts: list[dict[str, str]] = [
        {
            "label": "Поддержка",
            "value": "Напишите в раздел «Сообщения» в кабинете, и рекрутер увидит сообщение в CRM.",
        }
    ]
    recruiter_name = getattr(getattr(active_slot, "recruiter", None), "name", None)
    if recruiter_name:
        contacts.append(
            {
                "label": "Рекрутер",
                "value": str(recruiter_name),
            }
        )
    if candidate.phone:
        contacts.append(
            {
                "label": "Контакт кандидата",
                "value": str(candidate.phone),
            }
        )
    return contacts


def _next_step_slot(
    *,
    current_step: str,
    active_slot: Slot | None,
    available_slots: list[Slot],
) -> Slot | None:
    if active_slot is not None and active_slot.start_utc is not None:
        return active_slot
    if current_step == "slot_selection" and available_slots:
        return available_slots[0]
    return None


def sign_candidate_portal_token(
    *,
    candidate_uuid: str | None = None,
    telegram_id: int | None = None,
    entry_channel: str = PORTAL_DEFAULT_ENTRY_CHANNEL,
    source_channel: str = "portal",
    journey_session_id: int | None = None,
    session_version: int | None = None,
) -> str:
    if not candidate_uuid and not telegram_id:
        raise CandidatePortalError("Candidate portal token requires candidate_uuid or telegram_id")
    return _serializer().dumps(
        {
            "candidate_uuid": candidate_uuid,
            "telegram_id": telegram_id,
            "entry_channel": entry_channel or PORTAL_DEFAULT_ENTRY_CHANNEL,
            "source_channel": source_channel or "portal",
            "journey_session_id": journey_session_id,
            "session_version": session_version,
        }
    )


def sign_candidate_portal_hh_entry_token(
    *,
    candidate_uuid: str,
    journey_session_id: int,
    session_version: int,
    source_channel: str = "hh",
) -> str:
    candidate_uuid_value = str(candidate_uuid or "").strip()
    if not candidate_uuid_value:
        raise CandidatePortalError("HH entry token requires candidate_uuid")
    if int(journey_session_id or 0) <= 0 or int(session_version or 0) <= 0:
        raise CandidatePortalError("HH entry token requires journey_session_id and session_version")

    payload = {
        "cid": candidate_uuid_value,
        "jid": int(journey_session_id),
        "sv": int(session_version),
        "src": str(source_channel or "hh").strip() or "hh",
        "iat": int(_utcnow().timestamp()),
    }
    body = _urlsafe_b64encode(
        json.dumps(payload, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    )
    settings = get_settings()
    signature = _urlsafe_b64encode(
        hmac.new(
            settings.session_secret.encode("utf-8"),
            body.encode("ascii"),
            hashlib.sha256,
        ).digest()
    )
    return f"{HH_ENTRY_TOKEN_PREFIX}{signature}{body}"


def sign_candidate_portal_max_launch_token(
    *,
    candidate_uuid: str,
    journey_session_id: int,
    session_version: int,
    source_channel: str = "max_app",
) -> str:
    candidate_uuid_value = str(candidate_uuid or "").strip()
    if not candidate_uuid_value:
        raise CandidatePortalError("MAX launch token requires candidate_uuid")
    if int(journey_session_id or 0) <= 0 or int(session_version or 0) <= 0:
        raise CandidatePortalError("MAX launch token requires journey_session_id and session_version")

    payload = {
        "cid": candidate_uuid_value,
        "jid": int(journey_session_id),
        "sv": int(session_version),
        "src": str(source_channel or "max_app").strip() or "max_app",
        "iat": int(_utcnow().timestamp()),
    }
    body = _urlsafe_b64encode(
        json.dumps(payload, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    )
    settings = get_settings()
    signature = _urlsafe_b64encode(
        hmac.new(
            settings.session_secret.encode("utf-8"),
            body.encode("ascii"),
            hashlib.sha256,
        ).digest()
    )
    return f"{MAX_PORTAL_LAUNCH_TOKEN_PREFIX}{signature}{body}"


def parse_candidate_portal_token(value: str) -> CandidatePortalAccess:
    settings = get_settings()
    try:
        payload = _serializer().loads(
            value,
            max_age=settings.candidate_portal_token_ttl_seconds,
        )
    except SignatureExpired as exc:
        raise CandidatePortalAuthError("Ссылка для входа устарела.") from exc
    except BadSignature as exc:
        raise CandidatePortalAuthError("Ссылка для входа недействительна.") from exc

    candidate_uuid = str(payload.get("candidate_uuid") or "").strip() or None
    telegram_id_raw = payload.get("telegram_id")
    telegram_id = int(telegram_id_raw) if telegram_id_raw not in (None, "") else None
    if not candidate_uuid and not telegram_id:
        raise CandidatePortalAuthError("Ссылка не содержит идентификатор кандидата.")

    return CandidatePortalAccess(
        candidate_uuid=candidate_uuid,
        telegram_id=telegram_id,
        entry_channel=str(payload.get("entry_channel") or PORTAL_DEFAULT_ENTRY_CHANNEL),
        source_channel=str(payload.get("source_channel") or "portal"),
        journey_session_id=int(payload["journey_session_id"]) if payload.get("journey_session_id") not in (None, "") else None,
        session_version=int(payload["session_version"]) if payload.get("session_version") not in (None, "") else None,
    )


def parse_candidate_portal_hh_entry_token(value: str) -> CandidatePortalAccess:
    raw = (value or "").strip()
    if not raw.startswith(HH_ENTRY_TOKEN_PREFIX):
        raise CandidatePortalAuthError("Ссылка для входа недействительна.")

    signature_length = 43
    offset = len(HH_ENTRY_TOKEN_PREFIX)
    if len(raw) <= offset + signature_length:
        raise CandidatePortalAuthError("Ссылка для входа недействительна.")
    provided_signature = raw[offset : offset + signature_length]
    body = raw[offset + signature_length :]

    settings = get_settings()
    expected_signature = _urlsafe_b64encode(
        hmac.new(
            settings.session_secret.encode("utf-8"),
            body.encode("ascii"),
            hashlib.sha256,
        ).digest()
    )
    if not hmac.compare_digest(provided_signature, expected_signature):
        raise CandidatePortalAuthError("Ссылка для входа недействительна.")

    try:
        payload = json.loads(_urlsafe_b64decode(body).decode("utf-8"))
    except CandidatePortalAuthError:
        raise
    except Exception as exc:
        raise CandidatePortalAuthError("Ссылка для входа недействительна.") from exc

    candidate_uuid = str(payload.get("cid") or "").strip() or None
    journey_session_id_raw = payload.get("jid")
    session_version_raw = payload.get("sv")
    journey_session_id = int(journey_session_id_raw or 0) or None
    session_version = int(session_version_raw or 0) or None
    issued_at = int(payload.get("iat") or 0)
    if not candidate_uuid or issued_at <= 0:
        raise CandidatePortalAuthError("Ссылка для входа недействительна.")

    if int(_utcnow().timestamp()) - issued_at > max(
        int(settings.candidate_portal_token_ttl_seconds),
        HH_ENTRY_TOKEN_MAX_AGE_SECONDS,
    ):
        raise CandidatePortalAuthError("Ссылка для входа устарела.")

    return CandidatePortalAccess(
        candidate_uuid=candidate_uuid,
        telegram_id=None,
        entry_channel=PORTAL_DEFAULT_ENTRY_CHANNEL,
        source_channel=str(payload.get("src") or "hh"),
        journey_session_id=journey_session_id,
        session_version=session_version,
    )


def parse_candidate_portal_max_launch_token(value: str) -> CandidatePortalAccess:
    raw = (value or "").strip()
    if not raw.startswith(MAX_PORTAL_LAUNCH_TOKEN_PREFIX):
        raise CandidatePortalAuthError("Ссылка для входа недействительна.")

    signature_length = 43
    offset = len(MAX_PORTAL_LAUNCH_TOKEN_PREFIX)
    if len(raw) <= offset + signature_length:
        raise CandidatePortalAuthError("Ссылка для входа недействительна.")
    provided_signature = raw[offset : offset + signature_length]
    body = raw[offset + signature_length :]

    settings = get_settings()
    expected_signature = _urlsafe_b64encode(
        hmac.new(
            settings.session_secret.encode("utf-8"),
            body.encode("ascii"),
            hashlib.sha256,
        ).digest()
    )
    if not hmac.compare_digest(provided_signature, expected_signature):
        raise CandidatePortalAuthError("Ссылка для входа недействительна.")

    try:
        payload = json.loads(_urlsafe_b64decode(body).decode("utf-8"))
    except CandidatePortalAuthError:
        raise
    except Exception as exc:
        raise CandidatePortalAuthError("Ссылка для входа недействительна.") from exc

    candidate_uuid = str(payload.get("cid") or "").strip() or None
    journey_session_id = int(payload.get("jid") or 0)
    session_version = int(payload.get("sv") or 0)
    issued_at = int(payload.get("iat") or 0)
    if not candidate_uuid or journey_session_id <= 0 or session_version <= 0 or issued_at <= 0:
        raise CandidatePortalAuthError("Ссылка для входа недействительна.")

    if int(_utcnow().timestamp()) - issued_at > int(settings.candidate_portal_token_ttl_seconds):
        raise CandidatePortalAuthError("Ссылка для входа устарела.")

    return CandidatePortalAccess(
        candidate_uuid=candidate_uuid,
        telegram_id=None,
        entry_channel="max",
        source_channel=str(payload.get("src") or "max_app"),
        journey_session_id=journey_session_id,
        session_version=session_version,
    )


def build_candidate_portal_url(
    *,
    candidate_uuid: str | None = None,
    telegram_id: int | None = None,
    entry_channel: str = PORTAL_DEFAULT_ENTRY_CHANNEL,
    source_channel: str = "portal",
    journey_session_id: int | None = None,
    session_version: int | None = None,
) -> str:
    settings = get_settings()
    token = sign_candidate_portal_token(
        candidate_uuid=candidate_uuid,
        telegram_id=telegram_id,
        entry_channel=entry_channel,
        source_channel=source_channel,
        journey_session_id=journey_session_id,
        session_version=session_version,
    )
    encoded_token = quote(str(token).strip(), safe="")
    base = (settings.candidate_portal_public_url or settings.crm_public_url or settings.bot_backend_url or "").rstrip("/")
    if not base:
        return f"/candidate/start?start={encoded_token}"
    if base.endswith("/candidate"):
        return f"{base}/start?start={encoded_token}"
    return f"{base}/candidate/start?start={encoded_token}"


def build_candidate_max_mini_app_url(
    *,
    start_param: str | None = None,
    invite_token: str | None = None,
    link_base: str | None = None,
) -> str:
    settings = get_settings()
    base = (link_base or settings.max_bot_link_base or "").rstrip("/")
    if not base:
        return ""
    token = (start_param or invite_token or "").strip()
    if not token:
        return ""
    separator = "&" if "?" in base else "?"
    return f"{base}{separator}startapp={quote(token, safe='')}"


def build_candidate_hh_entry_url(
    *,
    candidate_uuid: str,
    journey_session_id: int,
    session_version: int,
    source_channel: str = "hh",
) -> str:
    status = get_candidate_portal_public_status()
    if not status["ready"]:
        return ""
    token = sign_candidate_portal_hh_entry_token(
        candidate_uuid=candidate_uuid,
        journey_session_id=journey_session_id,
        session_version=session_version,
        source_channel=source_channel,
    )
    encoded_token = quote(str(token).strip(), safe="")
    base = str(status["url"] or "").rstrip("/")
    if base.endswith("/candidate"):
        return f"{base}/start?entry={encoded_token}"
    return f"{base}/candidate/start?entry={encoded_token}"


def build_candidate_public_portal_url(
    *,
    candidate_uuid: str | None = None,
    telegram_id: int | None = None,
    entry_channel: str = PORTAL_DEFAULT_ENTRY_CHANNEL,
    source_channel: str = "portal",
    journey_session_id: int | None = None,
    session_version: int | None = None,
) -> str:
    status = get_candidate_portal_public_status()
    if not status["ready"]:
        return ""
    token = sign_candidate_portal_token(
        candidate_uuid=candidate_uuid,
        telegram_id=telegram_id,
        entry_channel=entry_channel,
        source_channel=source_channel,
        journey_session_id=journey_session_id,
        session_version=session_version,
    )
    encoded_token = quote(str(token).strip(), safe="")
    base = str(status["url"] or "").rstrip("/")
    if base.endswith("/candidate"):
        return f"{base}/start?start={encoded_token}"
    return f"{base}/candidate/start?start={encoded_token}"


def build_candidate_public_max_mini_app_url(
    *,
    candidate_uuid: str,
    journey_session_id: int,
    session_version: int,
    source_channel: str = "max_app",
) -> str:
    status = get_candidate_portal_max_entry_status()
    if not status["ready"]:
        return ""
    token = sign_candidate_portal_max_launch_token(
        candidate_uuid=candidate_uuid,
        journey_session_id=journey_session_id,
        session_version=session_version,
        source_channel=source_channel,
    )
    return build_candidate_max_mini_app_url(start_param=token, link_base=str(status["url"] or ""))


async def build_candidate_public_max_mini_app_url_async(
    *,
    candidate_uuid: str,
    journey_session_id: int,
    session_version: int,
    source_channel: str = "max_app",
) -> str:
    status = await get_candidate_portal_max_entry_status_async()
    if not status["ready"]:
        return ""
    token = sign_candidate_portal_max_launch_token(
        candidate_uuid=candidate_uuid,
        journey_session_id=journey_session_id,
        session_version=session_version,
        source_channel=source_channel,
    )
    return build_candidate_max_mini_app_url(
        start_param=token,
        link_base=str(status["url"] or ""),
    )


async def build_candidate_public_telegram_entry_url_async(
    session: AsyncSession,
    *,
    candidate_uuid: str,
) -> str:
    status = await get_candidate_portal_telegram_entry_status_async()
    if not status["ready"]:
        return ""
    invite = await ensure_candidate_invite_token(session, candidate_uuid, channel="telegram")
    link_base = str(status.get("url") or "").strip().rstrip("/")
    if not link_base or not invite.token:
        return ""
    separator = "&" if "?" in link_base else "?"
    return f"{link_base}{separator}start={quote(str(invite.token), safe='')}"


def is_candidate_portal_session_valid(payload: object) -> bool:
    if not isinstance(payload, dict):
        return False
    candidate_id = payload.get("candidate_id")
    last_seen_at = payload.get("last_seen_at")
    if not isinstance(candidate_id, int) or candidate_id <= 0:
        return False
    if not isinstance(last_seen_at, (int, float)):
        return False
    journey_session_id = payload.get("journey_session_id")
    session_version = payload.get("session_version")
    if journey_session_id is not None and (not isinstance(journey_session_id, int) or journey_session_id <= 0):
        return False
    if session_version is not None and (not isinstance(session_version, int) or session_version <= 0):
        return False
    settings = get_settings()
    age_seconds = _utcnow().timestamp() - float(last_seen_at)
    return age_seconds <= float(settings.candidate_portal_session_ttl_seconds)


def touch_candidate_portal_session(payload: dict[str, Any]) -> dict[str, Any]:
    next_payload = dict(payload)
    next_payload["last_seen_at"] = _utcnow().timestamp()
    return next_payload


async def resolve_candidate_portal_user(
    session: AsyncSession,
    access: CandidatePortalAccess,
) -> User:
    user: User | None = None

    if access.candidate_uuid:
        user = await session.scalar(
            select(User).where(User.candidate_id == access.candidate_uuid)
        )

    if user is None and access.telegram_id is not None:
        user = await session.scalar(
            select(User).where(
                or_(
                    User.telegram_id == access.telegram_id,
                    User.telegram_user_id == access.telegram_id,
                )
            )
        )

    now = _utcnow()
    if user is None:
        if access.telegram_id is None:
            raise CandidatePortalAuthError("Кандидат по ссылке не найден.")
        user = User(
            telegram_id=access.telegram_id,
            telegram_user_id=access.telegram_id,
            telegram_linked_at=now,
            fio=f"TG {access.telegram_id}",
            source=access.source_channel or "portal",
            messenger_platform="telegram",
            last_activity=now,
        )
        session.add(user)
        await session.flush()
    else:
        if access.telegram_id is not None:
            if user.telegram_id is None:
                user.telegram_id = access.telegram_id
            if user.telegram_user_id is None:
                user.telegram_user_id = access.telegram_id
            if user.telegram_linked_at is None:
                user.telegram_linked_at = now
            if not user.messenger_platform:
                user.messenger_platform = "telegram"

    user.last_activity = now
    if access.source_channel and not user.source:
        user.source = access.source_channel
    await session.flush()
    return user


async def resolve_candidate_portal_access_token(
    session: AsyncSession,
    token: str,
) -> CandidatePortalAccess:
    raw_token = (token or "").strip()
    if not raw_token:
        raise CandidatePortalAuthError("Ссылка для входа недействительна.")

    if raw_token.startswith(MAX_PORTAL_LAUNCH_TOKEN_PREFIX):
        return parse_candidate_portal_max_launch_token(raw_token)
    return parse_candidate_portal_token(raw_token)


async def get_candidate_portal_user(
    session: AsyncSession,
    candidate_id: int,
) -> User | None:
    return await session.scalar(
        select(User).where(User.id == candidate_id)
    )


async def ensure_candidate_portal_session(
    session: AsyncSession,
    candidate: User,
    *,
    entry_channel: str = PORTAL_DEFAULT_ENTRY_CHANNEL,
) -> CandidateJourneySession:
    journey = await session.scalar(
        select(CandidateJourneySession)
        .where(
            CandidateJourneySession.candidate_id == candidate.id,
            CandidateJourneySession.journey_key == PORTAL_JOURNEY_KEY,
            CandidateJourneySession.status == CandidateJourneySessionStatus.ACTIVE.value,
        )
        .options(selectinload(CandidateJourneySession.step_states))
        .order_by(CandidateJourneySession.id.desc())
        .limit(1)
    )
    now = _utcnow()
    if journey is None:
        journey = CandidateJourneySession(
            candidate_id=candidate.id,
            journey_key=PORTAL_JOURNEY_KEY,
            journey_version=PORTAL_JOURNEY_VERSION,
            entry_channel=entry_channel or PORTAL_DEFAULT_ENTRY_CHANNEL,
            current_step_key="profile",
            status=CandidateJourneySessionStatus.ACTIVE.value,
            session_version=1,
            started_at=now,
            last_activity_at=now,
        )
        session.add(journey)
        await session.flush()
        return journey

    journey.entry_channel = journey.entry_channel or entry_channel or PORTAL_DEFAULT_ENTRY_CHANNEL
    journey.last_activity_at = now
    await session.flush()
    return journey


def build_candidate_portal_session_payload(
    *,
    candidate_id: int,
    entry_channel: str,
    journey: CandidateJourneySession,
    last_seen_at: datetime | None = None,
) -> dict[str, Any]:
    seen_at = last_seen_at or _utcnow()
    if seen_at.tzinfo is None:
        seen_at = seen_at.replace(tzinfo=timezone.utc)
    return {
        "candidate_id": candidate_id,
        "entry_channel": entry_channel or PORTAL_DEFAULT_ENTRY_CHANNEL,
        "journey_session_id": int(journey.id),
        "session_version": int(journey.session_version or 1),
        "last_seen_at": seen_at.timestamp(),
    }


async def bump_candidate_portal_session_version(
    session: AsyncSession,
    *,
    candidate_id: int,
) -> None:
    journeys = (
        await session.scalars(
            select(CandidateJourneySession)
            .where(
                CandidateJourneySession.candidate_id == candidate_id,
                CandidateJourneySession.journey_key == PORTAL_JOURNEY_KEY,
                CandidateJourneySession.status == CandidateJourneySessionStatus.ACTIVE.value,
            )
            .with_for_update()
        )
    ).all()
    for journey in journeys:
        journey.session_version = int(journey.session_version or 1) + 1
        journey.last_activity_at = _utcnow()


async def validate_candidate_portal_session_payload(
    session: AsyncSession,
    payload: dict[str, Any],
) -> bool:
    journey_id = int(payload.get("journey_session_id") or 0)
    session_version = int(payload.get("session_version") or 0)
    candidate_id = int(payload.get("candidate_id") or 0)
    if journey_id <= 0 or session_version <= 0 or candidate_id <= 0:
        return False

    journey = await session.get(CandidateJourneySession, journey_id)
    if journey is None:
        return False
    if int(journey.candidate_id or 0) != candidate_id:
        return False
    if journey.status != CandidateJourneySessionStatus.ACTIVE.value:
        return False
    return int(journey.session_version or 1) == session_version


async def build_candidate_entry_options(
    session: AsyncSession,
    *,
    candidate: User,
    journey: CandidateJourneySession,
    source_channel: str = "hh",
) -> dict[str, dict[str, Any]]:
    portal_status = get_candidate_portal_public_status()
    web_launch_url = ""
    if candidate.candidate_id:
        web_launch_url = build_candidate_public_portal_url(
            candidate_uuid=str(candidate.candidate_id),
            entry_channel="web",
            source_channel=f"{source_channel}_web",
            journey_session_id=int(journey.id),
            session_version=int(journey.session_version or 1),
        )

    max_status = await get_candidate_portal_max_entry_status_async()
    max_launch_url = ""
    if candidate.candidate_id and str(max_status.get("url") or "").strip():
        invite = await ensure_candidate_invite_token(session, str(candidate.candidate_id), channel="max")
        if invite.token:
            public_link = str(max_status.get("url") or "").strip().rstrip("/")
            separator = "&" if "?" in public_link else "?"
            max_launch_url = f"{public_link}{separator}start={quote(str(invite.token), safe='')}"

    telegram_status = await get_candidate_portal_telegram_entry_status_async()
    telegram_launch_url = ""
    if candidate.candidate_id:
        telegram_launch_url = await build_candidate_public_telegram_entry_url_async(
            session,
            candidate_uuid=str(candidate.candidate_id),
        )

    return {
        "web": {
            "channel": "web",
            "enabled": bool(portal_status.get("ready") and web_launch_url),
            "launch_url": web_launch_url or None,
            "reason_if_blocked": None
            if portal_status.get("ready") and web_launch_url
            else str(portal_status.get("error") or "candidate_portal_public_url_invalid"),
            "requires_bot_start": False,
            "type": "cabinet",
        },
        "max": {
            "channel": "max",
            "enabled": bool(max_status.get("ready") and max_launch_url),
            "launch_url": max_launch_url or None,
            "reason_if_blocked": None
            if max_status.get("ready") and max_launch_url
            else str(max_status.get("error") or "max_entry_blocked"),
            "requires_bot_start": True,
            "type": "external",
        },
        "telegram": {
            "channel": "telegram",
            "enabled": bool(telegram_status.get("ready") and telegram_launch_url),
            "launch_url": telegram_launch_url or None,
            "reason_if_blocked": None
            if telegram_status.get("ready") and telegram_launch_url
            else str(telegram_status.get("error") or "telegram_entry_blocked"),
            "requires_bot_start": True,
            "type": "external",
        },
    }


async def record_candidate_entry_selection(
    session: AsyncSession,
    *,
    journey: CandidateJourneySession,
    channel: str,
    source: str,
    options_snapshot: list[str],
) -> None:
    now = _utcnow()
    normalized_channel = str(channel or PORTAL_DEFAULT_ENTRY_CHANNEL).strip().lower() or PORTAL_DEFAULT_ENTRY_CHANNEL
    normalized_source = str(source or "portal").strip().lower() or "portal"
    meta = dict(journey.payload_json or {}) if isinstance(journey.payload_json, dict) else {}
    history_raw = meta.get("entry_channel_history")
    history = list(history_raw) if isinstance(history_raw, list) else []
    history.append(
        {
            "channel": normalized_channel,
            "source": normalized_source,
            "selected_at": now.isoformat(),
        }
    )
    meta["entry_source"] = normalized_source
    meta["last_entry_channel"] = normalized_channel
    meta["last_entry_channel_selected_at"] = now.isoformat()
    meta["available_channels_snapshot"] = list(options_snapshot)
    meta["entry_channel_history"] = history[-10:]
    journey.payload_json = meta
    journey.entry_channel = normalized_channel
    journey.last_activity_at = now
    await session.flush()


async def upsert_step_state(
    session: AsyncSession,
    journey: CandidateJourneySession,
    *,
    step_key: str,
    step_type: str = "form",
    status: str,
    payload: Optional[dict[str, Any]] = None,
) -> CandidateJourneyStepState:
    step_state = next((item for item in journey.step_states if item.step_key == step_key), None)
    now = _utcnow()
    if step_state is None:
        step_state = CandidateJourneyStepState(
            session_id=journey.id,
            step_key=step_key,
            step_type=step_type,
            status=status,
            payload_json=payload,
            started_at=now,
            updated_at=now,
            completed_at=now if status == CandidateJourneyStepStatus.COMPLETED.value else None,
        )
        journey.step_states.append(step_state)
        session.add(step_state)
    else:
        step_state.step_type = step_type
        step_state.status = status
        step_state.payload_json = payload
        step_state.updated_at = now
        if status == CandidateJourneyStepStatus.COMPLETED.value:
            step_state.completed_at = step_state.completed_at or now
        elif status in {
            CandidateJourneyStepStatus.PENDING.value,
            CandidateJourneyStepStatus.IN_PROGRESS.value,
        }:
            step_state.completed_at = None
    journey.last_activity_at = now
    await session.flush()
    return step_state


def _is_placeholder_fio(value: Optional[str]) -> bool:
    cleaned = (value or "").strip()
    return not cleaned or cleaned.startswith("TG ")


def _normalize_phone(value: str) -> str:
    digits = "".join(ch for ch in value if ch.isdigit())
    if len(digits) == 11 and digits.startswith("8"):
        digits = "7" + digits[1:]
    if len(digits) != 11 or not digits.startswith("7"):
        raise CandidatePortalError("Укажите телефон в формате +7XXXXXXXXXX.")
    return f"+{digits}"


async def _resolve_city(session: AsyncSession, *, city_id: int | None = None, city_name: str | None = None) -> City | None:
    if city_id:
        return await session.get(City, city_id)
    if city_name:
        return await find_city_by_plain_name(city_name)
    return None


def _question_input_type(question: dict[str, Any]) -> str:
    if question.get("options"):
        return "single_choice"
    if question.get("id") == "age":
        return "number"
    return "text"


def get_candidate_portal_questions() -> list[dict[str, Any]]:
    refresh_questions_bank()
    questions: list[dict[str, Any]] = []
    for index, question in enumerate(TEST1_QUESTIONS, start=1):
        question_id = str(question.get("id") or "").strip()
        if question_id in {"fio", "city"}:
            continue
        questions.append(
            {
                "index": index,
                "id": question_id,
                "prompt": question.get("prompt") or question.get("text") or "",
                "placeholder": question.get("placeholder"),
                "helper": question.get("helper"),
                "options": list(question.get("options") or []),
                "input_type": _question_input_type(question),
                "required": True,
            }
        )
    return questions


async def list_candidate_portal_cities(session: AsyncSession) -> list[dict[str, Any]]:
    rows = await session.execute(
        select(City)
        .where(City.active.is_(True))
        .order_by(func.lower(City.name))
    )
    return [
        {
            "id": city.id,
            "name": city.name_plain,
            "tz": city.tz,
        }
        for city in rows.scalars().all()
    ]


async def get_latest_test1_result(session: AsyncSession, candidate_id: int) -> TestResult | None:
    return await session.scalar(
        select(TestResult)
        .where(
            TestResult.user_id == candidate_id,
            TestResult.rating == "TEST1",
        )
        .order_by(TestResult.created_at.desc(), TestResult.id.desc())
        .limit(1)
    )


async def get_latest_test1_result_for_journey(
    session: AsyncSession,
    *,
    candidate_id: int,
    journey: CandidateJourneySession,
) -> TestResult | None:
    stmt = (
        select(TestResult)
        .where(
            TestResult.user_id == candidate_id,
            TestResult.rating == "TEST1",
        )
        .order_by(TestResult.created_at.desc(), TestResult.id.desc())
        .limit(1)
    )
    journey_meta = dict(journey.payload_json or {}) if journey.payload_json else {}
    if bool(journey_meta.get("restart_from_scratch")) and journey.started_at is not None:
        stmt = stmt.where(TestResult.created_at >= journey.started_at)
    return await session.scalar(stmt)


async def get_candidate_active_slot(session: AsyncSession, candidate: User) -> Slot | None:
    telegram_ids = {
        int(value)
        for value in (candidate.telegram_id, candidate.telegram_user_id)
        if value is not None
    }
    conditions = [Slot.candidate_id == candidate.candidate_id]
    if telegram_ids:
        conditions.append(Slot.candidate_tg_id.in_(telegram_ids))

    return await session.scalar(
        select(Slot)
        .options(selectinload(Slot.recruiter), selectinload(Slot.city))
        .where(
            or_(*conditions),
            func.lower(Slot.status).in_([status.lower() for status in PORTAL_ACTIVE_SLOT_STATUSES]),
            func.lower(func.coalesce(Slot.purpose, "interview")) == "interview",
        )
        .order_by(Slot.start_utc.asc(), Slot.id.asc())
        .limit(1)
    )


async def list_candidate_portal_slots(
    session: AsyncSession,
    *,
    city_id: int,
    exclude_slot_id: int | None = None,
    limit: int = 12,
) -> list[Slot]:
    now = _utcnow()
    stmt = (
        select(Slot)
        .options(selectinload(Slot.recruiter), selectinload(Slot.city))
        .where(
            Slot.city_id == city_id,
            func.lower(Slot.status) == SlotStatus.FREE,
            Slot.start_utc >= now,
            Slot.candidate_id.is_(None),
            Slot.candidate_tg_id.is_(None),
            func.lower(func.coalesce(Slot.purpose, "interview")) == "interview",
        )
        .order_by(Slot.start_utc.asc(), Slot.id.asc())
        .limit(limit)
    )
    if exclude_slot_id is not None:
        stmt = stmt.where(Slot.id != exclude_slot_id)
    rows = await session.execute(stmt)
    return list(rows.scalars().all())


def serialize_portal_slot(slot: Slot) -> dict[str, Any]:
    duration = int(getattr(slot, "duration_min", 60) or 60)
    start_utc = slot.start_utc
    end_utc = start_utc + timedelta(minutes=duration) if start_utc else None
    return {
        "id": slot.id,
        "status": slot.status,
        "purpose": slot.purpose,
        "start_utc": start_utc.isoformat() if start_utc else None,
        "end_utc": end_utc.isoformat() if end_utc else None,
        "duration_min": duration,
        "city_id": slot.city_id,
        "city_name": slot.city.name_plain if getattr(slot, "city", None) else None,
        "recruiter_id": slot.recruiter_id,
        "recruiter_name": getattr(getattr(slot, "recruiter", None), "name", None),
        "candidate_tz": slot.candidate_tz,
        "tz_name": slot.tz_name,
    }


def serialize_chat_message(message: ChatMessage) -> dict[str, Any]:
    payload = dict(message.payload_json or {}) if isinstance(message.payload_json, dict) else {}
    delivery_channels_raw = payload.get("delivery_channels")
    if isinstance(delivery_channels_raw, list):
        delivery_channels = [
            str(item).strip()
            for item in delivery_channels_raw
            if str(item).strip()
        ]
    else:
        delivery_channels = [str(message.channel).strip()] if str(message.channel or "").strip() else []

    author_role = str(payload.get("author_role") or "").strip().lower()
    if not author_role:
        if message.direction == ChatMessageDirection.INBOUND.value:
            author_role = "candidate"
        else:
            normalized_author = str(message.author_label or "").strip().lower()
            if normalized_author in {"бот", "bot"}:
                author_role = "bot"
            elif normalized_author in {"система", "system"}:
                author_role = "system"
            else:
                author_role = "recruiter"

    return {
        "id": message.id,
        "conversation_id": f"candidate:{int(message.candidate_id)}",
        "direction": message.direction,
        "channel": message.channel,
        "origin_channel": str(payload.get("origin_channel") or message.channel or "web"),
        "delivery_channels": delivery_channels,
        "delivery_state": message.status,
        "author_role": author_role,
        "text": message.text,
        "status": message.status,
        "author_label": message.author_label,
        "created_at": message.created_at.isoformat() if message.created_at else None,
    }


def _next_action_text(
    *,
    current_step: str,
    has_available_slots: bool,
    active_slot: Slot | None,
) -> str:
    if current_step == "profile":
        return "Заполните профиль, чтобы сохранить контакт и продолжить анкету."
    if current_step == "screening":
        return "Ответьте на короткую анкету. Прогресс сохранится автоматически."
    if current_step == "slot_selection":
        return "Выберите удобное время для собеседования."
    if active_slot is not None:
        status_value = (active_slot.status or "").lower()
        if status_value == SlotStatus.PENDING:
            return "Слот отправлен рекрутеру на подтверждение."
        if status_value == SlotStatus.CONFIRMED_BY_CANDIDATE:
            return "Собеседование подтверждено. Следите за напоминаниями и статусом."
        return "Проверьте детали собеседования и при необходимости подтвердите или перенесите слот."
    if has_available_slots:
        return "Выберите слот, чтобы завершить запись на собеседование."
    return "Слотов пока нет. Мы сохранили ваш прогресс и покажем следующий шаг здесь."


def _portal_slot_status_label(status: str | None) -> str | None:
    normalized = str(status or "").lower()
    if not normalized:
        return None
    if normalized == SlotStatus.PENDING.lower():
        return "На подтверждении"
    if normalized == SlotStatus.BOOKED.lower():
        return "Подтвержден рекрутером"
    if normalized in {SlotStatus.CONFIRMED.lower(), SlotStatus.CONFIRMED_BY_CANDIDATE.lower()}:
        return "Подтверждено"
    if normalized == SlotStatus.FREE.lower():
        return "Свободно"
    return normalized


def _candidate_primary_action(
    *,
    current_step: str,
    next_action: str,
    active_slot: Slot | None,
    has_available_slots: bool,
) -> dict[str, str]:
    if current_step == "profile":
        return {
            "key": "complete_profile",
            "label": "Заполнить профиль",
            "description": next_action,
            "target": "workflow",
        }
    if current_step == "screening":
        return {
            "key": "complete_screening",
            "label": "Завершить анкету",
            "description": next_action,
            "target": "workflow",
        }
    if current_step == "slot_selection":
        return {
            "key": "choose_slot",
            "label": "Выбрать слот",
            "description": next_action,
            "target": "schedule",
        }
    if active_slot is not None and str(active_slot.status or "").lower() in {
        SlotStatus.PENDING.lower(),
        SlotStatus.BOOKED.lower(),
    }:
        return {
            "key": "review_interview",
            "label": "Проверить детали собеседования",
            "description": next_action,
            "target": "schedule",
        }
    return {
        "key": "watch_updates",
        "label": "Следить за обновлениями",
        "description": next_action,
        "target": "feedback",
    }


def _dashboard_alerts(
    *,
    current_step: str,
    active_slot: Slot | None,
    available_slots: list[Slot],
    screening_complete: bool,
    messages: list[ChatMessage],
) -> list[dict[str, str]]:
    alerts: list[dict[str, str]] = []
    if current_step == "slot_selection" and not available_slots:
        alerts.append(
            {
                "level": "info",
                "title": "Свободных слотов пока нет",
                "body": "Мы сохранили ваш прогресс. Как только слот появится, кабинет покажет новый следующий шаг.",
            }
        )
    if active_slot is not None and str(active_slot.status or "").lower() == SlotStatus.PENDING.lower():
        alerts.append(
            {
                "level": "warning",
                "title": "Собеседование ожидает подтверждения",
                "body": "Рекрутер уже видит выбранный слот. Ответ и дальнейшие инструкции появятся в кабинете.",
            }
        )
    latest_outbound = next(
        (message for message in reversed(messages) if message.direction == ChatMessageDirection.OUTBOUND.value),
        None,
    )
    if latest_outbound is not None:
        alerts.append(
            {
                "level": "success",
                "title": "Есть обновление от рекрутера",
                "body": "Откройте раздел «Сообщения», чтобы прочитать последнее сообщение и ответить в том же кабинете.",
            }
        )
    elif screening_complete:
        alerts.append(
            {
                "level": "info",
                "title": "Анкета сохранена",
                "body": "Следующий шаг уже определяется системой. Проверяйте статус и раздел расписания.",
            }
        )
    return alerts[:3]


def _screening_test_item(
    *,
    screening_complete: bool,
    screening_questions_count: int,
    completed_at: str | None,
    current_step: str,
) -> dict[str, Any]:
    if screening_complete:
        status = "completed"
        status_label = "Завершено"
        summary = "Короткая анкета сохранена. Результат уже учтён в воронке."
    elif current_step == "screening":
        status = "in_progress"
        status_label = "В процессе"
        summary = "Можно продолжить с текущего места. Черновик ответов сохраняется автоматически."
    else:
        status = "pending"
        status_label = "Ожидает"
        summary = "Анкета откроется после проверки профиля и станет доступна в кабинете."
    return {
        "key": "screening",
        "title": "Короткая анкета",
        "status": status,
        "status_label": status_label,
        "summary": summary,
        "question_count": screening_questions_count,
        "completed_at": completed_at,
    }


def _test2_item(
    result: TestResult | None,
    *,
    candidate_status: CandidateStatus | None,
) -> dict[str, Any]:
    if result is not None:
        return {
            "key": "test2",
            "title": "Тест 2",
            "status": "completed",
            "status_label": "Завершено",
            "summary": "Результат второго теста сохранён в системе.",
            "completed_at": result.created_at.isoformat() if result.created_at else None,
            "final_score": float(result.final_score) if result.final_score is not None else None,
            "raw_score": int(result.raw_score) if result.raw_score is not None else None,
            "total_time": int(result.total_time) if result.total_time is not None else None,
        }
    if candidate_status in {CandidateStatus.TEST2_SENT, CandidateStatus.TEST2_COMPLETED, CandidateStatus.TEST2_FAILED}:
        status = "in_progress" if candidate_status == CandidateStatus.TEST2_SENT else "completed"
        return {
            "key": "test2",
            "title": "Тест 2",
            "status": status,
            "status_label": "Отправлен" if status == "in_progress" else "Завершено",
            "summary": "Этот этап привязывается к решению рекрутера и может открыться после первого собеседования.",
            "completed_at": None,
        }
    return {
        "key": "test2",
        "title": "Тест 2",
        "status": "pending",
        "status_label": "Пока не назначен",
        "summary": "Если этот этап понадобится, кабинет покажет задачу и дальнейшие инструкции.",
        "completed_at": None,
    }


def _feedback_items(
    *,
    candidate_status_label: str | None,
    current_step_label: str,
    next_action: str,
    active_slot: Slot | None,
    screening_complete: bool,
    screening_completed_at: str | None,
    messages: list[ChatMessage],
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = [
        {
            "kind": "status",
            "title": candidate_status_label or current_step_label,
            "body": next_action,
            "created_at": None,
            "author_role": "system",
        }
    ]
    if screening_complete:
        items.append(
            {
                "kind": "milestone",
                "title": "Анкета завершена",
                "body": "Ответы сохранены. Следующий шаг и доступные действия обновляются автоматически в кабинете.",
                "created_at": screening_completed_at,
                "author_role": "system",
            }
        )
    if active_slot is not None:
        items.append(
            {
                "kind": "schedule",
                "title": "Собеседование",
                "body": (
                    f"Статус: {str(active_slot.status or '').lower()} · "
                    f"{active_slot.city.name_plain if getattr(active_slot, 'city', None) else 'город уточняется'}"
                ),
                "created_at": active_slot.start_utc.isoformat() if active_slot.start_utc else None,
                "author_role": "system",
            }
        )
    outbound_messages = [
        message for message in reversed(messages)
        if message.direction == ChatMessageDirection.OUTBOUND.value and (message.text or "").strip()
    ]
    for message in outbound_messages[:2]:
        items.append(
            {
                "kind": "message",
                "title": "Сообщение от рекрутера",
                "body": str(message.text or "").strip(),
                "created_at": message.created_at.isoformat() if message.created_at else None,
                "author_role": "recruiter",
            }
        )
    return items[:4]


async def build_candidate_portal_journey(
    session: AsyncSession,
    candidate: User,
    *,
    entry_channel: str = PORTAL_DEFAULT_ENTRY_CHANNEL,
    journey: CandidateJourneySession | None = None,
) -> dict[str, Any]:
    if journey is None:
        journey = await ensure_candidate_portal_session(
            session,
            candidate,
            entry_channel=entry_channel,
        )
    if "step_states" not in journey.__dict__:
        await session.refresh(journey, attribute_names=["step_states"])
    step_map = {item.step_key: item for item in journey.step_states}
    profile_state = step_map.get("profile")
    screening_state = step_map.get("screening")

    test1_result = await get_latest_test1_result_for_journey(
        session,
        candidate_id=int(candidate.id),
        journey=journey,
    )
    active_slot = await get_candidate_active_slot(session, candidate)
    current_city = await _resolve_city(
        session,
        city_name=candidate.city,
    )
    available_slots = (
        await list_candidate_portal_slots(
            session,
            city_id=current_city.id,
            exclude_slot_id=active_slot.id if active_slot else None,
        )
        if current_city is not None
        else []
    )
    company_name = _portal_company_name()

    journey_meta = dict(journey.payload_json or {}) if journey.payload_json else {}
    restart_from_scratch = bool(journey_meta.get("restart_from_scratch"))
    profile_complete = (
        not _is_placeholder_fio(candidate.fio)
        and bool((candidate.phone or "").strip())
        and current_city is not None
    )
    if restart_from_scratch:
        profile_complete = bool(
            profile_state is not None
            and profile_state.status == CandidateJourneyStepStatus.COMPLETED.value
        )
    screening_complete = test1_result is not None
    has_available_slots = len(available_slots) > 0

    if not profile_complete:
        current_step = "profile"
    elif not screening_complete:
        current_step = "screening"
    elif active_slot is None and has_available_slots:
        current_step = "slot_selection"
    else:
        current_step = "status"

    next_step_slot = _next_step_slot(
        current_step=current_step,
        active_slot=active_slot,
        available_slots=available_slots,
    )
    next_step_at = next_step_slot.start_utc.isoformat() if next_step_slot and next_step_slot.start_utc else None
    next_step_timezone = None
    if next_step_slot is not None:
        next_step_timezone = next_step_slot.tz_name or next_step_slot.candidate_tz or DEFAULT_TZ

    journey.current_step_key = current_step
    journey.last_activity_at = _utcnow()
    if current_step == "profile":
        await upsert_step_state(
            session,
            journey,
            step_key="profile",
            status=CandidateJourneyStepStatus.IN_PROGRESS.value,
            payload=profile_state.payload_json if profile_state else None,
        )
    elif profile_complete:
        await upsert_step_state(
            session,
            journey,
            step_key="profile",
            status=CandidateJourneyStepStatus.COMPLETED.value,
            payload=profile_state.payload_json if profile_state else {
                "fio": candidate.fio,
                "phone": candidate.phone,
                "city_id": current_city.id if current_city else None,
            },
        )

    if screening_complete:
        await upsert_step_state(
            session,
            journey,
            step_key="screening",
            status=CandidateJourneyStepStatus.COMPLETED.value,
            payload=screening_state.payload_json if screening_state else None,
        )
    elif current_step == "screening":
        await upsert_step_state(
            session,
            journey,
            step_key="screening",
            status=CandidateJourneyStepStatus.IN_PROGRESS.value,
            payload=screening_state.payload_json if screening_state else None,
        )

    step_statuses = {
        "profile": (
            CandidateJourneyStepStatus.COMPLETED.value
            if profile_complete
            else CandidateJourneyStepStatus.IN_PROGRESS.value
        ),
        "screening": (
            CandidateJourneyStepStatus.COMPLETED.value
            if screening_complete
            else (
                CandidateJourneyStepStatus.IN_PROGRESS.value
                if current_step == "screening" or screening_state is not None
                else CandidateJourneyStepStatus.PENDING.value
            )
        ),
        "slot_selection": (
            CandidateJourneyStepStatus.COMPLETED.value
            if active_slot is not None
            else (
                CandidateJourneyStepStatus.IN_PROGRESS.value
                if screening_complete and has_available_slots and current_step in {"slot_selection", "status"}
                else CandidateJourneyStepStatus.PENDING.value
            )
        ),
        "status": (
            CandidateJourneyStepStatus.IN_PROGRESS.value
            if screening_complete
            else CandidateJourneyStepStatus.PENDING.value
        ),
    }

    messages = list(
        await session.scalars(
            select(ChatMessage)
            .where(ChatMessage.candidate_id == candidate.id)
            .order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc())
            .limit(20)
        )
    )
    latest_test2_result = await session.scalar(
        select(TestResult)
        .where(
            TestResult.user_id == candidate.id,
            func.upper(func.coalesce(TestResult.rating, "")) == "TEST2",
        )
        .order_by(TestResult.created_at.desc(), TestResult.id.desc())
        .limit(1)
    )
    next_action = _next_action_text(
        current_step=current_step,
        has_available_slots=has_available_slots,
        active_slot=active_slot,
    )
    company_faq = _portal_company_faq()
    company_documents = _portal_company_documents(candidate)
    company_contacts = _portal_company_contacts(candidate=candidate, active_slot=active_slot)
    latest_message = messages[0] if messages else None
    latest_outbound_message = next(
        (message for message in messages if message.direction == ChatMessageDirection.OUTBOUND.value),
        None,
    )
    available_channels = ["web"]
    if candidate.telegram_user_id or candidate.telegram_id:
        available_channels.append("telegram")
    if str(candidate.max_user_id or "").strip():
        available_channels.append("max")
    available_channels_snapshot = journey_meta.get("available_channels_snapshot")
    if isinstance(available_channels_snapshot, list):
        available_channels = [
            str(item).strip()
            for item in available_channels_snapshot
            if str(item).strip()
        ] or available_channels
    last_entry_channel = str(journey_meta.get("last_entry_channel") or journey.entry_channel or entry_channel or PORTAL_DEFAULT_ENTRY_CHANNEL).strip() or PORTAL_DEFAULT_ENTRY_CHANNEL

    return {
        "candidate": {
            "id": candidate.id,
            "candidate_id": candidate.candidate_id,
            "fio": candidate.fio,
            "phone": candidate.phone,
            "city": candidate.city,
            "city_id": current_city.id if current_city else None,
            "vacancy_label": _portal_vacancy_label(candidate),
            "vacancy_reference": str(candidate.hh_vacancy_id or "").strip() or None,
            "vacancy_position": str(candidate.desired_position or "").strip() or None,
            "status": candidate.candidate_status.value if candidate.candidate_status else None,
            "status_label": STATUS_LABELS.get(candidate.candidate_status) if candidate.candidate_status else None,
            "source": candidate.source,
            "entry_url": build_candidate_hh_entry_url(
                candidate_uuid=str(candidate.candidate_id or ""),
                journey_session_id=int(journey.id),
                session_version=int(journey.session_version or 1),
                source_channel="candidate_cabinet",
            )
            if candidate.candidate_id
            else "",
            "portal_url": build_candidate_portal_url(
                candidate_uuid=candidate.candidate_id,
                entry_channel=entry_channel,
                source_channel="portal",
                journey_session_id=journey.id,
                session_version=int(journey.session_version or 1),
            ),
        },
        "company": {
            "name": company_name,
            "summary": _portal_company_summary(candidate),
            "highlights": _portal_company_highlights(),
            "faq": company_faq,
            "documents": company_documents,
            "contacts": company_contacts,
        },
        "dashboard": {
            "primary_action": _candidate_primary_action(
                current_step=current_step,
                next_action=next_action,
                active_slot=active_slot,
                has_available_slots=has_available_slots,
            ),
            "alerts": _dashboard_alerts(
                current_step=current_step,
                active_slot=active_slot,
                available_slots=available_slots,
                screening_complete=screening_complete,
                messages=messages,
            ),
            "last_activity_at": candidate.last_activity.isoformat() if candidate.last_activity else None,
            "upcoming_items": [
                item
                for item in [
                    {
                        "kind": "interview",
                        "title": "Собеседование",
                        "scheduled_at": next_step_at,
                        "timezone": next_step_timezone,
                        "state": _portal_slot_status_label(getattr(active_slot, "status", None)) if active_slot else None,
                    }
                    if next_step_at
                    else None,
                    {
                        "kind": "message",
                        "title": "Последнее сообщение",
                        "scheduled_at": latest_message.created_at.isoformat() if latest_message and latest_message.created_at else None,
                        "timezone": None,
                        "state": latest_message.author_label if latest_message else None,
                    }
                    if latest_message is not None
                    else None,
                ]
                if item is not None
            ],
        },
        "tests": {
            "items": [
                _screening_test_item(
                    screening_complete=screening_complete,
                    screening_questions_count=len(get_candidate_portal_questions()),
                    completed_at=test1_result.created_at.isoformat() if test1_result and test1_result.created_at else None,
                    current_step=current_step,
                ),
                _test2_item(
                    latest_test2_result,
                    candidate_status=candidate.candidate_status,
                ),
            ],
        },
        "feedback": {
            "items": _feedback_items(
                candidate_status_label=STATUS_LABELS.get(candidate.candidate_status) if candidate.candidate_status else None,
                current_step_label=PORTAL_STEP_LABELS.get(current_step, current_step.title() if current_step else "Статус"),
                next_action=next_action,
                active_slot=active_slot,
                screening_complete=screening_complete,
                screening_completed_at=test1_result.created_at.isoformat() if test1_result and test1_result.created_at else None,
                messages=messages,
            ),
            "last_feedback_sent_at": latest_outbound_message.created_at.isoformat() if latest_outbound_message and latest_outbound_message.created_at else None,
        },
        "resources": {
            "faq": company_faq,
            "documents": company_documents,
            "contacts": company_contacts,
        },
        "journey": {
            "session_id": journey.id,
            "journey_key": journey.journey_key,
            "journey_version": journey.journey_version,
            "entry_channel": journey.entry_channel,
            "last_entry_channel": last_entry_channel,
            "available_channels": available_channels,
            "channel_options": await build_candidate_entry_options(
                session,
                candidate=candidate,
                journey=journey,
                source_channel="cabinet",
            ),
            "current_step": current_step,
            "current_step_label": PORTAL_STEP_LABELS.get(current_step, current_step.title() if current_step else "Статус"),
            "next_action": next_action,
            "next_step_at": next_step_at,
            "next_step_timezone": next_step_timezone,
            "steps": [
                {
                    "key": key,
                    "label": label,
                    "status": step_statuses.get(key, CandidateJourneyStepStatus.PENDING.value),
                }
                for key, label in PORTAL_STEP_LABELS.items()
            ],
            "profile": {
                "fio": candidate.fio if not _is_placeholder_fio(candidate.fio) else "",
                "phone": candidate.phone or "",
                "city_id": current_city.id if current_city else None,
                "city_name": current_city.name_plain if current_city else candidate.city,
            },
            "screening": {
                "questions": get_candidate_portal_questions(),
                "draft_answers": dict(screening_state.payload_json or {}) if screening_state and screening_state.payload_json else {},
                "completed": screening_complete,
                "completed_at": test1_result.created_at.isoformat() if test1_result and test1_result.created_at else None,
            },
            "slots": {
                "available": [serialize_portal_slot(slot) for slot in available_slots],
                "active": serialize_portal_slot(active_slot) if active_slot else None,
            },
            "messages": [serialize_chat_message(message) for message in reversed(messages)],
            "inbox": {
                "conversation_id": f"candidate:{int(candidate.id)}",
                "unread_count": None,
                "read_tracking_supported": False,
                "latest_message": serialize_chat_message(latest_message) if latest_message is not None else None,
                "delivery_state": latest_outbound_message.status if latest_outbound_message is not None else None,
                "available_channels": available_channels,
            },
            "cities": await list_candidate_portal_cities(session),
        },
    }


async def restart_candidate_portal_journey(
    session: AsyncSession,
    candidate: User,
    *,
    entry_channel: str = "max",
) -> tuple[CandidateJourneySession, int | None]:
    active_slot = await get_candidate_active_slot(session, candidate)
    active_slot_status = str(active_slot.status or "").lower() if active_slot is not None else ""
    if active_slot_status in {SlotStatus.CONFIRMED.lower(), SlotStatus.CONFIRMED_BY_CANDIDATE.lower()}:
        raise CandidatePortalError("У кандидата уже подтверждено собеседование. Сначала решите запись вручную.")

    released_slot_id: int | None = None
    if active_slot is not None and active_slot_status in {SlotStatus.PENDING.lower(), SlotStatus.BOOKED.lower()}:
        released_slot_id = int(active_slot.id)
        if _dialect_name(session) == "sqlite":
            active_slot.status = SlotStatus.FREE
            active_slot.candidate_id = None
            active_slot.candidate_tg_id = None
            active_slot.candidate_fio = None
            active_slot.candidate_tz = None
            active_slot.candidate_city_id = None
            active_slot.purpose = "interview"
            await session.flush()
        else:
            await reject_slot(active_slot.id)

    now = _utcnow()
    active_journeys = (
        await session.scalars(
            select(CandidateJourneySession)
            .where(
                CandidateJourneySession.candidate_id == candidate.id,
                CandidateJourneySession.journey_key == PORTAL_JOURNEY_KEY,
                CandidateJourneySession.status == CandidateJourneySessionStatus.ACTIVE.value,
            )
            .options(selectinload(CandidateJourneySession.step_states))
            .with_for_update()
        )
    ).all()

    for current_journey in active_journeys:
        current_journey.status = CandidateJourneySessionStatus.ABANDONED.value
        current_journey.completed_at = now
        current_journey.last_activity_at = now
        meta = dict(current_journey.payload_json or {})
        meta["abandoned_reason"] = "operator_restart"
        meta["abandoned_at"] = now.isoformat()
        current_journey.payload_json = meta

    await _status_service.force(candidate, CandidateStatus.LEAD, reason="candidate portal restarted")
    candidate.last_activity = now

    journey = CandidateJourneySession(
        candidate_id=candidate.id,
        journey_key=PORTAL_JOURNEY_KEY,
        journey_version=PORTAL_JOURNEY_VERSION,
        entry_channel=entry_channel or PORTAL_DEFAULT_ENTRY_CHANNEL,
        current_step_key="profile",
        status=CandidateJourneySessionStatus.ACTIVE.value,
        session_version=1,
        started_at=now,
        last_activity_at=now,
        payload_json={
            "restart_from_scratch": True,
            "restarted_at": now.isoformat(),
        },
    )
    session.add(journey)
    await session.flush()
    return journey, released_slot_id


async def save_candidate_profile(
    session: AsyncSession,
    candidate: User,
    journey: CandidateJourneySession,
    *,
    fio: str,
    phone: str,
    city_id: int,
) -> None:
    normalized_fio = (fio or "").strip()
    if not normalized_fio:
        raise CandidatePortalError("Укажите ФИО.")
    try:
        apply_partial_validation({"fio": normalized_fio})
    except Exception as exc:
        raise CandidatePortalError(str(exc)) from exc

    city = await session.get(City, city_id)
    if city is None or not city.active:
        raise CandidatePortalError("Выберите город из списка.")

    candidate.fio = normalized_fio
    candidate.phone = _normalize_phone(phone)
    candidate.city = city.name_plain
    candidate.last_activity = _utcnow()
    await upsert_step_state(
        session,
        journey,
        step_key="profile",
        status=CandidateJourneyStepStatus.COMPLETED.value,
        payload={
            "fio": candidate.fio,
            "phone": candidate.phone,
            "city_id": city.id,
            "city_name": city.name_plain,
        },
    )


def _normalize_screening_answers(answers: dict[str, Any]) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for key, value in answers.items():
        question_key = str(key or "").strip()
        if not question_key:
            continue
        text = str(value or "").strip()
        if text:
            normalized[question_key] = text
    return normalized


def validate_screening_answers(answers: dict[str, Any]) -> dict[str, str]:
    normalized = _normalize_screening_answers(answers)
    questions = get_candidate_portal_questions()
    required_fields = [str(item["id"]) for item in questions]
    missing = [field for field in required_fields if not normalized.get(field)]
    if missing:
        raise CandidatePortalError("Заполните все вопросы анкеты.")

    age_raw = normalized.get("age")
    if age_raw is not None:
        try:
            normalized["age"] = str(convert_age(age_raw))
            apply_partial_validation({"age": int(normalized["age"])})
        except Exception as exc:
            raise CandidatePortalError(str(exc)) from exc

    return normalized


async def save_screening_draft(
    session: AsyncSession,
    journey: CandidateJourneySession,
    *,
    answers: dict[str, Any],
) -> None:
    normalized = _normalize_screening_answers(answers)
    await upsert_step_state(
        session,
        journey,
        step_key="screening",
        status=CandidateJourneyStepStatus.IN_PROGRESS.value,
        payload=normalized,
    )


async def complete_screening(
    session: AsyncSession,
    candidate: User,
    journey: CandidateJourneySession,
    *,
    answers: dict[str, Any],
    source_channel: str = "candidate_portal",
) -> TestResult:
    normalized = validate_screening_answers(answers)
    now = _utcnow()
    normalized_source = (source_channel or "candidate_portal").strip() or "candidate_portal"

    question_data = []
    for index, question in enumerate(get_candidate_portal_questions(), start=1):
        question_key = str(question["id"])
        answer = normalized.get(question_key, "")
        question_data.append(
            {
                "question_index": index,
                "question_text": question["prompt"],
                "correct_answer": None,
                "user_answer": answer,
                "attempts_count": 1 if answer else 0,
                "time_spent": 0,
                "is_correct": True,
                "overtime": False,
            }
        )

    test_result = TestResult(
        user_id=candidate.id,
        raw_score=len(question_data),
        final_score=float(len(question_data)),
        rating="TEST1",
        source=normalized_source,
        total_time=0,
        created_at=now,
    )
    session.add(test_result)
    await session.flush()

    for item in question_data:
        session.add(
            QuestionAnswer(
                test_result_id=test_result.id,
                question_index=int(item["question_index"]),
                question_text=str(item["question_text"]),
                correct_answer=item["correct_answer"],
                user_answer=item["user_answer"],
                attempts_count=int(item["attempts_count"]),
                time_spent=int(item["time_spent"]),
                is_correct=bool(item["is_correct"]),
                overtime=bool(item["overtime"]),
            )
        )

    candidate.last_activity = now
    await _status_service.force(
        candidate,
        CandidateStatus.TEST1_COMPLETED,
        reason="candidate portal screening completed",
    )
    await _status_service.force(
        candidate,
        CandidateStatus.WAITING_SLOT,
        reason="candidate portal waiting for slot",
    )
    await upsert_step_state(
        session,
        journey,
        step_key="screening",
        status=CandidateJourneyStepStatus.COMPLETED.value,
        payload=normalized,
    )
    await analytics.log_funnel_event(
        analytics.FunnelEvent.TEST1_COMPLETED,
        user_id=candidate.telegram_id or candidate.telegram_user_id,
        candidate_id=candidate.id,
        metadata={"result": "passed", "channel": normalized_source},
        session=session,
    )
    return test_result


async def create_candidate_portal_message(
    session: AsyncSession,
    candidate: User,
    *,
    text: str,
) -> ChatMessage:
    clean_text = (text or "").strip()
    if not clean_text:
        raise CandidatePortalError("Введите сообщение для рекрутера.")
    message = ChatMessage(
        candidate_id=candidate.id,
        telegram_user_id=candidate.telegram_user_id or candidate.telegram_id,
        direction=ChatMessageDirection.INBOUND.value,
        channel="candidate_portal",
        text=clean_text,
        payload_json={
            "origin_channel": "web",
            "delivery_channels": ["web"],
            "author_role": "candidate",
        },
        status=ChatMessageStatus.RECEIVED.value,
        author_label=candidate.fio if not _is_placeholder_fio(candidate.fio) else "Кандидат",
    )
    candidate.last_activity = _utcnow()
    session.add(message)
    await session.flush()
    return message


async def ensure_candidate_waiting_slot(
    session: AsyncSession,
    candidate: User,
) -> None:
    target = CandidateStatus.WAITING_SLOT
    if candidate.candidate_status != target:
        await _status_service.force(
            candidate,
            target,
            reason="candidate portal slot released",
        )


async def ensure_candidate_slot_pending(
    session: AsyncSession,
    candidate: User,
) -> None:
    target = CandidateStatus.SLOT_PENDING
    if candidate.candidate_status != target:
        await _status_service.force(
            candidate,
            target,
            reason="candidate portal slot reserved",
        )


async def ensure_candidate_slot_confirmed(
    session: AsyncSession,
    candidate: User,
) -> None:
    target = CandidateStatus.INTERVIEW_CONFIRMED
    if candidate.candidate_status != target:
        await _status_service.force(
            candidate,
            target,
            reason="candidate portal slot confirmed",
        )


def resolve_candidate_timezone(*, city: City | None, candidate: User) -> str:
    return (
        (city.tz if city and city.tz else None)
        or candidate.manual_slot_timezone
        or DEFAULT_TZ
    )


def _dialect_name(session: AsyncSession) -> str:
    bind = session.get_bind()
    return bind.dialect.name if bind is not None else ""


async def reserve_candidate_portal_slot(
    session: AsyncSession,
    candidate: User,
    journey: CandidateJourneySession,
    *,
    slot_id: int,
) -> dict[str, Any]:
    city = await _resolve_city(session, city_name=candidate.city)
    if city is None:
        raise CandidatePortalError("Сначала укажите город кандидата.")

    reserved_slot: Slot | None = None
    if _dialect_name(session) == "sqlite":
        existing_active = await get_candidate_active_slot(session, candidate)
        if existing_active is not None and existing_active.id != slot_id:
            raise CandidatePortalError("У вас уже есть активная запись на собеседование.")

        slot = await session.scalar(
            select(Slot)
            .options(selectinload(Slot.recruiter), selectinload(Slot.city))
            .where(Slot.id == slot_id)
        )
        if slot is None:
            raise CandidatePortalError("Слот не найден.")
        if (slot.status or "").lower() != SlotStatus.FREE or slot.candidate_id or slot.candidate_tg_id:
            raise CandidatePortalError("Слот уже занят. Обновите список и выберите другое время.")

        slot.status = SlotStatus.PENDING
        slot.candidate_id = candidate.candidate_id
        slot.candidate_tg_id = candidate.telegram_user_id or candidate.telegram_id
        slot.candidate_fio = candidate.fio
        slot.candidate_tz = resolve_candidate_timezone(city=city, candidate=candidate)
        slot.candidate_city_id = city.id
        slot.purpose = "interview"
        reserved_slot = slot
        await session.flush()
    else:
        reservation = await reserve_slot(
            slot_id,
            candidate.telegram_user_id or candidate.telegram_id,
            candidate.fio,
            resolve_candidate_timezone(city=city, candidate=candidate),
            candidate_id=candidate.candidate_id,
            candidate_city_id=city.id,
            candidate_username=candidate.username or candidate.telegram_username,
            purpose="interview",
        )
        if reservation.status != "reserved" or reservation.slot is None:
            error_messages = {
                "slot_taken": "Слот уже занят. Обновите список и выберите другое время.",
                "duplicate_candidate": "У вас уже есть активная запись на собеседование.",
                "already_reserved": "Этот слот уже закреплен за вами.",
                "not_found": "Слот не найден.",
            }
            raise CandidatePortalError(error_messages.get(reservation.status, "Не удалось забронировать слот."))
        reserved_slot = reservation.slot

    candidate.responsible_recruiter_id = reserved_slot.recruiter_id if reserved_slot else candidate.responsible_recruiter_id
    await ensure_candidate_slot_pending(session, candidate)
    await upsert_step_state(
        session,
        journey,
        step_key="slot_selection",
        step_type="schedule",
        status=CandidateJourneyStepStatus.COMPLETED.value,
        payload={"slot_id": reserved_slot.id if reserved_slot else slot_id, "action": "reserve"},
    )
    await analytics.log_slot_booked(
        user_id=candidate.telegram_id or candidate.telegram_user_id or candidate.id,
        candidate_id=candidate.id,
        slot_id=reserved_slot.id if reserved_slot else slot_id,
        booking_id=reserved_slot.id if reserved_slot else slot_id,
        city_id=reserved_slot.city_id if reserved_slot else city.id,
        metadata={"source": "candidate_portal"},
    )
    return serialize_portal_slot(reserved_slot) if reserved_slot else {"id": slot_id}


async def confirm_candidate_portal_slot(
    session: AsyncSession,
    candidate: User,
    journey: CandidateJourneySession,
) -> dict[str, Any]:
    active_slot = await get_candidate_active_slot(session, candidate)
    if active_slot is None:
        raise CandidatePortalError("Активный слот не найден.")

    slot = active_slot
    if _dialect_name(session) == "sqlite":
        status_value = (active_slot.status or "").lower()
        if status_value in {SlotStatus.CONFIRMED, SlotStatus.CONFIRMED_BY_CANDIDATE}:
            slot = active_slot
        elif status_value not in {SlotStatus.PENDING, SlotStatus.BOOKED}:
            raise CandidatePortalError("Слот нельзя подтвердить в текущем статусе.")
        else:
            active_slot.status = SlotStatus.CONFIRMED_BY_CANDIDATE
            slot = active_slot
            await session.flush()
    else:
        result = await confirm_slot_by_candidate(active_slot.id)
        slot = result.slot if result and result.slot is not None else active_slot
        if result.status not in {"already_confirmed", "confirmed"}:
            raise CandidatePortalError("Слот нельзя подтвердить в текущем статусе.")

    await ensure_candidate_slot_confirmed(session, candidate)
    await upsert_step_state(
        session,
        journey,
        step_key="status",
        step_type="status",
        status=CandidateJourneyStepStatus.IN_PROGRESS.value,
        payload={"slot_id": slot.id, "action": "confirm"},
    )
    await analytics.log_funnel_event(
        analytics.FunnelEvent.SLOT_CONFIRMED,
        user_id=candidate.telegram_id or candidate.telegram_user_id,
        candidate_id=candidate.id,
        slot_id=slot.id,
        booking_id=slot.id,
        metadata={"source": "candidate_portal"},
        session=session,
    )
    return serialize_portal_slot(slot)


async def cancel_candidate_portal_slot(
    session: AsyncSession,
    candidate: User,
    journey: CandidateJourneySession,
) -> dict[str, Any]:
    active_slot = await get_candidate_active_slot(session, candidate)
    if active_slot is None:
        raise CandidatePortalError("Активный слот не найден.")

    released_slot_id = active_slot.id
    if _dialect_name(session) == "sqlite":
        active_slot.status = SlotStatus.FREE
        active_slot.candidate_id = None
        active_slot.candidate_tg_id = None
        active_slot.candidate_fio = None
        active_slot.candidate_tz = None
        active_slot.candidate_city_id = None
        active_slot.purpose = "interview"
        await session.flush()
    else:
        await reject_slot(released_slot_id)
    await ensure_candidate_waiting_slot(session, candidate)
    await upsert_step_state(
        session,
        journey,
        step_key="slot_selection",
        step_type="schedule",
        status=CandidateJourneyStepStatus.IN_PROGRESS.value,
        payload={"released_slot_id": released_slot_id, "action": "cancel"},
    )
    await analytics.log_slot_canceled(
        user_id=candidate.telegram_id or candidate.telegram_user_id or candidate.id,
        candidate_id=candidate.id,
        booking_id=released_slot_id,
        slot_id=released_slot_id,
        reason="candidate_portal_cancel",
        metadata={"source": "candidate_portal"},
    )
    return {"released_slot_id": released_slot_id}


async def reschedule_candidate_portal_slot(
    session: AsyncSession,
    candidate: User,
    journey: CandidateJourneySession,
    *,
    new_slot_id: int,
) -> dict[str, Any]:
    active_slot = await get_candidate_active_slot(session, candidate)
    if active_slot is None:
        raise CandidatePortalError("Текущий слот не найден.")

    city = await _resolve_city(session, city_name=candidate.city)
    if city is None:
        raise CandidatePortalError("Сначала укажите город кандидата.")

    replacement = await session.scalar(
        select(Slot)
        .options(selectinload(Slot.recruiter), selectinload(Slot.city))
        .where(Slot.id == new_slot_id)
        .with_for_update()
    )
    if replacement is None:
        raise CandidatePortalError("Новый слот не найден.")
    if (replacement.status or "").lower() != SlotStatus.FREE:
        raise CandidatePortalError("Новый слот уже занят.")
    if replacement.id == active_slot.id:
        raise CandidatePortalError("Выберите другой слот для переноса.")

    old_slot_id = active_slot.id
    if _dialect_name(session) == "sqlite":
        active_slot.status = SlotStatus.FREE
        active_slot.candidate_id = None
        active_slot.candidate_tg_id = None
        active_slot.candidate_fio = None
        active_slot.candidate_tz = None
        active_slot.candidate_city_id = None
        active_slot.purpose = "interview"
        replacement.status = SlotStatus.PENDING
        replacement.candidate_id = candidate.candidate_id
        replacement.candidate_tg_id = candidate.telegram_user_id or candidate.telegram_id
        replacement.candidate_fio = candidate.fio
        replacement.candidate_tz = resolve_candidate_timezone(city=city, candidate=candidate)
        replacement.candidate_city_id = city.id
        replacement.purpose = "interview"
        await session.flush()
    else:
        await reject_slot(old_slot_id)
        replacement.status = SlotStatus.PENDING
        replacement.candidate_id = candidate.candidate_id
        replacement.candidate_tg_id = candidate.telegram_user_id or candidate.telegram_id
        replacement.candidate_fio = candidate.fio
        replacement.candidate_tz = resolve_candidate_timezone(city=city, candidate=candidate)
        replacement.candidate_city_id = city.id
        replacement.purpose = "interview"

    candidate.responsible_recruiter_id = replacement.recruiter_id
    await ensure_candidate_slot_pending(session, candidate)
    await upsert_step_state(
        session,
        journey,
        step_key="slot_selection",
        step_type="schedule",
        status=CandidateJourneyStepStatus.COMPLETED.value,
        payload={"slot_id": replacement.id, "previous_slot_id": old_slot_id, "action": "reschedule"},
    )
    await analytics.log_slot_rescheduled(
        user_id=candidate.telegram_id or candidate.telegram_user_id or candidate.id,
        candidate_id=candidate.id,
        old_booking_id=old_slot_id,
        new_booking_id=replacement.id,
        new_slot_id=replacement.id,
        metadata={"source": "candidate_portal"},
    )
    return serialize_portal_slot(replacement)
