from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, List, Optional, Sequence

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.apps.admin_ui.security import admin_principal
from backend.core.db import async_session
from backend.domain import analytics

from .models import (
    AutoMessage,
    CandidateAccessToken,
    CandidateAccessTokenKind,
    CandidateLaunchChannel,
    CandidateInviteToken,
    ChatMessage,
    ChatMessageDirection,
    ChatMessageStatus,
    InterviewNote,
    Notification,
    QuestionAnswer,
    TestResult,
    User,
)

if TYPE_CHECKING:
    from .status import CandidateStatus


INVITE_STATUS_ACTIVE = "active"
INVITE_STATUS_USED = "used"
INVITE_STATUS_SUPERSEDED = "superseded"
INVITE_STATUS_CONFLICT = "conflict"

INVITE_CHANNEL_GENERIC = "generic"
INVITE_CHANNEL_TELEGRAM = "telegram"
INVITE_CHANNEL_MAX = "max"


def normalize_invite_channel(value: Optional[str]) -> str:
    normalized = (value or "").strip().lower()
    if normalized in {"tg", INVITE_CHANNEL_TELEGRAM}:
        return INVITE_CHANNEL_TELEGRAM
    if normalized in {"vk_max", "vkmax", INVITE_CHANNEL_MAX}:
        return INVITE_CHANNEL_MAX
    if normalized == INVITE_CHANNEL_GENERIC:
        return INVITE_CHANNEL_GENERIC
    return INVITE_CHANNEL_GENERIC


def _should_promote_source_to_max(source: Optional[str]) -> bool:
    normalized = str(source or "").strip().lower()
    return normalized in {"", "bot", "generic", "unknown", "candidate_access"}


async def create_or_update_user(
    telegram_id: int,
    fio: str,
    city: str,
    username: Optional[str] = None,
    initial_status: Optional[CandidateStatus] = None,
    *,
    candidate_id: Optional[str] = None,
    source: Optional[str] = None,
    responsible_recruiter_id: Optional[int] = None,
) -> User:
    """Create or update user. For new users, optionally set initial candidate_status.

    Args:
        initial_status: Status to set for NEW users only (e.g., TEST1_COMPLETED when booking interview).
                       Existing users keep their current status.
    """
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        now = datetime.now(timezone.utc)
        created = False
        if user:
            user.fio = fio
            user.city = city
            user.last_activity = now
            if not user.candidate_id:
                user.candidate_id = candidate_id or str(uuid.uuid4())
            if (
                responsible_recruiter_id is not None
                and user.responsible_recruiter_id != responsible_recruiter_id
            ):
                user.responsible_recruiter_id = responsible_recruiter_id
            if user.telegram_user_id is None:
                user.telegram_user_id = telegram_id
            if user.telegram_linked_at is None:
                user.telegram_linked_at = now
            # Update username if provided (user might add/change it)
            if username is not None:
                user.username = username
                user.telegram_username = username
            if source and not user.source:
                user.source = source
        else:
            created = True
            payload = {
                "telegram_id": telegram_id,
                "username": username,
                "telegram_user_id": telegram_id,
                "telegram_username": username,
                "telegram_linked_at": now,
                "fio": fio,
                "city": city,
                "last_activity": now,
                "candidate_status": initial_status,
                "source": source or "bot",
                "responsible_recruiter_id": responsible_recruiter_id,
            }
            if candidate_id:
                payload["candidate_id"] = candidate_id
            user = User(**payload)
            session.add(user)
        await session.commit()
        await session.refresh(user)
    if created:
        from backend.core.ai.service import schedule_warm_candidate_ai_outputs

        schedule_warm_candidate_ai_outputs(int(user.id), principal=admin_principal(), refresh=True)
    return user


