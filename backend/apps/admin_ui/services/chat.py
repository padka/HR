from __future__ import annotations

import asyncio
import logging
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Dict, List, Optional, Tuple

from fastapi import HTTPException, status
from redis.exceptions import RedisError
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend.apps.admin_ui.services.bot_service import BotService
from backend.apps.admin_ui.services.chat_meta import derive_chat_message_kind
from backend.core.db import async_session
from backend.core.messenger.registry import get_registry
from backend.core.messenger.protocol import MessengerPlatform
from backend.core.redis_factory import create_redis_client
from backend.core.settings import get_settings
from backend.domain.candidates.models import ChatMessage, ChatMessageStatus, ChatMessageDirection, User
from backend.domain.candidates.services import (
    list_chat_messages as domain_list_chat_messages,
    update_chat_message_status,
    set_conversation_mode,
)
from backend.domain.models import Slot, Recruiter

logger = logging.getLogger(__name__)

# Rate limiting configuration
CHAT_RATE_LIMIT_PER_HOUR = 20  # Max messages per candidate per hour
CHAT_RATE_LIMIT_WINDOW_SECONDS = 3600  # 1 hour window

# In-memory rate limit store (candidate_id -> list of timestamps)
# In production, consider using Redis for persistence across workers
_rate_limit_store: Dict[int, List[float]] = defaultdict(list)
_rate_limit_redis_client = None
_rate_limit_redis_url = ""
_rate_limit_redis_failed = False

CHAT_TEMPLATES: List[Dict[str, str]] = [
    {
        "key": "reminder",
        "label": "Напоминание",
        "text": "Добрый день! Напоминаем о предстоящем собеседовании. Подтвердите, пожалуйста, участие.",
    },
    {
        "key": "confirm_time",
        "label": "Подтвердите время",
        "text": "Пожалуйста, подтвердите, подходит ли вам назначенное время встречи. Если нужно перенести — напишите удобный слот.",
    },
    {
        "key": "call_link",
        "label": "Ссылка на созвон",
        "text": "Подключайтесь к встрече по ссылке: {link}. Если возникнут сложности, дайте знать.",
    },
    {
        "key": "reschedule",
        "label": "Перенос",
        "text": "Если необходимо перенести встречу, напишите, какие даты и время вам удобны. Мы подберём другой слот.",
    },
    {
        "key": "address",
        "label": "Адрес",
        "text": "Адрес проведения встречи: <адрес>. Приходите за 5–10 минут до начала, не забудьте документ.",
    },
    {
        "key": "thanks",
        "label": "Спасибо/фидбек",
        "text": "Спасибо, что нашли время на встречу! Если остались вопросы или есть обратная связь — напишите нам.",
    },
]

CHAT_MODE_TTL_MINUTES = 45
CHAT_RATE_LIMIT_REDIS_TTL_SECONDS = CHAT_RATE_LIMIT_WINDOW_SECONDS + 60


def get_chat_templates() -> List[Dict[str, str]]:
    return CHAT_TEMPLATES


def _chat_rate_limit_key(candidate_id: int) -> str:
    return f"chat:rate_limit:{candidate_id}"


def _clear_rate_limit_state() -> None:
    global _rate_limit_redis_client, _rate_limit_redis_url, _rate_limit_redis_failed
    _rate_limit_store.clear()
    _rate_limit_redis_client = None
    _rate_limit_redis_url = ""
    _rate_limit_redis_failed = False


async def _get_rate_limit_redis_client():
    global _rate_limit_redis_client, _rate_limit_redis_url, _rate_limit_redis_failed

    settings = get_settings()
    if settings.environment == "test":
        return None

    redis_url = (settings.rate_limit_redis_url or settings.redis_url or "").strip()
    if not redis_url:
        return None

    if _rate_limit_redis_client is not None and _rate_limit_redis_url == redis_url:
        return _rate_limit_redis_client
    if _rate_limit_redis_failed and _rate_limit_redis_url == redis_url:
        return None

    try:
        client = create_redis_client(redis_url, component="chat_rate_limit", decode_responses=True)
        await client.ping()
    except Exception as exc:
        _rate_limit_redis_client = None
        _rate_limit_redis_url = redis_url
        _rate_limit_redis_failed = True
        logger.warning("chat.rate_limit.redis_unavailable", extra={"error": str(exc)})
        return None

    _rate_limit_redis_client = client
    _rate_limit_redis_url = redis_url
    _rate_limit_redis_failed = False
    return client


