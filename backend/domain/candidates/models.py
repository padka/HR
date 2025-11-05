from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    BigInteger,
    Float,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.domain.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False)
    username: Mapped[Optional[str]] = mapped_column(String(32), index=True, nullable=True)
    fio: Mapped[str] = mapped_column(String(160), nullable=False)
    city: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    test1_report_url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    test2_report_url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_activity: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    test_results: Mapped[List["TestResult"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover - repr helper
        return f"<User {self.id} tg={self.telegram_id}>"


class TestResult(Base):
    __tablename__ = "test_results"
    __test__ = False  # pytest should not treat SQLAlchemy model as a test case

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    raw_score: Mapped[int] = mapped_column(Integer, nullable=False)
    final_score: Mapped[float] = mapped_column(Float, nullable=False)
    rating: Mapped[str] = mapped_column(String(50), nullable=False)
    total_time: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    user: Mapped["User"] = relationship(back_populates="test_results")
    answers: Mapped[List["QuestionAnswer"]] = relationship(
        back_populates="test_result", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover - repr helper
        return f"<TestResult {self.id} user={self.user_id} score={self.final_score}>"


class QuestionAnswer(Base):
    __tablename__ = "question_answers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    test_result_id: Mapped[int] = mapped_column(
        ForeignKey("test_results.id", ondelete="CASCADE"), nullable=False
    )
    question_index: Mapped[int] = mapped_column(Integer, nullable=False)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    correct_answer: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    user_answer: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    attempts_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    time_spent: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    overtime: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    test_result: Mapped["TestResult"] = relationship(back_populates="answers")

    __table_args__ = (
        UniqueConstraint("test_result_id", "question_index", name="uq_test_result_question"),
    )

    def __repr__(self) -> str:  # pragma: no cover - repr helper
        return f"<QuestionAnswer result={self.test_result_id} index={self.question_index}>"


class AutoMessage(Base):
    __tablename__ = "auto_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    message_text: Mapped[str] = mapped_column(Text, nullable=False)
    send_time: Mapped[str] = mapped_column(String(64), nullable=False)
    target_chat_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:  # pragma: no cover - repr helper
        return f"<AutoMessage {self.id} active={self.is_active}>"


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    admin_chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    notification_type: Mapped[str] = mapped_column(String(50), nullable=False)
    message_text: Mapped[str] = mapped_column(Text, nullable=False)
    is_sent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover - repr helper
        return f"<Notification {self.id} type={self.notification_type}>"