async def save_test_result(
    user_id: int,
    raw_score: int,
    final_score: float,
    rating: str,
    total_time: int,
    question_data: Sequence[dict],
    *,
    source: str = "bot",
) -> TestResult:
    async with async_session() as session:
        test_result = TestResult(
            user_id=user_id,
            raw_score=raw_score,
            final_score=final_score,
            rating=rating,
            source=source,
            total_time=total_time,
        )
        session.add(test_result)
        await session.flush()  # ensure PK for FK usage

        for q_data in question_data:
            answer = QuestionAnswer(
                test_result_id=test_result.id,
                question_index=q_data.get("question_index", 0),
                question_text=q_data.get("question_text", ""),
                correct_answer=q_data.get("correct_answer"),
                user_answer=q_data.get("user_answer"),
                attempts_count=q_data.get("attempts_count", 0),
                time_spent=q_data.get("time_spent", 0),
                is_correct=bool(q_data.get("is_correct", False)),
                overtime=bool(q_data.get("overtime", False)),
            )
            session.add(answer)

        await session.commit()
        await session.refresh(test_result)
    from backend.core.ai.service import invalidate_candidate_ai_outputs, schedule_warm_candidate_ai_outputs

    await invalidate_candidate_ai_outputs(user_id)
    schedule_warm_candidate_ai_outputs(int(user_id), principal=admin_principal(), refresh=True)
    return test_result


async def get_user_by_telegram_id(telegram_id: int) -> Optional[User]:
    if telegram_id is None:
        return None
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        if user:
            session.expunge(user)
        return user


async def get_user_by_candidate_id(candidate_id: str) -> Optional[User]:
    if not candidate_id:
        return None
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.candidate_id == candidate_id)
        )
        user = result.scalar_one_or_none()
        if user:
            session.expunge(user)
        return user


async def get_user_by_max_user_id(max_user_id: str) -> Optional[User]:
    normalized = str(max_user_id or "").strip()
    if not normalized:
        return None
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.max_user_id == normalized)
        )
        user = result.scalar_one_or_none()
        if user:
            session.expunge(user)
        return user


async def get_all_active_users() -> List[User]:
    async with async_session() as session:
        result = await session.scalars(select(User).where(User.is_active.is_(True)))
        users = list(result.all())
        for user in users:
            session.expunge(user)
        return users


async def get_test_statistics() -> dict:
    async with async_session() as session:
        total_tests = await session.scalar(select(func.count(TestResult.id)))
        completed_tests = total_tests or 0

        if not completed_tests:
            return {
                "total_tests": 0,
                "completed_tests": 0,
                "average_score": 0,
                "success_rate": 0,
            }

        avg_score = await session.scalar(select(func.avg(TestResult.final_score)))
        successful_tests = await session.scalar(
            select(func.count(TestResult.id)).where(TestResult.final_score >= 3.5)
        )

        return {
            "total_tests": completed_tests,
            "completed_tests": completed_tests,
            "average_score": round(avg_score or 0, 2),
            "success_rate": round(((successful_tests or 0) / completed_tests) * 100, 2),
        }


async def create_auto_message(
    message_text: str, send_time: str, target_chat_id: Optional[int] = None
) -> AutoMessage:
    async with async_session() as session:
        auto_message = AutoMessage(
            message_text=message_text,
            send_time=send_time,
            target_chat_id=target_chat_id,
        )
        session.add(auto_message)
        await session.commit()
        await session.refresh(auto_message)
        return auto_message


async def get_active_auto_messages() -> List[AutoMessage]:
    async with async_session() as session:
        result = await session.scalars(
            select(AutoMessage).where(AutoMessage.is_active.is_(True))
        )
        return list(result.all())


async def create_notification(
    admin_chat_id: int, notification_type: str, message_text: str
) -> Notification:
    async with async_session() as session:
        notification = Notification(
            admin_chat_id=admin_chat_id,
            notification_type=notification_type,
            message_text=message_text,
        )
        session.add(notification)
        await session.commit()
        await session.refresh(notification)
        return notification


async def mark_notification_sent(notification_id: int) -> None:
    async with async_session() as session:
        notification = await session.get(Notification, notification_id)
        if notification:
            notification.is_sent = True
            notification.sent_at = datetime.now(timezone.utc)
            await session.commit()


async def update_chat_message_status(
    message_id: int,
    *,
    status: ChatMessageStatus,
    telegram_message_id: Optional[int] = None,
    provider_message_id: Optional[str] = None,
    error: Optional[str] = None,
) -> None:
    async with async_session() as session:
        message = await session.get(ChatMessage, message_id)
        if not message:
            return
        message.status = status.value
        if telegram_message_id is not None:
            message.telegram_message_id = telegram_message_id
        if provider_message_id:
            payload = dict(message.payload_json or {})
            payload["provider_message_id"] = str(provider_message_id)
            message.payload_json = payload
        if error is not None:
            message.error = error
        await session.commit()


