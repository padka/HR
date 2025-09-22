from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable, List, Optional, Sequence

from sqlalchemy import func, select

from backend.core.db import sync_session
from .models import AutoMessage, Notification, QuestionAnswer, TestResult, User


def create_or_update_user(telegram_id: int, fio: str, city: str) -> User:
    with sync_session() as session:
        user = session.execute(
            select(User).where(User.telegram_id == telegram_id)
        ).scalar_one_or_none()
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
        session.commit()
        session.refresh(user)
        return user


def save_test_result(
    user_id: int,
    raw_score: int,
    final_score: float,
    rating: str,
    total_time: int,
    question_data: Sequence[dict],
) -> TestResult:
    with sync_session() as session:
        test_result = TestResult(
            user_id=user_id,
            raw_score=raw_score,
            final_score=final_score,
            rating=rating,
            total_time=total_time,
        )
        session.add(test_result)
        session.flush()  # ensure PK for FK usage

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

        session.commit()
        session.refresh(test_result)
        return test_result


def get_user_by_telegram_id(telegram_id: int) -> Optional[User]:
    with sync_session() as session:
        return session.execute(
            select(User).where(User.telegram_id == telegram_id)
        ).scalar_one_or_none()


def get_all_active_users() -> List[User]:
    with sync_session() as session:
        return (session.execute(select(User).where(User.is_active.is_(True))).scalars().all())


def get_test_statistics() -> dict:
    with sync_session() as session:
        total_tests = session.execute(select(func.count(TestResult.id))).scalar_one()
        completed_tests = total_tests

        if not completed_tests:
            return {
                "total_tests": 0,
                "completed_tests": 0,
                "average_score": 0,
                "success_rate": 0,
            }

        avg_score = session.execute(select(func.avg(TestResult.final_score))).scalar()
        successful_tests = session.execute(
            select(func.count(TestResult.id)).where(TestResult.final_score >= 3.5)
        ).scalar()

        return {
            "total_tests": total_tests,
            "completed_tests": completed_tests,
            "average_score": round(avg_score or 0, 2),
            "success_rate": round(((successful_tests or 0) / completed_tests) * 100, 2),
        }


def create_auto_message(
    message_text: str, send_time: str, target_chat_id: Optional[int] = None
) -> AutoMessage:
    with sync_session() as session:
        auto_message = AutoMessage(
            message_text=message_text,
            send_time=send_time,
            target_chat_id=target_chat_id,
        )
        session.add(auto_message)
        session.commit()
        session.refresh(auto_message)
        return auto_message


def get_active_auto_messages() -> List[AutoMessage]:
    with sync_session() as session:
        return (
            session.execute(select(AutoMessage).where(AutoMessage.is_active.is_(True))).scalars().all()
        )


def create_notification(
    admin_chat_id: int, notification_type: str, message_text: str
) -> Notification:
    with sync_session() as session:
        notification = Notification(
            admin_chat_id=admin_chat_id,
            notification_type=notification_type,
            message_text=message_text,
        )
        session.add(notification)
        session.commit()
        session.refresh(notification)
        return notification


def mark_notification_sent(notification_id: int) -> None:
    with sync_session() as session:
        notification = session.get(Notification, notification_id)
        if notification:
            notification.is_sent = True
            notification.sent_at = datetime.now(timezone.utc)
            session.commit()