def _check_rate_limit(candidate_id: int) -> Tuple[bool, int]:
    """Check if sending to this candidate is allowed within rate limits.

    Returns:
        Tuple of (is_allowed, remaining_count)
    """
    now = datetime.now(timezone.utc).timestamp()
    window_start = now - CHAT_RATE_LIMIT_WINDOW_SECONDS

    # Clean up old entries
    timestamps = _rate_limit_store[candidate_id]
    _rate_limit_store[candidate_id] = [ts for ts in timestamps if ts > window_start]

    current_count = len(_rate_limit_store[candidate_id])
    remaining = max(0, CHAT_RATE_LIMIT_PER_HOUR - current_count)

    return current_count < CHAT_RATE_LIMIT_PER_HOUR, remaining


def _record_message_sent(candidate_id: int) -> None:
    """Record that a message was sent for rate limiting."""
    now = datetime.now(timezone.utc).timestamp()
    _rate_limit_store[candidate_id].append(now)


async def _check_rate_limit_async(candidate_id: int) -> Tuple[bool, int]:
    client = await _get_rate_limit_redis_client()
    if client is None:
        return _check_rate_limit(candidate_id)

    now = datetime.now(timezone.utc).timestamp()
    window_start = now - CHAT_RATE_LIMIT_WINDOW_SECONDS
    key = _chat_rate_limit_key(candidate_id)
    try:
        async with client.pipeline(transaction=True) as pipe:
            pipe.zremrangebyscore(key, "-inf", window_start)
            pipe.zcard(key)
            pipe.expire(key, CHAT_RATE_LIMIT_REDIS_TTL_SECONDS)
            _, current_count, _ = await pipe.execute()
    except (RedisError, OSError) as exc:
        logger.warning("chat.rate_limit.redis_fallback", extra={"error": str(exc)})
        return _check_rate_limit(candidate_id)

    remaining = max(0, CHAT_RATE_LIMIT_PER_HOUR - int(current_count))
    return int(current_count) < CHAT_RATE_LIMIT_PER_HOUR, remaining


async def _record_message_sent_async(candidate_id: int) -> None:
    client = await _get_rate_limit_redis_client()
    if client is None:
        _record_message_sent(candidate_id)
        return

    now = datetime.now(timezone.utc).timestamp()
    key = _chat_rate_limit_key(candidate_id)
    member = f"{now:.6f}:{uuid.uuid4().hex}"
    try:
        async with client.pipeline(transaction=True) as pipe:
            pipe.zadd(key, {member: now})
            pipe.zremrangebyscore(key, "-inf", now - CHAT_RATE_LIMIT_WINDOW_SECONDS)
            pipe.expire(key, CHAT_RATE_LIMIT_REDIS_TTL_SECONDS)
            await pipe.execute()
    except (RedisError, OSError) as exc:
        logger.warning("chat.rate_limit.redis_record_fallback", extra={"error": str(exc)})
        _record_message_sent(candidate_id)


def _delivery_stage(status_value: Optional[str]) -> str:
    normalized = (status_value or "").strip().lower()
    if normalized == ChatMessageStatus.QUEUED.value:
        return "queued"
    if normalized == ChatMessageStatus.SENT.value:
        return "provider_accepted"
    if normalized == ChatMessageStatus.FAILED.value:
        return "terminal_failed"
    return normalized or "unknown"