async def log_inbound_chat_message(
    telegram_user_id: int,
    *,
    text: Optional[str],
    telegram_message_id: Optional[int] = None,
    payload: Optional[dict] = None,
    username: Optional[str] = None,
) -> Optional[ChatMessage]:
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_user_id)
        )
        user = result.scalar_one_or_none()
        now = datetime.now(timezone.utc)
        is_new_user = user is None
        if is_new_user:
            user = User(
                telegram_id=telegram_user_id,
                telegram_user_id=telegram_user_id,
                telegram_username=username,
                username=username,
                fio=f"TG {telegram_user_id}",
                last_activity=now,
                telegram_linked_at=now,
            )
            session.add(user)
            await session.flush()
            await analytics.log_funnel_event(
                analytics.FunnelEvent.BOT_ENTERED,
                user_id=telegram_user_id,
                candidate_id=user.id,
                metadata={"channel": "telegram"},
                session=session,
            )
        else:
            if username:
                user.username = username
                user.telegram_username = username
        message = ChatMessage(
            candidate_id=user.id,
            telegram_user_id=telegram_user_id,
            direction=ChatMessageDirection.INBOUND.value,
            channel="telegram",
            text=text,
            payload_json=payload,
            status=ChatMessageStatus.RECEIVED.value,
            telegram_message_id=telegram_message_id,
        )
        session.add(message)
        user.last_activity = now
        await session.commit()
        await session.refresh(message)
        return message


async def log_outbound_chat_message(
    telegram_user_id: int,
    *,
    text: Optional[str],
    telegram_message_id: Optional[int] = None,
    payload: Optional[dict] = None,
    author_label: Optional[str] = "bot",
    channel: str = "telegram",
    provider_message_id: Optional[str] = None,
) -> Optional[ChatMessage]:
    async with async_session() as session:
        result = await session.execute(
            select(User).where(
                or_(
                    User.telegram_id == telegram_user_id,
                    User.telegram_user_id == telegram_user_id,
                )
            )
        )
        user = result.scalar_one_or_none()
        if user is None:
            return None

        message = ChatMessage(
            candidate_id=user.id,
            telegram_user_id=telegram_user_id if channel == "telegram" else None,
            direction=ChatMessageDirection.OUTBOUND.value,
            channel=channel,
            text=text,
            payload_json={
                **(payload or {}),
                **(
                    {"provider_message_id": str(provider_message_id)}
                    if provider_message_id
                    else {}
                ),
            }
            if payload or provider_message_id
            else payload,
            status=ChatMessageStatus.SENT.value,
            telegram_message_id=telegram_message_id,
            author_label=author_label,
        )
        session.add(message)
        await session.commit()
        await session.refresh(message)
        return message


