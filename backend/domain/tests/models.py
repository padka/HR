from typing import List, Optional
from sqlalchemy import String, Integer, ForeignKey, Text, Boolean, Float, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.domain.base import Base

class Test(Base):
    __tablename__ = "tests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)

    questions: Mapped[List["Question"]] = relationship(
        back_populates="test", cascade="all, delete-orphan", order_by="Question.order"
    )

    def __repr__(self) -> str:
        return f"<Test {self.slug}>"


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    test_id: Mapped[int] = mapped_column(ForeignKey("tests.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    text: Mapped[str] = mapped_column(Text, nullable=False)
    key: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    type: Mapped[str] = mapped_column(String(32), nullable=False, default="single_choice")
    order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    test: Mapped["Test"] = relationship(back_populates="questions")
    answer_options: Mapped[List["AnswerOption"]] = relationship(
        back_populates="question", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Question {self.id} test={self.test_id}>"


class AnswerOption(Base):
    __tablename__ = "answer_options"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id", ondelete="CASCADE"), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    points: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    question: Mapped["Question"] = relationship(back_populates="answer_options")

    def __repr__(self) -> str:
        return f"<AnswerOption {self.id} question={self.question_id} correct={self.is_correct}>"