def serialize_chat_message(message: ChatMessage) -> Dict[str, object]:
    payload = dict(message.payload_json or {}) if isinstance(message.payload_json, dict) else {}
    delivery_channels_raw = payload.get("delivery_channels")
    if isinstance(delivery_channels_raw, list):
        delivery_channels = [str(item).strip() for item in delivery_channels_raw if str(item).strip()]
    else:
        delivery_channels = [str(message.channel).strip()] if str(message.channel or "").strip() else []

    return {
        "id": message.id,
        "conversation_id": f"candidate:{int(message.candidate_id)}",
        "direction": message.direction,
        "kind": derive_chat_message_kind(
            message.direction,
            author_label=message.author_label,
            payload_json=message.payload_json,
        ),
        "channel": message.channel,
        "origin_channel": str(payload.get("origin_channel") or message.channel or "web"),
        "delivery_channels": delivery_channels,
        "delivery_state": message.status,
        "author_role": str(payload.get("author_role") or "").strip().lower() or (
            "candidate" if message.direction == ChatMessageDirection.INBOUND.value else "recruiter"
        ),
        "text": message.text or "",
        "status": message.status,
        "delivery_stage": _delivery_stage(message.status),
        "error": message.error,
        "telegram_message_id": message.telegram_message_id,
        "created_at": message.created_at.isoformat(),
        "author": message.author_label,
        "can_retry": message.direction == ChatMessageDirection.OUTBOUND.value and message.status == ChatMessageStatus.FAILED.value,
    }


async def list_chat_history(candidate_id: int, limit: int, before: Optional[datetime]) -> Dict[str, object]:
    fetch_limit = min(limit, 200)
    messages = await domain_list_chat_messages(candidate_id, limit=fetch_limit + 1, before=before)
    has_more = len(messages) > fetch_limit
    data = messages[:fetch_limit]
    latest_message_at = data[0].created_at.isoformat() if data else None
    return {
        "messages": [serialize_chat_message(msg) for msg in data],
        "has_more": has_more,
        "latest_message_at": latest_message_at,
    }


async def _latest_chat_message_at(candidate_id: int) -> Optional[datetime]:
    async with async_session() as session:
        row = await session.execute(
            select(ChatMessage.created_at)
            .where(ChatMessage.candidate_id == candidate_id)
            .order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc())
            .limit(1)
        )
        created_at = row.scalar_one_or_none()
    if created_at and created_at.tzinfo is None:
        return created_at.replace(tzinfo=timezone.utc)
    return created_at


async def wait_for_chat_history_updates(
    candidate_id: int,
    *,
    since: Optional[datetime],
    timeout: int = 25,
    limit: int = 80,
) -> Dict[str, object]:
    deadline = datetime.now(timezone.utc) + timedelta(seconds=max(timeout, 5))
    since_utc = since if since is None or since.tzinfo is not None else since.replace(tzinfo=timezone.utc)

    while True:
        latest_message_at = await _latest_chat_message_at(candidate_id)
        if since_utc is None or (latest_message_at and latest_message_at > since_utc):
            payload = await list_chat_history(candidate_id, limit=limit, before=None)
            payload["updated"] = True
            return payload
        if datetime.now(timezone.utc) >= deadline:
            return {
                "messages": [],
                "has_more": False,
                "latest_message_at": latest_message_at.isoformat() if latest_message_at else None,
                "updated": False,
            }
        await asyncio.sleep(1.0)


async def _load_candidate(candidate_id: int) -> User:
    async with async_session() as session:
        user = await session.get(User, candidate_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"message": "Кандидат не найден"},
            )
        session.expunge(user)
        return user


async def _existing_message(candidate_id: int, client_request_id: Optional[str]) -> Optional[ChatMessage]:
    if not client_request_id:
        return None
    async with async_session() as session:
        stmt = (
            select(ChatMessage)
            .where(
                ChatMessage.candidate_id == candidate_id,
                ChatMessage.client_request_id == client_request_id,
            )
        )
        result = await session.execute(stmt)
        message = result.scalar_one_or_none()
        if message:
            session.expunge(message)
        return message


def _resolve_delivery_channel(
    candidate: User,
    *,
    preferred_channel: Optional[str] = None,
) -> tuple[str, Optional[int]]:
    requested = str(preferred_channel or "").strip().lower()
    telegram_user_id = candidate.telegram_user_id or candidate.telegram_id
    max_user_id = str(candidate.max_user_id or "").strip()
    default_channel = str(getattr(candidate, "messenger_platform", "") or "").strip().lower()

    channel = requested or default_channel
    if channel == "max":
        if max_user_id:
            return "max", None
        if requested == "max":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"message": "Для кандидата не найден MAX ID"},
            )
        channel = ""

    if channel == "telegram":
        if telegram_user_id:
            return "telegram", telegram_user_id
        if requested == "telegram":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"message": "Для кандидата не найден Telegram ID"},
            )
        channel = ""

    if channel == "web":
        return "web", None

    if telegram_user_id:
        return "telegram", telegram_user_id
    if max_user_id:
        return "max", None
    return "web", None