async def bind_max_to_candidate(
    *,
    start_param: str,
    max_user_id: str,
    username: Optional[str] = None,
    display_name: Optional[str] = None,
    provider_chat_id: Optional[str] = None,
) -> Optional[User]:
    normalized_start_param = str(start_param or "").strip()
    normalized_max_user_id = str(max_user_id or "").strip()
    if not normalized_start_param or not normalized_max_user_id:
        return None

    async with async_session() as session:
        async with session.begin():
            invite = await session.scalar(
                select(CandidateAccessToken)
                .where(CandidateAccessToken.start_param == normalized_start_param)
                .with_for_update()
            )
            if invite is None:
                return None
            if invite.launch_channel != CandidateLaunchChannel.MAX.value:
                return None
            if invite.token_kind not in {
                CandidateAccessTokenKind.INVITE.value,
                CandidateAccessTokenKind.LAUNCH.value,
                CandidateAccessTokenKind.RESUME.value,
            }:
                return None
            now = datetime.now(timezone.utc)
            if invite.revoked_at is not None:
                return None
            invite_expires_at = invite.expires_at
            if invite_expires_at.tzinfo is None:
                invite_expires_at = invite_expires_at.replace(tzinfo=timezone.utc)
            if invite_expires_at <= now:
                return None

            candidate = await session.get(User, int(invite.candidate_id))
            if candidate is None or not candidate.is_active:
                return None
            if candidate.max_user_id and candidate.max_user_id != normalized_max_user_id:
                return None

            existing = await session.scalar(
                select(User).where(User.max_user_id == normalized_max_user_id)
            )
            if existing is not None and existing.id != candidate.id:
                return None

            candidate.max_user_id = normalized_max_user_id
            candidate.messenger_platform = "max"
            if _should_promote_source_to_max(candidate.source):
                candidate.source = "max"
            candidate.last_activity = now
            if username and not candidate.username:
                candidate.username = username
            if display_name and (
                not candidate.fio or str(candidate.fio).startswith("TG ")
            ):
                candidate.fio = display_name

            invite.provider_user_id = normalized_max_user_id
            invite.provider_chat_id = str(provider_chat_id or normalized_max_user_id)
            invite.last_seen_at = now
            if invite.consumed_at is None:
                invite.consumed_at = now

            try:
                from backend.domain.candidates.journey import append_journey_event

                append_journey_event(
                    candidate,
                    event_key="max_linked",
                    stage="lead",
                    actor_type="candidate",
                    summary="Кандидат открыл MAX-бота",
                    payload={
                        "channel": "max",
                        "provider_user_id": normalized_max_user_id,
                        "start_param": normalized_start_param,
                    },
                    created_at=now,
                )
            except Exception:
                # Journey append must not block identity binding.
                pass

        await session.refresh(candidate)
        return candidate


async def log_inbound_max_message(
    max_user_id: str,
    *,
    text: Optional[str],
    provider_message_id: Optional[str] = None,
    client_request_id: Optional[str] = None,
    payload: Optional[dict] = None,
    username: Optional[str] = None,
    display_name: Optional[str] = None,
) -> Optional[ChatMessage]:
    normalized_max_user_id = str(max_user_id or "").strip()
    if not normalized_max_user_id:
        return None
    async with async_session() as session:
        if client_request_id:
            existing = await session.scalar(
                select(ChatMessage).where(ChatMessage.client_request_id == client_request_id)
            )
            if existing is not None:
                await session.refresh(existing)
                return existing
        result = await session.execute(
            select(User).where(User.max_user_id == normalized_max_user_id)
        )
        user = result.scalar_one_or_none()
        if user is None:
            return None
        now = datetime.now(timezone.utc)
        if username and not user.username:
            user.username = username
        if display_name and (
            not user.fio or str(user.fio).startswith("TG ")
        ):
            user.fio = display_name
        user.last_activity = now
        user.messenger_platform = "max"

        message_payload = dict(payload or {})
        message_payload["provider_user_id"] = normalized_max_user_id
        if provider_message_id:
            message_payload["provider_message_id"] = str(provider_message_id)

        message = ChatMessage(
            candidate_id=user.id,
            telegram_user_id=None,
            direction=ChatMessageDirection.INBOUND.value,
            channel="max",
            text=text,
            payload_json=message_payload,
            status=ChatMessageStatus.RECEIVED.value,
            client_request_id=client_request_id,
        )
        session.add(message)
        await session.commit()
        await session.refresh(message)
        return message


async def log_outbound_max_message(
    max_user_id: str,
    *,
    text: Optional[str],
    payload: Optional[dict] = None,
    author_label: Optional[str] = "max_bot",
    provider_message_id: Optional[str] = None,
    client_request_id: Optional[str] = None,
) -> Optional[ChatMessage]:
    normalized_max_user_id = str(max_user_id or "").strip()
    if not normalized_max_user_id:
        return None

    async with async_session() as session:
        if client_request_id:
            existing = await session.scalar(
                select(ChatMessage).where(ChatMessage.client_request_id == client_request_id)
            )
            if existing is not None:
                await session.refresh(existing)
                return existing

        user = await session.scalar(select(User).where(User.max_user_id == normalized_max_user_id))
        if user is None:
            return None

        message_payload = dict(payload or {})
        message_payload["provider_user_id"] = normalized_max_user_id
        if provider_message_id:
            message_payload["provider_message_id"] = str(provider_message_id)

        message = ChatMessage(
            candidate_id=user.id,
            telegram_user_id=None,
            direction=ChatMessageDirection.OUTBOUND.value,
            channel="max",
            text=text,
            payload_json=message_payload,
            status=ChatMessageStatus.SENT.value,
            author_label=author_label,
            client_request_id=client_request_id,
        )
        session.add(message)
        await session.commit()
        await session.refresh(message)
        return message


