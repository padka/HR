from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Iterable, Optional, Tuple
from zoneinfo import ZoneInfo

from backend.core.settings import get_settings

logger = logging.getLogger(__name__)

MAX_INTRO_DAY_HANDOFF_ENABLED_ENV = "MAX_INTRO_DAY_HANDOFF_ENABLED"
MAX_INTRO_DAY_GROUP_ROUTES_ENV = "MAX_INTRO_DAY_GROUP_ROUTES"


@dataclass(frozen=True)
class IntroDayHandoffContext:
    candidate_id: int
    candidate_fio: str
    slot_id: int
    slot_start_utc: datetime
    slot_tz: str
    recruiter_id: Optional[int] = None
    recruiter_name: Optional[str] = None
    city_id: Optional[int] = None
    city_name: Optional[str] = None
    candidate_card_url: Optional[str] = None
    hh_profile_url: Optional[str] = None


@dataclass(frozen=True)
class _RouteConfig:
    recruiters: Dict[str, list[str]]
    cities: Dict[str, list[str]]
    city_names: Dict[str, list[str]]
    default_targets: list[str]


def _is_enabled() -> bool:
    raw = os.getenv(MAX_INTRO_DAY_HANDOFF_ENABLED_ENV)
    if raw is None:
        return False
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _normalize_targets(value: Any) -> list[str]:
    raw_items: list[str] = []
    if value is None:
        return raw_items
    if isinstance(value, (str, int)):
        candidate = str(value).strip()
        return [candidate] if candidate else []
    if isinstance(value, Iterable):
        for item in value:
            if item is None:
                continue
            candidate = str(item).strip()
            if candidate:
                raw_items.append(candidate)
    deduped: list[str] = []
    seen: set[str] = set()
    for item in raw_items:
        if item in seen:
            continue
        seen.add(item)
        deduped.append(item)
    return deduped


def _parse_routes(raw: str) -> _RouteConfig:
    recruiters: Dict[str, list[str]] = {}
    cities: Dict[str, list[str]] = {}
    city_names: Dict[str, list[str]] = {}
    default_targets: list[str] = []

    payload: Any = {}
    if raw.strip():
        try:
            payload = json.loads(raw)
        except Exception:
            logger.warning(
                "max.intro_day_handoff.invalid_routes_json",
                extra={"env": MAX_INTRO_DAY_GROUP_ROUTES_ENV},
            )
            payload = {}
    if not isinstance(payload, dict):
        return _RouteConfig(recruiters=recruiters, cities=cities, city_names=city_names, default_targets=default_targets)

    default_targets = _normalize_targets(payload.get("default"))

    recruiter_map = payload.get("recruiters")
    if isinstance(recruiter_map, dict):
        for key, value in recruiter_map.items():
            targets = _normalize_targets(value)
            if not targets:
                continue
            recruiter_key = str(key).strip()
            if recruiter_key:
                recruiters[recruiter_key] = targets

    city_map = payload.get("cities")
    if isinstance(city_map, dict):
        for key, value in city_map.items():
            targets = _normalize_targets(value)
            if not targets:
                continue
            city_key = str(key).strip()
            if not city_key:
                continue
            if city_key.isdigit():
                cities[city_key] = targets
            else:
                city_names[city_key.lower()] = targets

    city_name_map = payload.get("city_names")
    if isinstance(city_name_map, dict):
        for key, value in city_name_map.items():
            targets = _normalize_targets(value)
            if not targets:
                continue
            city_name_key = str(key).strip().lower()
            if city_name_key:
                city_names[city_name_key] = targets

    return _RouteConfig(
        recruiters=recruiters,
        cities=cities,
        city_names=city_names,
        default_targets=default_targets,
    )


def _resolve_targets(
    config: _RouteConfig,
    *,
    recruiter_id: Optional[int],
    city_id: Optional[int],
    city_name: Optional[str],
) -> Tuple[Optional[str], list[str]]:
    if recruiter_id is not None:
        recruiter_key = str(int(recruiter_id))
        targets = config.recruiters.get(recruiter_key)
        if targets:
            return f"recruiter:{recruiter_key}", targets

    if city_id is not None:
        city_key = str(int(city_id))
        targets = config.cities.get(city_key)
        if targets:
            return f"city:{city_key}", targets

    city_name_key = (city_name or "").strip().lower()
    if city_name_key:
        targets = config.city_names.get(city_name_key)
        if targets:
            return f"city_name:{city_name_key}", targets

    if config.default_targets:
        return "default", config.default_targets

    return None, []