async def _dispatch_chat_message(
    candidate: User,
    *,
    text: str,
    bot_service: BotService,
    reply_markup: Optional[object] = None,
    preferred_channel: Optional[str] = None,
):
    channel, telegram_user_id = _resolve_delivery_channel(
        candidate,
        preferred_channel=preferred_channel,
    )

    if channel == "web":
        return channel, SimpleNamespace(
            ok=True,
            success=True,
            status="sent",
            error=None,
            message=None,
        )

    if channel == "telegram":
        send_result = await bot_service.send_chat_message(
            telegram_user_id,
            text,
            reply_markup=reply_markup,
        )
        return channel, send_result

    adapter = get_registry().get(MessengerPlatform.MAX)
    if adapter is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"message": "MAX bot не настроен"},
        )
    if reply_markup is not None:
        logger.info(
            "chat.max.reply_markup_ignored",
            extra={"candidate_id": candidate.id},
        )
    send_result = await adapter.send_message(
        str(candidate.max_user_id),
        text,
        correlation_id=f"candidate-chat:{candidate.id}",
    )
    return channel, send_result


def _send_result_ok(send_result: object) -> bool:
    return bool(getattr(send_result, "ok", False) or getattr(send_result, "success", False))


def _send_result_status(send_result: object) -> str:
    status_value = getattr(send_result, "status", None)
    if isinstance(status_value, str) and status_value:
        return status_value
    return "sent" if _send_result_ok(send_result) else "failed"


def _send_result_error(send_result: object) -> str:
    return str(
        getattr(send_result, "error", None)
        or getattr(send_result, "message", None)
        or "Не удалось отправить сообщение"
    )


async def send_chat_message(
    candidate_id: int,
    *,
    text: str,
    client_request_id: Optional[str],
    author_label: Optional[str],
    bot_service: BotService,
    reply_markup: Optional[object] = None,
) -> Dict[str, object]:
    candidate = await _load_candidate(candidate_id)
    channel, telegram_user_id = _resolve_delivery_channel(candidate)

    duplicate = await _existing_message(candidate_id, client_request_id)
    if duplicate:
        return {
            "message": serialize_chat_message(duplicate),
            "status": "duplicate",
        }

    is_allowed, remaining = await _check_rate_limit_async(candidate_id)
    if not is_allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "message": f"Превышен лимит сообщений ({CHAT_RATE_LIMIT_PER_HOUR} в час). Попробуйте позже.",
                "retry_after": CHAT_RATE_LIMIT_WINDOW_SECONDS,
                "remaining": remaining,
            },
        )

    text = await _fill_dynamic_fields(text, candidate)

    async with async_session() as session:
        message = ChatMessage(
            candidate_id=candidate.id,
            telegram_user_id=telegram_user_id if channel == "telegram" else None,
            direction=ChatMessageDirection.OUTBOUND.value,
            channel=channel,
            text=text,
            payload_json={
                "origin_channel": "crm",
                "delivery_channels": ["web"] if channel == "web" else ["web", channel],
                "author_role": "recruiter",
            },
            status=ChatMessageStatus.QUEUED.value,
            author_label=author_label,
            client_request_id=client_request_id,
        )
        session.add(message)
        await session.commit()
        await session.refresh(message)
        message_id = message.id

    delivery_channel, send_result = await _dispatch_chat_message(
        candidate,
        text=text,
        bot_service=bot_service,
        reply_markup=reply_markup,
    )
    if _send_result_ok(send_result):
        await _record_message_sent_async(candidate_id)

        await update_chat_message_status(
            message_id,
            status=ChatMessageStatus.SENT,
            telegram_message_id=(
                getattr(send_result, "telegram_message_id", None)
                if delivery_channel == "telegram"
                else None
            ),
            error=None,
        )
        if delivery_channel == "telegram":
            try:
                await set_conversation_mode(
                    candidate.telegram_user_id or candidate.telegram_id,
                    mode="chat",
                    ttl_minutes=CHAT_MODE_TTL_MINUTES,
                )
            except Exception:  # pragma: no cover - non-critical
                pass
    else:
        await update_chat_message_status(
            message_id,
            status=ChatMessageStatus.FAILED,
            error=_send_result_error(send_result),
        )

    updated = await _existing_message(candidate_id, client_request_id) or await _fetch_message_by_id(message_id)
    return {
        "message": serialize_chat_message(updated),
        "status": _send_result_status(send_result) if _send_result_ok(send_result) else "failed",
    }