def _generate_invite_token() -> str:
    return secrets.token_urlsafe(8).rstrip("=")


async def create_candidate_invite_token(
    candidate_id: str,
    *,
    channel: str = INVITE_CHANNEL_GENERIC,
) -> CandidateInviteToken:
    channel_value = normalize_invite_channel(channel)
    async with async_session() as session:
        async with session.begin():
            token_value = _generate_invite_token()
            for _ in range(5):
                exists = await session.scalar(
                    select(func.count()).where(
                        CandidateInviteToken.token == token_value
                    )
                )
                if not exists:
                    break
                token_value = _generate_invite_token()

            invite = CandidateInviteToken(
                candidate_id=candidate_id,
                token=token_value,
                channel=channel_value,
                status=INVITE_STATUS_ACTIVE,
                created_at=datetime.now(timezone.utc),
            )
            session.add(invite)
        await session.refresh(invite)
        return invite


async def issue_candidate_invite_token(
    candidate_id: str,
    *,
    channel: str,
    rotate_active: bool = False,
    session: AsyncSession | None = None,
) -> tuple[CandidateInviteToken, list[int]]:
    now = datetime.now(timezone.utc)
    channel_value = normalize_invite_channel(channel)
    superseded_ids: list[int] = []

    async def _issue(db_session: AsyncSession) -> tuple[CandidateInviteToken, list[int]]:
        await db_session.scalar(
            select(User.id)
            .where(User.candidate_id == candidate_id)
            .with_for_update()
        )
        if rotate_active:
            existing_rows = (
                await db_session.scalars(
                    select(CandidateInviteToken)
                    .where(
                        CandidateInviteToken.candidate_id == candidate_id,
                        CandidateInviteToken.channel == channel_value,
                        CandidateInviteToken.status == INVITE_STATUS_ACTIVE,
                    )
                    .with_for_update()
                )
            ).all()
            for row in existing_rows:
                row.status = INVITE_STATUS_SUPERSEDED
                row.superseded_at = now
                superseded_ids.append(int(row.id))

        token_value = _generate_invite_token()
        for _ in range(5):
            exists = await db_session.scalar(
                select(func.count()).where(
                    CandidateInviteToken.token == token_value
                )
            )
            if not exists:
                break
            token_value = _generate_invite_token()

        invite = CandidateInviteToken(
            candidate_id=candidate_id,
            token=token_value,
            channel=channel_value,
            status=INVITE_STATUS_ACTIVE,
            created_at=now,
        )
        db_session.add(invite)
        await db_session.flush()
        return invite, superseded_ids

    if session is not None:
        return await _issue(session)

    async with async_session() as db_session:
        async with db_session.begin():
            invite, superseded_ids = await _issue(db_session)
        await db_session.refresh(invite)
        return invite, superseded_ids


async def get_latest_candidate_invite_token(
    session: AsyncSession,
    candidate_id: str,
    *,
    channel: str | None = None,
) -> Optional[CandidateInviteToken]:
    if not candidate_id:
        return None
    stmt = select(CandidateInviteToken).where(CandidateInviteToken.candidate_id == candidate_id)
    if channel:
        stmt = stmt.where(CandidateInviteToken.channel == normalize_invite_channel(channel))
    return await session.scalar(
        stmt.order_by(CandidateInviteToken.created_at.desc(), CandidateInviteToken.id.desc()).limit(1)
    )


