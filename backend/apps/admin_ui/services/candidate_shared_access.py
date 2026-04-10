"""Shared candidate portal access via phone + one-time code."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import hmac
import json
import logging
import secrets
from typing import Any

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.apps.admin_ui.services.bot_service import get_bot_service
from backend.core.cache import get_cache
from backend.core.messenger.protocol import MessengerPlatform
from backend.core.messenger.registry import get_registry
from backend.core.settings import get_settings
from backend.domain.candidates.models import User
from backend.domain.candidates.phones import normalize_candidate_phone
from backend.domain.candidates.portal_service import (
    _mark_journey_event_once,
    build_candidate_portal_journey,
    ensure_candidate_portal_session,
)
from backend.domain.hh_integration import HHApiClient, HHApiError, decrypt_access_token
from backend.domain.hh_integration.models import CandidateExternalIdentity, HHConnection, HHNegotiation

logger = logging.getLogger(__name__)

SHARED_ACCESS_CHALLENGE_TTL_SECONDS = 10 * 60
SHARED_ACCESS_RESEND_COOLDOWN_SECONDS = 60
SHARED_ACCESS_MAX_ATTEMPTS = 5
SHARED_ACCESS_CODE_LENGTH = 6
SHARED_ACCESS_TOKEN_SALT = "candidate-shared-access"
SHARED_ACCESS_STORE_PREFIX = "candidate:shared_access:challenge:"
SHARED_ACCESS_PHONE_PREFIX = "candidate:shared_access:phone:"
SHARED_ACCESS_METRIC_PREFIX = "candidate:shared_access:metric:"

_memory_store: dict[str, tuple[float, dict[str, Any]]] = {}
_memory_counters: dict[str, int] = {}


class CandidateSharedAccessError(ValueError):
    """Raised when shared candidate portal access is invalid."""

    def __init__(self, message: str, *, code: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class CandidateSharedAccessChallenge:
    token: str
    expires_in_seconds: int
    retry_after_seconds: int


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _serializer() -> URLSafeTimedSerializer:
    settings = get_settings()
    return URLSafeTimedSerializer(settings.session_secret, salt=SHARED_ACCESS_TOKEN_SALT)


def _phone_hash(phone: str) -> str:
    return hashlib.sha256(phone.encode("utf-8")).hexdigest()


def _challenge_key(challenge_id: str) -> str:
    return f"{SHARED_ACCESS_STORE_PREFIX}{challenge_id}"


def _phone_index_key(phone_hash: str) -> str:
    return f"{SHARED_ACCESS_PHONE_PREFIX}{phone_hash}"


def _cleanup_memory_store() -> None:
    now = _utcnow().timestamp()
    expired = [key for key, (expires_at, _) in _memory_store.items() if expires_at <= now]
    for key in expired:
        _memory_store.pop(key, None)


def _cache_client():
    try:
        cache = get_cache()
    except RuntimeError:
        return None
    return getattr(cache, "client", None)


def _shared_access_requires_redis() -> bool:
    settings = get_settings()
    return settings.environment == "production"


def _shared_access_store_backend() -> str:
    return "redis" if _cache_client() is not None else "memory"


def _shared_access_store_ready() -> bool:
    if not _shared_access_requires_redis():
        return True
    return _cache_client() is not None


def _metric_key(name: str, label: str | None = None) -> str:
    suffix = str(name or "").strip().lower().replace(" ", "_") or "unknown"
    if label:
        normalized_label = "".join(
            ch if ch.isalnum() or ch in {"_", "-", ":"} else "_"
            for ch in str(label).strip().lower()
        ).strip("_") or "unknown"
        suffix = f"{suffix}:{normalized_label}"
    return f"{SHARED_ACCESS_METRIC_PREFIX}{suffix}"


async def _store_json(key: str, payload: dict[str, Any], ttl_seconds: int) -> None:
    client = _cache_client()
    if client is not None:
        await client.setex(key, ttl_seconds, json.dumps(payload, ensure_ascii=True, default=str))
        return
    _cleanup_memory_store()
    _memory_store[key] = (_utcnow().timestamp() + ttl_seconds, dict(payload))


async def _load_json(key: str) -> dict[str, Any] | None:
    client = _cache_client()
    if client is not None:
        raw = await client.get(key)
        if not raw:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8", "ignore")
        try:
            payload = json.loads(str(raw))
        except Exception:
            return None
        return payload if isinstance(payload, dict) else None
    _cleanup_memory_store()
    item = _memory_store.get(key)
    if not item:
        return None
    _, payload = item
    return dict(payload)


async def _delete_key(key: str) -> None:
    client = _cache_client()
    if client is not None:
        await client.delete(key)
        return
    _memory_store.pop(key, None)


async def _increment_metric(name: str, *, label: str | None = None, amount: int = 1) -> None:
    key = _metric_key(name, label)
    client = _cache_client()
    if client is not None:
        await client.incrby(key, int(amount))
        return
    _memory_counters[key] = int(_memory_counters.get(key, 0) or 0) + int(amount)


async def _read_metric(name: str, *, label: str | None = None) -> int:
    key = _metric_key(name, label)
    client = _cache_client()
    if client is not None:
        raw = await client.get(key)
        if raw is None:
            return 0
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8", "ignore")
        try:
            return int(str(raw).strip() or "0")
        except Exception:
            return 0
    return int(_memory_counters.get(key, 0) or 0)


async def find_candidate_by_phone(session: AsyncSession, phone: str) -> User | None:
    normalized = normalize_candidate_phone(phone)
    if not normalized:
        raise CandidateSharedAccessError(
            "Укажите телефон в формате +7XXXXXXXXXX.",
            code="candidate_shared_access_phone_invalid",
        )
    result = await session.execute(
        select(User)
        .where(
            User.is_active.is_(True),
            User.phone_normalized == normalized,
        )
        .order_by(User.last_activity.desc(), User.id.desc())
        .limit(3)
    )
    matches = list(result.scalars().all())
    if len(matches) != 1:
        return None
    return matches[0]


def _sign_code(challenge_id: str, code: str) -> str:
    settings = get_settings()
    return hmac.new(
        settings.session_secret.encode("utf-8"),
        f"{challenge_id}:{code}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _sign_challenge_token(challenge_id: str) -> str:
    return str(_serializer().dumps({"id": challenge_id}))


def _parse_challenge_token(token: str) -> str:
    raw = str(token or "").strip()
    if not raw:
        raise CandidateSharedAccessError(
            "Код входа устарел. Запросите новый код.",
            code="candidate_shared_access_challenge_invalid",
        )
    try:
        payload = _serializer().loads(raw, max_age=SHARED_ACCESS_CHALLENGE_TTL_SECONDS)
    except SignatureExpired as exc:
        raise CandidateSharedAccessError(
            "Код входа устарел. Запросите новый код.",
            code="candidate_shared_access_challenge_expired",
        ) from exc
    except BadSignature as exc:
        raise CandidateSharedAccessError(
            "Код входа недействителен.",
            code="candidate_shared_access_challenge_invalid",
        ) from exc
    challenge_id = str(payload.get("id") or "").strip() if isinstance(payload, dict) else ""
    if not challenge_id:
        raise CandidateSharedAccessError(
            "Код входа недействителен.",
            code="candidate_shared_access_challenge_invalid",
        )
    return challenge_id


def _iter_hh_actions_snapshot(actions_snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    actions = actions_snapshot.get("actions")
    if not isinstance(actions, list):
        return []
    return [item for item in actions if isinstance(item, dict)]


def _flatten_hh_actions(actions_snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    flattened: list[dict[str, Any]] = []
    for action in _iter_hh_actions_snapshot(actions_snapshot):
        flattened.append(action)
        for sub_action in action.get("sub_actions") or []:
            if isinstance(sub_action, dict):
                merged = dict(sub_action)
                merged.setdefault("arguments", action.get("arguments") or [])
                merged.setdefault("resulting_employer_state", action.get("resulting_employer_state") or {})
                flattened.append(merged)
    return flattened


def _hh_message_argument_name(action: dict[str, Any]) -> str | None:
    arguments = action.get("arguments")
    if not isinstance(arguments, list):
        return None
    for item in arguments:
        if not isinstance(item, dict):
            continue
        arg_id = str(item.get("id") or "").strip().lower()
        if arg_id in {"message", "text", "body", "comment"}:
            return arg_id
    return None


def _select_hh_message_action(actions_snapshot: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    ranked: list[tuple[int, dict[str, Any], str]] = []
    for action in _flatten_hh_actions(actions_snapshot):
        if action.get("enabled") is False or action.get("hidden") is True:
            continue
        method = str(action.get("method") or "").strip().upper()
        url = str(action.get("url") or "").strip()
        if not method or not url:
            continue
        message_arg = _hh_message_argument_name(action)
        if not message_arg:
            continue
        name = str(action.get("name") or "").strip().lower()
        score = 0
        if "сообщ" in name or "message" in name or "напис" in name:
            score += 4
        if "invite" in name or "приглаш" in name:
            score += 2
        ranked.append((score, action, message_arg))
    if not ranked:
        return None, None
    ranked.sort(key=lambda item: item[0], reverse=True)
    _, action, message_arg = ranked[0]
    return action, message_arg


async def _deliver_via_hh(
    session: AsyncSession,
    *,
    candidate: User,
    message_text: str,
) -> str | None:
    identity = (
        await session.execute(
            select(CandidateExternalIdentity).where(
                CandidateExternalIdentity.candidate_id == int(candidate.id),
                CandidateExternalIdentity.source == "hh",
            )
        )
    ).scalar_one_or_none()
    if identity is None:
        return None
    negotiation = (
        await session.execute(
            select(HHNegotiation)
            .where(HHNegotiation.candidate_identity_id == identity.id)
            .order_by(HHNegotiation.updated_at.desc(), HHNegotiation.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if negotiation is None or not isinstance(negotiation.actions_snapshot, dict):
        return None
    action, message_arg = _select_hh_message_action(negotiation.actions_snapshot)
    if action is None or not message_arg or not negotiation.connection_id:
        return None
    connection = await session.get(HHConnection, int(negotiation.connection_id))
    if connection is None:
        return None
    action_url = str(action.get("url") or "").strip()
    method = str(action.get("method") or "").strip().upper()
    if not action_url or not method:
        return None
    client = HHApiClient()
    try:
        await client.execute_negotiation_action(
            decrypt_access_token(connection),
            action_url=action_url,
            method=method,
            manager_account_id=connection.manager_account_id,
            arguments={message_arg: message_text},
        )
    except HHApiError as exc:
        logger.warning(
            "candidate.shared_access.hh_delivery_failed",
            extra={"candidate_id": int(candidate.id), "error": str(exc)},
        )
        return None
    return "hh"


async def _deliver_via_telegram(
    *,
    candidate: User,
    message_text: str,
) -> str | None:
    telegram_id = candidate.telegram_user_id or candidate.telegram_id
    if not telegram_id:
        return None
    result = await get_bot_service(allow_null=True).send_chat_message(
        int(telegram_id),
        message_text,
    )
    if getattr(result, "ok", False):
        return "telegram"
    logger.warning(
        "candidate.shared_access.telegram_delivery_failed",
        extra={"candidate_id": int(candidate.id), "status": getattr(result, "status", None)},
    )
    return None


async def _deliver_via_max(
    *,
    candidate: User,
    message_text: str,
) -> str | None:
    max_user_id = str(candidate.max_user_id or "").strip()
    if not max_user_id:
        return None
    adapter = get_registry().get(MessengerPlatform.MAX)
    if adapter is None:
        return None
    result = await adapter.send_message(
        max_user_id,
        message_text,
        correlation_id=f"candidate-shared-access:{candidate.id}",
    )
    if getattr(result, "ok", False) or getattr(result, "success", False):
        return "max"
    logger.warning(
        "candidate.shared_access.max_delivery_failed",
        extra={"candidate_id": int(candidate.id), "status": getattr(result, "status", None)},
    )
    return None


async def deliver_candidate_shared_access_code(
    session: AsyncSession,
    *,
    candidate: User,
    code: str,
) -> str | None:
    message_text = "\n".join(
        [
            "Код входа в кабинет Attila Recruiting:",
            code,
            f"Код действует {SHARED_ACCESS_CHALLENGE_TTL_SECONDS // 60} минут и нужен только для входа на сайте.",
            "Никому его не сообщайте.",
        ]
    )
    for channel in ("hh", "telegram", "max"):
        if channel == "hh":
            delivered = await _deliver_via_hh(session, candidate=candidate, message_text=message_text)
        elif channel == "telegram":
            delivered = await _deliver_via_telegram(candidate=candidate, message_text=message_text)
        else:
            delivered = await _deliver_via_max(candidate=candidate, message_text=message_text)
        if delivered:
            return delivered
    return None


async def start_candidate_shared_access_challenge(
    session: AsyncSession,
    *,
    phone: str,
) -> CandidateSharedAccessChallenge:
    normalized_phone = normalize_candidate_phone(phone)
    if not normalized_phone:
        raise CandidateSharedAccessError(
            "Укажите телефон в формате +7XXXXXXXXXX.",
            code="candidate_shared_access_phone_invalid",
        )
    if not _shared_access_store_ready():
        raise CandidateSharedAccessError(
            "Вход в кабинет временно недоступен. Попробуйте позже.",
            code="candidate_shared_access_temporarily_unavailable",
        )
    phone_hash = _phone_hash(normalized_phone)
    now_ts = int(_utcnow().timestamp())
    existing_index = await _load_json(_phone_index_key(phone_hash))
    if isinstance(existing_index, dict):
        existing_challenge_id = str(existing_index.get("challenge_id") or "").strip()
        retry_after = max(0, int(existing_index.get("retry_after") or 0) - now_ts)
        if existing_challenge_id and retry_after > 0:
            await _increment_metric("challenge_rate_limited")
            record = await _load_json(_challenge_key(existing_challenge_id))
            if isinstance(record, dict):
                return CandidateSharedAccessChallenge(
                    token=_sign_challenge_token(existing_challenge_id),
                    expires_in_seconds=max(60, int(record.get("expires_at") or now_ts + SHARED_ACCESS_CHALLENGE_TTL_SECONDS) - now_ts),
                    retry_after_seconds=retry_after,
                )

    candidate = await find_candidate_by_phone(session, normalized_phone)
    challenge_id = secrets.token_urlsafe(16)
    code = f"{secrets.randbelow(10**SHARED_ACCESS_CODE_LENGTH):0{SHARED_ACCESS_CODE_LENGTH}d}"
    delivery_channel = None
    journey_id = None
    session_version = None
    delivery_block_reason = None

    if candidate is not None:
        journey = await ensure_candidate_portal_session(session, candidate, entry_channel="web")
        journey_id = int(journey.id)
        session_version = int(journey.session_version or 1)
        delivery_channel = await deliver_candidate_shared_access_code(
            session,
            candidate=candidate,
            code=code,
        )
        journey_meta = dict(journey.payload_json or {}) if isinstance(journey.payload_json, dict) else {}
        journey_meta["shared_portal_last_challenge_at"] = _utcnow().isoformat()
        journey_meta["shared_portal_last_phone_hash"] = phone_hash[:12]
        if delivery_channel:
            journey_meta["shared_portal_last_delivery_channel"] = delivery_channel
            journey_meta["shared_portal_block_reason"] = None
        else:
            delivery_block_reason = "shared_access_delivery_unavailable"
            journey_meta["shared_portal_block_reason"] = delivery_block_reason
        journey.payload_json = journey_meta
        await session.flush()
    else:
        delivery_block_reason = "candidate_not_found_or_ambiguous"

    expires_at = now_ts + SHARED_ACCESS_CHALLENGE_TTL_SECONDS
    record = {
        "candidate_id": int(candidate.id) if candidate is not None and delivery_channel else None,
        "journey_session_id": journey_id if delivery_channel else None,
        "session_version": session_version if delivery_channel else None,
        "phone_hash": phone_hash,
        "delivery_channel": delivery_channel,
        "code_hash": _sign_code(challenge_id, code if delivery_channel else secrets.token_hex(4)),
        "attempts": 0,
        "expires_at": expires_at,
    }
    await _store_json(_challenge_key(challenge_id), record, SHARED_ACCESS_CHALLENGE_TTL_SECONDS)
    await _store_json(
        _phone_index_key(phone_hash),
        {
            "challenge_id": challenge_id,
            "retry_after": now_ts + SHARED_ACCESS_RESEND_COOLDOWN_SECONDS,
        },
        SHARED_ACCESS_CHALLENGE_TTL_SECONDS,
    )
    logger.info(
        "candidate.shared_access.challenge_created",
        extra={
            "candidate_id": int(candidate.id) if candidate is not None else None,
            "phone_hash": phone_hash[:12],
            "delivery_channel": delivery_channel,
        },
    )
    await _increment_metric("challenge_started")
    if delivery_channel:
        await _increment_metric("delivery_channel_used", label=delivery_channel)
    elif delivery_block_reason:
        await _increment_metric("delivery_block_reason", label=delivery_block_reason)
    return CandidateSharedAccessChallenge(
        token=_sign_challenge_token(challenge_id),
        expires_in_seconds=SHARED_ACCESS_CHALLENGE_TTL_SECONDS,
        retry_after_seconds=SHARED_ACCESS_RESEND_COOLDOWN_SECONDS,
    )


async def verify_candidate_shared_access_code(
    session: AsyncSession,
    *,
    challenge_token: str,
    code: str,
) -> tuple[User, Any, dict[str, Any]]:
    challenge_id = _parse_challenge_token(challenge_token)
    record = await _load_json(_challenge_key(challenge_id))
    if not isinstance(record, dict):
        await _increment_metric("verify_expired")
        raise CandidateSharedAccessError(
            "Код входа устарел. Запросите новый код.",
            code="candidate_shared_access_challenge_expired",
        )
    attempts = int(record.get("attempts") or 0)
    if attempts >= SHARED_ACCESS_MAX_ATTEMPTS:
        await _delete_key(_challenge_key(challenge_id))
        await _increment_metric("verify_failed")
        raise CandidateSharedAccessError(
            "Попытки входа исчерпаны. Запросите новый код.",
            code="candidate_shared_access_attempts_exceeded",
        )
    candidate_id = int(record.get("candidate_id") or 0)
    code_hash = str(record.get("code_hash") or "")
    normalized_code = "".join(ch for ch in str(code or "") if ch.isdigit())
    if not normalized_code or not hmac.compare_digest(code_hash, _sign_code(challenge_id, normalized_code)):
        record["attempts"] = attempts + 1
        if int(record["attempts"]) >= SHARED_ACCESS_MAX_ATTEMPTS:
            await _delete_key(_challenge_key(challenge_id))
        else:
            ttl = max(1, int(record.get("expires_at") or 0) - int(_utcnow().timestamp()))
            await _store_json(_challenge_key(challenge_id), record, ttl)
        await _increment_metric("verify_failed")
        raise CandidateSharedAccessError(
            "Код не подошёл или уже истёк. Запросите новый код.",
            code="candidate_shared_access_code_invalid",
        )
    await _delete_key(_challenge_key(challenge_id))
    if candidate_id <= 0:
        await _increment_metric("verify_failed")
        raise CandidateSharedAccessError(
            "Код не подошёл или уже истёк. Запросите новый код.",
            code="candidate_shared_access_code_invalid",
        )
    candidate = await session.get(User, candidate_id)
    if candidate is None:
        await _increment_metric("verify_failed")
        raise CandidateSharedAccessError(
            "Код не подошёл или уже истёк. Запросите новый код.",
            code="candidate_shared_access_code_invalid",
        )
    journey = await ensure_candidate_portal_session(session, candidate, entry_channel="web")
    journey_meta = dict(journey.payload_json or {}) if isinstance(journey.payload_json, dict) else {}
    journey_meta["entry_source"] = "shared_portal"
    journey_meta["shared_access_verified_at"] = _utcnow().isoformat()
    journey.payload_json = journey_meta
    _mark_journey_event_once(
        candidate,
        journey,
        flag_key="shared_access_verified_event_logged_at",
        event_key="shared_access_verified",
        summary="Кандидат подтвердил вход по одноразовому коду.",
        stage="lead",
        payload={"entry_channel": "web", "source": "shared_portal"},
    )
    response_payload = await build_candidate_portal_journey(
        session,
        candidate,
        entry_channel="web",
        journey=journey,
    )
    await _increment_metric("verify_success")
    return candidate, journey, response_payload


async def get_candidate_shared_access_health() -> dict[str, Any]:
    settings = get_settings()
    rate_limit_ready = (
        settings.environment != "production"
        or (settings.rate_limit_enabled and bool(settings.rate_limit_redis_url))
    )
    production_ready = _shared_access_store_ready() and rate_limit_ready
    return {
        "store_backend": _shared_access_store_backend(),
        "store_ready": _shared_access_store_ready(),
        "rate_limit_ready": rate_limit_ready,
        "production_required": settings.environment == "production",
        "production_ready": production_ready,
        "challenge_started": await _read_metric("challenge_started"),
        "challenge_rate_limited": await _read_metric("challenge_rate_limited"),
        "verify_success": await _read_metric("verify_success"),
        "verify_failed": await _read_metric("verify_failed"),
        "verify_expired": await _read_metric("verify_expired"),
        "delivery_channel_used": {
            "hh": await _read_metric("delivery_channel_used", label="hh"),
            "telegram": await _read_metric("delivery_channel_used", label="telegram"),
            "max": await _read_metric("delivery_channel_used", label="max"),
        },
        "delivery_block_reason": {
            "candidate_not_found_or_ambiguous": await _read_metric(
                "delivery_block_reason",
                label="candidate_not_found_or_ambiguous",
            ),
            "shared_access_delivery_unavailable": await _read_metric(
                "delivery_block_reason",
                label="shared_access_delivery_unavailable",
            ),
        },
    }


async def record_candidate_shared_access_rate_limited() -> None:
    await _increment_metric("challenge_rate_limited")