async def _resolve_recruiter_link(candidate: User) -> Optional[str]:
    tg_id = candidate.telegram_user_id or candidate.telegram_id
    if not tg_id:
        return None
    async with async_session() as session:
        row = (
            await session.execute(
                select(Slot, Recruiter)
                .join(Recruiter, Recruiter.id == Slot.recruiter_id)
                .options(selectinload(Slot.recruiter))
                .where(Slot.candidate_tg_id == tg_id)
                .order_by(Slot.start_utc.desc())
                .limit(1)
            )
        ).first()
        if not row:
            return None
        _, recruiter = row
        return getattr(recruiter, "telemost_url", None) or None


async def _fill_dynamic_fields(text: str, candidate: User) -> str:
    if "{link}" not in text and "<ссылка>" not in text:
        return text
    link = await _resolve_recruiter_link(candidate)
    if not link:
        return text.replace("{link}", "").replace("<ссылка>", "").strip()
    return text.replace("{link}", link).replace("<ссылка>", link)


async def _fetch_message_by_id(message_id: int) -> Optional[ChatMessage]:
    async with async_session() as session:
        message = await session.get(ChatMessage, message_id)
        if message:
            session.expunge(message)
        return message


async def retry_chat_message(
    candidate_id: int,
    message_id: int,
    *,
    bot_service: BotService,
) -> Dict[str, object]:
    async with async_session() as session:
        message = await session.get(ChatMessage, message_id)
        if not message or message.candidate_id != candidate_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"message": "Сообщение не найдено"},
            )
        if message.direction != ChatMessageDirection.OUTBOUND.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"message": "Повторно можно отправить только исходящее сообщение"},
            )
        if message.status != ChatMessageStatus.FAILED.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"message": "Можно повторно отправить только сообщения со статусом failed"},
            )
        message.status = ChatMessageStatus.QUEUED.value
        message.error = None
        await session.commit()
        await session.refresh(message)
        text = message.text or ""
        channel = message.channel or "telegram"
        candidate = await session.get(User, candidate_id)

    if candidate is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": "Кандидат не найден"},
        )
    is_allowed, remaining = await _check_rate_limit_async(candidate_id)
    if not is_allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "message": f"Превышен лимит сообщений ({CHAT_RATE_LIMIT_PER_HOUR} в час). Попробуйте позже.",
                "retry_after": CHAT_RATE_LIMIT_WINDOW_SECONDS,
                "remaining": remaining,
            },
        )
    delivery_channel, send_result = await _dispatch_chat_message(
        candidate,
        text=text,
        bot_service=bot_service,
        preferred_channel=channel,
    )
    if _send_result_ok(send_result):
        await _record_message_sent_async(candidate_id)
        await update_chat_message_status(
            message_id,
            status=ChatMessageStatus.SENT,
            telegram_message_id=(
                getattr(send_result, "telegram_message_id", None)
                if delivery_channel == "telegram"
                else None
            ),
            error=None,
        )
    else:
        await update_chat_message_status(
            message_id,
            status=ChatMessageStatus.FAILED,
            error=_send_result_error(send_result),
        )

    refreshed = await _fetch_message_by_id(message_id)
    return {
        "message": serialize_chat_message(refreshed),
        "status": _send_result_status(send_result) if _send_result_ok(send_result) else "failed",
    }