async def ensure_candidate_invite_token(
    session: AsyncSession,
    candidate_id: str,
    *,
    channel: str = INVITE_CHANNEL_GENERIC,
) -> CandidateInviteToken:
    channel_value = normalize_invite_channel(channel)
    await session.scalar(
        select(User.id)
        .where(User.candidate_id == candidate_id)
        .with_for_update()
    )
    existing = await session.scalar(
        select(CandidateInviteToken)
        .where(
            CandidateInviteToken.candidate_id == candidate_id,
            CandidateInviteToken.channel == channel_value,
        )
        .order_by(CandidateInviteToken.created_at.desc(), CandidateInviteToken.id.desc())
        .limit(1)
        .with_for_update()
    )
    if existing is not None and (existing.status or INVITE_STATUS_ACTIVE) == INVITE_STATUS_ACTIVE:
        return existing

    token_value = _generate_invite_token()
    for _ in range(5):
        exists = await session.scalar(
            select(func.count()).where(
                CandidateInviteToken.token == token_value
            )
        )
        if not exists:
            break
        token_value = _generate_invite_token()

    invite = CandidateInviteToken(
        candidate_id=candidate_id,
        token=token_value,
        channel=channel_value,
        status=INVITE_STATUS_ACTIVE,
        created_at=datetime.now(timezone.utc),
    )
    session.add(invite)
    await session.flush()
    return invite


async def bind_telegram_to_candidate(
    *,
    token: str,
    telegram_id: int,
    username: Optional[str] = None,
) -> Optional[User]:
    clean_token = (token or "").strip()
    if not clean_token:
        return None

    async with async_session() as session:
        async with session.begin():
            invite = await session.scalar(
                select(CandidateInviteToken)
                .where(CandidateInviteToken.token == clean_token)
                .with_for_update()
            )
            if not invite:
                return None
            if invite.channel not in {INVITE_CHANNEL_GENERIC, INVITE_CHANNEL_TELEGRAM}:
                return None
            if invite.status in {INVITE_STATUS_SUPERSEDED, INVITE_STATUS_CONFLICT}:
                return None
            if invite.used_at is not None and invite.used_by_telegram_id not in {None, telegram_id}:
                invite.status = INVITE_STATUS_CONFLICT
                invite.used_by_external_id = str(telegram_id)
                return None

            candidate = await session.scalar(
                select(User).where(User.candidate_id == invite.candidate_id)
            )
            if not candidate:
                return None

            if candidate.telegram_id and candidate.telegram_id != telegram_id:
                return None

            existing = await session.scalar(
                select(User).where(User.telegram_id == telegram_id)
            )
            if existing and existing.id != candidate.id:
                await session.execute(
                    update(TestResult)
                    .where(TestResult.user_id == existing.id)
                    .values(user_id=candidate.id)
                )
                await session.execute(
                    update(ChatMessage)
                    .where(ChatMessage.candidate_id == existing.id)
                    .values(candidate_id=candidate.id)
                )
                await session.execute(
                    update(InterviewNote)
                    .where(InterviewNote.user_id == existing.id)
                    .values(user_id=candidate.id)
                )
                await session.delete(existing)

            now = datetime.now(timezone.utc)
            candidate.telegram_id = telegram_id
            candidate.telegram_user_id = telegram_id
            candidate.telegram_username = username or candidate.telegram_username
            candidate.username = username or candidate.username
            if candidate.telegram_linked_at is None:
                candidate.telegram_linked_at = now
            candidate.last_activity = now

            invite.used_at = now
            invite.status = "used"
            invite.used_by_telegram_id = telegram_id
            invite.used_by_external_id = str(telegram_id)

        await session.refresh(candidate)
        return candidate


async def list_chat_messages(
    candidate_id: int,
    *,
    limit: int = 50,
    before: Optional[datetime] = None,
) -> List[ChatMessage]:
    async with async_session() as session:
        stmt = (
            select(ChatMessage)
            .where(ChatMessage.candidate_id == candidate_id)
            .order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc())
            .limit(limit)
        )
        if before is not None:
            stmt = stmt.where(ChatMessage.created_at < before)
        rows = await session.execute(stmt)
        messages = list(rows.scalars())
        # Expunge objects from session to prevent lazy loading after session closes
        for msg in messages:
            session.expunge(msg)
        return messages


CONVERSATION_FLOW = "flow"
CONVERSATION_CHAT = "chat"
CONVERSATION_CHAT_TTL_MINUTES = 45


async def set_conversation_mode(
    telegram_id: int,
    mode: str,
    *,
    ttl_minutes: Optional[int] = None,
) -> None:
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        if not user:
            return
        user.conversation_mode = mode
        if mode == CONVERSATION_CHAT:
            minutes = ttl_minutes or CONVERSATION_CHAT_TTL_MINUTES
            user.conversation_mode_expires_at = datetime.now(timezone.utc) + timedelta(
                minutes=minutes
            )
        else:
            user.conversation_mode_expires_at = None
        await session.commit()


