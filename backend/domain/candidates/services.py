from __future__ import annotations

from datetime import datetime, timezone, timedelta
import secrets
import uuid
from typing import List, Optional, Sequence, TYPE_CHECKING

from sqlalchemy import func, select, update

from backend.core.db import async_session
from backend.domain import analytics
from .models import (
    AutoMessage,
    Notification,
    QuestionAnswer,
    TestResult,
    User,
    ChatMessage,
    ChatMessageDirection,
    ChatMessageStatus,
    CandidateInviteToken,
)

if TYPE_CHECKING:
    from .status import CandidateStatus


async def create_or_update_user(
    telegram_id: int,
    fio: str,
    city: str,
    username: Optional[str] = None,
    initial_status: Optional[CandidateStatus] = None,
    *,
    candidate_id: Optional[str] = None,
    source: Optional[str] = None,
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
        if user:
            user.fio = fio
            user.city = city
            user.last_activity = now
            if not user.candidate_id:
                user.candidate_id = candidate_id or str(uuid.uuid4())
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
            }
            if candidate_id:
                payload["candidate_id"] = candidate_id
            user = User(**payload)
            session.add(user)
        await session.commit()
        await session.refresh(user)
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
    error: Optional[str] = None,
) -> None:
    async with async_session() as session:
        message = await session.get(ChatMessage, message_id)
        if not message:
            return
        message.status = status.value
        if telegram_message_id is not None:
            message.telegram_message_id = telegram_message_id
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


def _generate_invite_token() -> str:
    return secrets.token_urlsafe(8).rstrip("=")


async def create_candidate_invite_token(candidate_id: str) -> CandidateInviteToken:
    async with async_session() as session:
        async with session.begin():
            token_value = _generate_invite_token()
            for _ in range(5):
                exists = await session.scalar(
                    select(func.count()).where(CandidateInviteToken.token == token_value)
                )
                if not exists:
                    break
                token_value = _generate_invite_token()

            invite = CandidateInviteToken(
                candidate_id=candidate_id,
                token=token_value,
                created_at=datetime.now(timezone.utc),
            )
            session.add(invite)
        await session.refresh(invite)
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
                select(CandidateInviteToken).where(
                    CandidateInviteToken.token == clean_token,
                    CandidateInviteToken.used_at.is_(None),
                )
            )
            if not invite:
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
            invite.used_by_telegram_id = telegram_id

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
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
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
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
        if not user:
            return None
        user.manual_slot_from = window_start
        user.manual_slot_to = window_end
        user.manual_slot_comment = note
        if timezone_label:
            user.manual_slot_timezone = timezone_label
        if user.manual_slot_requested_at is None:
            user.manual_slot_requested_at = datetime.now(timezone.utc)
        user.manual_slot_response_at = datetime.now(timezone.utc)
        await session.commit()
        await session.refresh(user)
        return user
