from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Sequence

from sqlalchemy import func, select

from backend.core.db import async_session
from backend.core.settings import get_settings
from .models import (
    AutoMessage,
    CandidateTestOutcome,
    CandidateTestOutcomeDelivery,
    Notification,
    QuestionAnswer,
    TestResult,
    User,
)


@dataclass(slots=True)
class PersistedOutcome:
    outcome: CandidateTestOutcome
    created: bool


async def create_or_update_user(telegram_id: int, fio: str, city: str) -> User:
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        if user:
            user.fio = fio
            user.city = city
            user.last_activity = datetime.now(timezone.utc)
        else:
            user = User(
                telegram_id=telegram_id,
                fio=fio,
                city=city,
                last_activity=datetime.now(timezone.utc),
            )
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
) -> TestResult:
    async with async_session() as session:
        test_result = TestResult(
            user_id=user_id,
            raw_score=raw_score,
            final_score=final_score,
            rating=rating,
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


async def record_candidate_test_outcome(
    *,
    user_id: int,
    test_id: str,
    status: str,
    rating: Optional[str],
    score: float,
    correct_answers: int,
    total_questions: int,
    attempt_at: datetime,
    artifact_path: str,
    artifact_name: str,
    artifact_mime: str,
    artifact_size: int,
    payload: Optional[dict] = None,
) -> PersistedOutcome:
    payload_data = payload or {}
    attempt_value = attempt_at.astimezone(timezone.utc)

    async with async_session() as session:
        result = await session.execute(
            select(CandidateTestOutcome)
            .where(
                CandidateTestOutcome.user_id == user_id,
                CandidateTestOutcome.test_id == test_id,
                CandidateTestOutcome.attempt_at == attempt_value,
            )
            .limit(1)
        )
        outcome = result.scalar_one_or_none()
        created = False
        if outcome is None:
            outcome = CandidateTestOutcome(
                user_id=user_id,
                test_id=test_id,
                status=status,
                rating=rating,
                score=score,
                correct_answers=correct_answers,
                total_questions=total_questions,
                attempt_at=attempt_value,
                artifact_path=artifact_path,
                artifact_name=artifact_name,
                artifact_mime=artifact_mime,
                artifact_size=artifact_size,
                payload=payload_data,
            )
            session.add(outcome)
            created = True
        else:
            outcome.status = status
            outcome.rating = rating
            outcome.score = score
            outcome.correct_answers = correct_answers
            outcome.total_questions = total_questions
            outcome.attempt_at = attempt_value
            outcome.artifact_path = artifact_path
            outcome.artifact_name = artifact_name
            outcome.artifact_mime = artifact_mime
            outcome.artifact_size = artifact_size
            outcome.payload = payload_data

        await session.commit()
        await session.refresh(outcome)
        return PersistedOutcome(outcome=outcome, created=created)


async def list_candidate_test_outcomes(user_id: int) -> List[CandidateTestOutcome]:
    async with async_session() as session:
        rows = await session.execute(
            select(CandidateTestOutcome)
            .where(CandidateTestOutcome.user_id == user_id)
            .order_by(
                CandidateTestOutcome.attempt_at.desc(),
                CandidateTestOutcome.id.desc(),
            )
        )
        return list(rows.scalars().all())


async def was_test_outcome_delivered(outcome_id: int, chat_id: int) -> bool:
    async with async_session() as session:
        exists_query = await session.execute(
            select(CandidateTestOutcomeDelivery.id)
            .where(
                CandidateTestOutcomeDelivery.outcome_id == outcome_id,
                CandidateTestOutcomeDelivery.chat_id == chat_id,
            )
            .limit(1)
        )
        return exists_query.scalar_one_or_none() is not None


async def mark_test_outcome_delivered(
    outcome_id: int, chat_id: int, *, message_id: Optional[int] = None
) -> None:
    async with async_session() as session:
        existing = await session.execute(
            select(CandidateTestOutcomeDelivery)
            .where(
                CandidateTestOutcomeDelivery.outcome_id == outcome_id,
                CandidateTestOutcomeDelivery.chat_id == chat_id,
            )
            .limit(1)
        )
        delivery = existing.scalar_one_or_none()
        if delivery is not None:
            if message_id is not None and delivery.message_id != message_id:
                delivery.message_id = message_id
                await session.commit()
            return

        delivery = CandidateTestOutcomeDelivery(
            outcome_id=outcome_id,
            chat_id=chat_id,
            message_id=message_id,
        )
        session.add(delivery)
        await session.commit()


def resolve_test_outcome_artifact(artifact_path: str) -> Path:
    base_dir = get_settings().data_dir
    candidate_path = (base_dir / artifact_path).resolve()
    base_resolved = base_dir.resolve()
    if not str(candidate_path).startswith(str(base_resolved)):
        raise ValueError("Invalid artifact path")
    return candidate_path


async def get_user_by_telegram_id(telegram_id: int) -> Optional[User]:
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()


async def get_all_active_users() -> List[User]:
    async with async_session() as session:
        result = await session.scalars(select(User).where(User.is_active.is_(True)))
        return list(result.all())


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