async def is_chat_mode_active(telegram_id: int) -> bool:
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        if not user:
            return False
        if user.conversation_mode != CONVERSATION_CHAT:
            return False
        expires = user.conversation_mode_expires_at
        if expires and expires < datetime.now(timezone.utc):
            user.conversation_mode = CONVERSATION_FLOW
            user.conversation_mode_expires_at = None
            await session.commit()
            return False
        return True


async def link_telegram_identity(
    telegram_user_id: int,
    *,
    username: Optional[str] = None,
    linked_at: Optional[datetime] = None,
) -> Optional[User]:
    """Ensure Telegram identifiers are stored even before the candidate finishes Test 1."""
    if not telegram_user_id:
        return None

    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_user_id)
        )
        user = result.scalar_one_or_none()
        now = datetime.now(timezone.utc)
        link_moment = linked_at or now

        if user:
            updated = False
            if user.telegram_user_id != telegram_user_id:
                user.telegram_user_id = telegram_user_id
                updated = True
            if user.telegram_linked_at is None:
                user.telegram_linked_at = link_moment
                updated = True
            if username is not None:
                if user.telegram_username != username:
                    user.telegram_username = username
                    updated = True
                if user.username != username:
                    user.username = username
                    updated = True
            if updated:
                user.last_activity = now
                await session.commit()
                await session.refresh(user)
            return user

        placeholder = User(
            telegram_id=telegram_user_id,
            telegram_user_id=telegram_user_id,
            telegram_username=username,
            telegram_linked_at=link_moment,
            username=username,
            fio=f"TG {telegram_user_id}",
            last_activity=now,
        )
        session.add(placeholder)
        await session.commit()
        await session.refresh(placeholder)
        return placeholder


async def update_candidate_reports(
    user_id: int,
    *,
    test1_path: Optional[str] = None,
    test2_path: Optional[str] = None,
) -> None:
    async with async_session() as session:
        user = await session.get(User, user_id)
        if not user:
            return
        updated = False
        if test1_path is not None:
            user.test1_report_url = test1_path
            updated = True
        if test2_path is not None:
            user.test2_report_url = test2_path
            updated = True
        if updated:
            await session.commit()


async def mark_manual_slot_requested(
    telegram_id: int,
    *,
    timezone_label: Optional[str] = None,
) -> None:
    """Store the moment when a manual slot was requested from the candidate."""
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        if not user:
            return
        user.manual_slot_requested_at = datetime.now(timezone.utc)
        if timezone_label:
            user.manual_slot_timezone = timezone_label
        await session.commit()


async def mark_manual_slot_requested_for_candidate(
    candidate_id: int,
    *,
    timezone_label: Optional[str] = None,
) -> None:
    async with async_session() as session:
        user = await session.get(User, int(candidate_id))
        if not user:
            return
        user.manual_slot_requested_at = datetime.now(timezone.utc)
        if timezone_label:
            user.manual_slot_timezone = timezone_label
        await session.commit()


async def save_manual_slot_response(
    telegram_id: int,
    *,
    window_start: Optional[datetime],
    window_end: Optional[datetime],
    note: Optional[str],
    timezone_label: Optional[str],
) -> Optional[User]:
    """Persist candidate-provided availability for manual slot assignment."""
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        if not user:
            return None
        await save_manual_slot_response_for_user(
            session,
            user,
            window_start=window_start,
            window_end=window_end,
            note=note,
            timezone_label=timezone_label,
        )
        await session.commit()
        await session.refresh(user)
        return user


async def save_manual_slot_response_for_user(
    session: AsyncSession,
    user: User,
    *,
    window_start: Optional[datetime],
    window_end: Optional[datetime],
    note: Optional[str],
    timezone_label: Optional[str],
) -> User:
    """Persist candidate availability inside the caller's transaction."""
    user.manual_slot_from = window_start
    user.manual_slot_to = window_end
    user.manual_slot_comment = note
    if timezone_label:
        user.manual_slot_timezone = timezone_label
    if user.manual_slot_requested_at is None:
        user.manual_slot_requested_at = datetime.now(timezone.utc)
    user.manual_slot_response_at = datetime.now(timezone.utc)
    await session.flush()
    return user