def _format_slot_local(start_utc: datetime, tz_name: str) -> str:
    local_dt = start_utc
    if start_utc.tzinfo is None:
        local_dt = start_utc.replace(tzinfo=ZoneInfo("UTC"))
    try:
        local_dt = local_dt.astimezone(ZoneInfo(tz_name))
    except Exception:
        pass
    return local_dt.strftime("%d.%m.%Y %H:%M")


def _build_message(context: IntroDayHandoffContext) -> str:
    lines = [
        "📥 <b>Новый кандидат на ознакомительный день</b>",
        f"👤 Кандидат: <b>{context.candidate_fio or f'#{context.candidate_id}'}</b>",
        f"🆔 CRM ID: {context.candidate_id}",
        f"🗓 ОД: {_format_slot_local(context.slot_start_utc, context.slot_tz)} ({context.slot_tz})",
    ]
    if context.city_name:
        lines.append(f"🏙 Город: {context.city_name}")
    if context.recruiter_name:
        lines.append(f"🧑‍💼 Рекрутёр: {context.recruiter_name}")
    if context.hh_profile_url:
        lines.append(f"📄 Резюме: {context.hh_profile_url}")
    if context.candidate_card_url:
        lines.append(f"🔗 Карточка кандидата: {context.candidate_card_url}")
    lines.append(
        "ℹ️ Канал служебный: общение с кандидатом ведёт рекрутёр, группа продаж получает только контекст по ОД."
    )
    return "\n".join(lines)


async def _ensure_max_adapter(*, bot: Optional[Any] = None):
    from backend.core.messenger.protocol import MessengerPlatform
    from backend.core.messenger.registry import get_registry

    registry = get_registry()
    adapter = registry.get(MessengerPlatform.MAX)
    if adapter is not None:
        return adapter

    settings = get_settings()
    if not settings.max_bot_enabled or not settings.max_bot_token:
        return None

    try:
        from backend.core.messenger.bootstrap import bootstrap_messenger_adapters

        await bootstrap_messenger_adapters(
            bot=bot,
            max_bot_enabled=settings.max_bot_enabled,
            max_bot_token=settings.max_bot_token,
        )
    except Exception:
        logger.exception("max.intro_day_handoff.bootstrap_failed")
        return None

    return get_registry().get(MessengerPlatform.MAX)


async def dispatch_intro_day_handoff_to_max(
    context: IntroDayHandoffContext,
    *,
    bot: Optional[Any] = None,
) -> dict[str, Any]:
    settings = get_settings()
    if not settings.max_bot_enabled:
        return {"ok": False, "status": "skipped:max_disabled"}
    if not _is_enabled():
        return {"ok": False, "status": "skipped:feature_disabled"}

    route_config = _parse_routes(os.getenv(MAX_INTRO_DAY_GROUP_ROUTES_ENV, ""))
    route_key, targets = _resolve_targets(
        route_config,
        recruiter_id=context.recruiter_id,
        city_id=context.city_id,
        city_name=context.city_name,
    )
    if not targets:
        return {"ok": False, "status": "skipped:no_route"}

    adapter = await _ensure_max_adapter(bot=bot)
    if adapter is None:
        return {"ok": False, "status": "skipped:adapter_unavailable", "route": route_key}

    correlation_id = f"intro_day_handoff:{context.slot_id}:{context.candidate_id}"
    text = _build_message(context)
    sent = 0
    failed = 0
    errors: list[str] = []

    for target in targets:
        try:
            result = await adapter.send_message(
                target,
                text,
                parse_mode="HTML",
                correlation_id=correlation_id,
            )
        except Exception as exc:
            failed += 1
            error = f"{target}: {exc.__class__.__name__}: {exc}"
            errors.append(error)
            logger.exception(
                "max.intro_day_handoff.send_exception",
                extra={
                    "target": target,
                    "candidate_id": context.candidate_id,
                    "slot_id": context.slot_id,
                    "route": route_key,
                },
            )
            continue

        if getattr(result, "success", False):
            sent += 1
            continue

        failed += 1
        error_value = getattr(result, "error", None) or "unknown_error"
        errors.append(f"{target}: {error_value}")
        logger.warning(
            "max.intro_day_handoff.send_failed",
            extra={
                "target": target,
                "candidate_id": context.candidate_id,
                "slot_id": context.slot_id,
                "route": route_key,
                "error": error_value,
            },
        )

    status = "failed"
    if sent > 0 and failed == 0:
        status = "sent"
    elif sent > 0:
        status = "partial"

    payload = {
        "ok": status == "sent",
        "status": status,
        "route": route_key,
        "targets_total": len(targets),
        "targets_sent": sent,
        "targets_failed": failed,
    }
    if errors:
        payload["errors"] = errors
    return payload


__all__ = [
    "IntroDayHandoffContext",
    "dispatch_intro_day_handoff_to_max",
]

