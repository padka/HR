from __future__ import annotations

from contextlib import asynccontextmanager, contextmanager
from typing import AsyncIterator, Iterator

import json

from sqlalchemy import create_engine, text, select, func
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import Session, sessionmaker

from backend.core.settings import get_settings

_settings = get_settings()

async_engine: AsyncEngine = create_async_engine(
    _settings.database_url_async,
    echo=_settings.sql_echo,
    future=True,
)
_async_session_factory = async_sessionmaker(
    bind=async_engine,
    expire_on_commit=False,
    class_=AsyncSession,
)

sync_engine = create_engine(
    _settings.database_url_sync,
    echo=_settings.sql_echo,
    future=True,
)
_sync_session_factory = sessionmaker(
    bind=sync_engine,
    expire_on_commit=False,
    class_=Session,
)


async def init_models() -> None:
    """Ensure all ORM tables exist."""
    from backend.domain import models  # noqa: F401  # импортирует модели для metadata
    from backend.domain.candidates import models as candidates_models  # noqa: F401
    from backend.domain.base import Base

    async with async_engine.begin() as conn:
        await conn.run_sync(lambda sync_conn: Base.metadata.create_all(sync_conn, checkfirst=True))
        await _ensure_city_owner_column(conn)
        await _ensure_slot_purpose_column(conn)

    await _seed_defaults()


async def _ensure_city_owner_column(conn) -> None:
    """Добавляет колонку responsible_recruiter_id в cities при необходимости."""
    result = await conn.execute(text("PRAGMA table_info('cities')"))
    columns = {row[1] for row in result}
    if "responsible_recruiter_id" not in columns:
        await conn.execute(
            text(
                "ALTER TABLE cities ADD COLUMN responsible_recruiter_id INTEGER "
                "REFERENCES recruiters(id) ON DELETE SET NULL"
            )
        )


async def _ensure_slot_purpose_column(conn) -> None:
    """Гарантирует наличие вспомогательных столбцов в таблице slots."""
    result = await conn.execute(text("PRAGMA table_info('slots')"))
    columns = {row[1] for row in result}
    if "purpose" not in columns:
        await conn.execute(
            text(
                "ALTER TABLE slots ADD COLUMN purpose VARCHAR(32) NOT NULL DEFAULT 'interview'"
            )
        )
    if "candidate_city_id" not in columns:
        await conn.execute(
            text(
                "ALTER TABLE slots ADD COLUMN candidate_city_id INTEGER REFERENCES cities(id) ON DELETE SET NULL"
            )
        )


DEFAULT_CITIES = [
    {"name": "Москва", "tz": "Europe/Moscow"},
    {"name": "Санкт-Петербург", "tz": "Europe/Moscow"},
    {"name": "Новосибирск", "tz": "Asia/Novosibirsk"},
    {"name": "Екатеринбург", "tz": "Asia/Yekaterinburg"},
]

DEFAULT_RECRUITERS = [
    {
        "name": "Михаил Шеншин",
        "tz": "Europe/Moscow",
        "telemost_url": "https://telemost.yandex.ru/j/SMART_ONBOARDING",
        "active": True,
    },
    {
        "name": "Юлия Начауридзе",
        "tz": "Europe/Moscow",
        "telemost_url": "https://telemost.yandex.ru/j/SMART_RECRUIT",
        "active": True,
    },
]


async def _seed_defaults() -> None:
    from backend.domain.models import City, Recruiter, TestQuestion
    from backend.domain.default_questions import DEFAULT_TEST_QUESTIONS

    async with async_session() as session:
        for city_data in DEFAULT_CITIES:
            exists = await session.scalar(select(City).where(City.name == city_data["name"]))
            if not exists:
                session.add(City(**city_data))

        for rec_data in DEFAULT_RECRUITERS:
            exists = await session.scalar(select(Recruiter).where(Recruiter.name == rec_data["name"]))
            if not exists:
                session.add(Recruiter(**rec_data))

        existing_questions = await session.scalar(select(func.count()).select_from(TestQuestion))
        if not existing_questions:
            for test_id, questions in DEFAULT_TEST_QUESTIONS.items():
                for idx, question in enumerate(questions, start=1):
                    title = question.get("prompt") or question.get("text") or f"Вопрос {idx}"
                    session.add(
                        TestQuestion(
                            test_id=test_id,
                            question_index=idx,
                            title=title,
                            payload=json.dumps(question, ensure_ascii=False),
                        )
                    )

        await session.commit()


def new_async_session() -> AsyncSession:
    """Return a raw AsyncSession instance."""
    return _async_session_factory()


@asynccontextmanager
async def async_session() -> AsyncIterator[AsyncSession]:
    session = new_async_session()
    try:
        yield session
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


def new_sync_session() -> Session:
    """Return a raw synchronous Session instance."""
    return _sync_session_factory()


@contextmanager
def sync_session() -> Iterator[Session]:
    session = new_sync_session()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


__all__ = [
    "async_session",
    "new_async_session",
    "sync_session",
    "new_sync_session",
    "init_models",
    "async_engine",
    "sync_engine",
]
