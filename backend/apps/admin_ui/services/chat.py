from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend.apps.admin_ui.services.bot_service import BotService
from backend.core.db import async_session
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


def get_chat_templates() -> List[Dict[str, str]]:
    return CHAT_TEMPLATES


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


def serialize_chat_message(message: ChatMessage) -> Dict[str, object]:
    return {
        "id": message.id,
        "direction": message.direction,
        "channel": message.channel,
        "text": message.text or "",
        "status": message.status,
        "error": message.error,
        "created_at": message.created_at.isoformat(),
        "author": message.author_label,
        "can_retry": message.direction == ChatMessageDirection.OUTBOUND.value and message.status == ChatMessageStatus.FAILED.value,
    }


async def list_chat_history(candidate_id: int, limit: int, before: Optional[datetime]) -> Dict[str, object]:
    fetch_limit = min(limit, 200)
    messages = await domain_list_chat_messages(candidate_id, limit=fetch_limit + 1, before=before)
    has_more = len(messages) > fetch_limit
    data = messages[:fetch_limit]
    return {
        "messages": [serialize_chat_message(msg) for msg in data],
        "has_more": has_more,
    }


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
    if not candidate.telegram_user_id and not candidate.telegram_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "Для кандидата не найден Telegram ID"},
        )

    # Check rate limit before processing
    is_allowed, remaining = _check_rate_limit(candidate_id)
    if not is_allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "message": f"Превышен лимит сообщений ({CHAT_RATE_LIMIT_PER_HOUR} в час). Попробуйте позже.",
                "retry_after": CHAT_RATE_LIMIT_WINDOW_SECONDS,
            },
        )

    duplicate = await _existing_message(candidate_id, client_request_id)
    if duplicate:
        return {
            "message": serialize_chat_message(duplicate),
            "status": "duplicate",
        }

    text = await _fill_dynamic_fields(text, candidate)

    async with async_session() as session:
        message = ChatMessage(
            candidate_id=candidate.id,
            telegram_user_id=candidate.telegram_user_id or candidate.telegram_id,
            direction=ChatMessageDirection.OUTBOUND.value,
            channel="telegram",
            text=text,
            status=ChatMessageStatus.QUEUED.value,
            author_label=author_label,
            client_request_id=client_request_id,
        )
        session.add(message)
        await session.commit()
        await session.refresh(message)
        message_id = message.id

    send_result = await bot_service.send_chat_message(
        candidate.telegram_user_id or candidate.telegram_id,
        text,
        reply_markup=reply_markup,
    )
    if send_result.ok:
        # Record successful send for rate limiting
        _record_message_sent(candidate_id)

        await update_chat_message_status(
            message_id,
            status=ChatMessageStatus.SENT,
            telegram_message_id=getattr(send_result, "telegram_message_id", None),
            error=None,
        )
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
            error=send_result.error or send_result.message or "Не удалось отправить сообщение",
        )

    updated = await _existing_message(candidate_id, client_request_id) or await _fetch_message_by_id(message_id)
    return {
        "message": serialize_chat_message(updated),
        "status": send_result.status if send_result.ok else "failed",
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
        telegram_user_id = message.telegram_user_id
        text = message.text or ""

    if not telegram_user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "Нет Telegram ID для повторной отправки"},
        )
    send_result = await bot_service.send_chat_message(telegram_user_id, text)
    if send_result.ok:
        await update_chat_message_status(
            message_id,
            status=ChatMessageStatus.SENT,
            telegram_message_id=getattr(send_result, "telegram_message_id", None),
            error=None,
        )
    else:
        await update_chat_message_status(
            message_id,
            status=ChatMessageStatus.FAILED,
            error=send_result.error or send_result.message or "Не удалось отправить сообщение",
        )

    refreshed = await _fetch_message_by_id(message_id)
    return {
        "message": serialize_chat_message(refreshed),
        "status": send_result.status if send_result.ok else "failed",
    }
