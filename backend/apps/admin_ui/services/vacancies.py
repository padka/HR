"""Vacancy CRUD service — manages named question-sets for Test1/Test2."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import select, delete
from sqlalchemy.exc import IntegrityError

from backend.core.db import async_session
from backend.domain.models import City, TestQuestion, Vacancy

logger = logging.getLogger(__name__)

_SLUG_RE = re.compile(r"^[a-z0-9_-]{2,80}$")


@dataclass(frozen=True)
class VacancySummary:
    id: int
    title: str
    slug: str
    city_id: Optional[int]
    city_name: Optional[str]
    is_active: bool
    description: Optional[str]
    test1_question_count: int
    test2_question_count: int
    created_at: datetime
    updated_at: datetime


async def list_vacancies(*, city_id: Optional[int] = None) -> List[VacancySummary]:
    """Return all vacancies, optionally filtered by city (None = all)."""
    async with async_session() as session:
        stmt = select(Vacancy).order_by(Vacancy.city_id.nullsfirst(), Vacancy.title)
        if city_id is not None:
            stmt = stmt.where(Vacancy.city_id == city_id)
        rows = (await session.scalars(stmt)).all()

        summaries = []
        for v in rows:
            city_name: Optional[str] = None
            if v.city_id:
                city = await session.get(City, v.city_id)
                city_name = city.name if city else None

            # Count questions per test_id
            q1 = await session.scalars(
                select(TestQuestion).where(
                    TestQuestion.vacancy_id == v.id,
                    TestQuestion.test_id == "test1",
                    TestQuestion.is_active.is_(True),
                )
            )
            q2 = await session.scalars(
                select(TestQuestion).where(
                    TestQuestion.vacancy_id == v.id,
                    TestQuestion.test_id == "test2",
                    TestQuestion.is_active.is_(True),
                )
            )
            summaries.append(
                VacancySummary(
                    id=v.id,
                    title=v.title,
                    slug=v.slug,
                    city_id=v.city_id,
                    city_name=city_name,
                    is_active=v.is_active,
                    description=v.description,
                    test1_question_count=len(list(q1.all())),
                    test2_question_count=len(list(q2.all())),
                    created_at=v.created_at,
                    updated_at=v.updated_at,
                )
            )
        return summaries


async def get_vacancy(vacancy_id: int) -> Optional[Vacancy]:
    async with async_session() as session:
        return await session.get(Vacancy, vacancy_id)


def _validate_vacancy_fields(
    title: str, slug: str
) -> List[str]:
    errors: List[str] = []
    if not title or not title.strip():
        errors.append("title: обязательное поле")
    elif len(title.strip()) > 200:
        errors.append("title: максимум 200 символов")
    if not slug or not slug.strip():
        errors.append("slug: обязательное поле")
    elif not _SLUG_RE.match(slug.strip()):
        errors.append("slug: допустимы строчные буквы, цифры, дефис и подчёркивание (2–80 символов)")
    return errors


async def create_vacancy(
    *,
    title: str,
    slug: str,
    city_id: Optional[int] = None,
    description: Optional[str] = None,
    is_active: bool = True,
) -> tuple[bool, List[str], Optional[Vacancy]]:
    """Create a vacancy. Returns (ok, errors, vacancy)."""
    errors = _validate_vacancy_fields(title, slug)
    if errors:
        return False, errors, None

    vacancy = Vacancy(
        title=title.strip(),
        slug=slug.strip(),
        city_id=city_id,
        description=description,
        is_active=is_active,
    )
    try:
        async with async_session() as session:
            session.add(vacancy)
            await session.commit()
            await session.refresh(vacancy)
        return True, [], vacancy
    except IntegrityError:
        return False, [f"slug '{slug}' уже используется"], None


async def update_vacancy(
    vacancy_id: int,
    *,
    title: Optional[str] = None,
    slug: Optional[str] = None,
    city_id: Optional[int] = None,  # pass -1 to clear (set NULL)
    description: Optional[str] = None,
    is_active: Optional[bool] = None,
) -> tuple[bool, List[str], Optional[Vacancy]]:
    """Update a vacancy. Returns (ok, errors, vacancy)."""
    async with async_session() as session:
        vacancy = await session.get(Vacancy, vacancy_id)
        if vacancy is None:
            return False, ["Вакансия не найдена"], None

        new_title = title.strip() if title is not None else vacancy.title
        new_slug = slug.strip() if slug is not None else vacancy.slug
        errors = _validate_vacancy_fields(new_title, new_slug)
        if errors:
            return False, errors, None

        vacancy.title = new_title
        vacancy.slug = new_slug
        if city_id is not None:
            vacancy.city_id = None if city_id == -1 else city_id
        if description is not None:
            vacancy.description = description
        if is_active is not None:
            vacancy.is_active = is_active
        vacancy.updated_at = datetime.now(timezone.utc)

        try:
            await session.commit()
            await session.refresh(vacancy)
            return True, [], vacancy
        except IntegrityError:
            return False, [f"slug '{new_slug}' уже используется"], None


async def delete_vacancy(vacancy_id: int) -> bool:
    """Delete a vacancy and all its questions. Returns True if deleted."""
    async with async_session() as session:
        vacancy = await session.get(Vacancy, vacancy_id)
        if vacancy is None:
            return False
        await session.delete(vacancy)
        await session.commit()
        return True


async def get_vacancy_questions(
    vacancy_id: int, test_id: str
) -> List[TestQuestion]:
    """Return questions belonging to a vacancy for a given test."""
    async with async_session() as session:
        rows = await session.scalars(
            select(TestQuestion)
            .where(
                TestQuestion.vacancy_id == vacancy_id,
                TestQuestion.test_id == test_id,
            )
            .order_by(TestQuestion.question_index)
        )
        return list(rows.all())


async def resolve_questions_for_city(
    test_id: str, city_id: Optional[int]
) -> tuple[List[TestQuestion], str]:
    """Resolve questions using vacancy chain: city-vacancy → global-vacancy → global.
    
    Returns (questions, source) where source is 'city_vacancy', 'global_vacancy', or 'global'.
    """
    async with async_session() as session:
        # 1. City-specific vacancy
        if city_id is not None:
            city_vacancy = await session.scalar(
                select(Vacancy).where(
                    Vacancy.city_id == city_id,
                    Vacancy.is_active.is_(True),
                )
            )
            if city_vacancy:
                qs = await session.scalars(
                    select(TestQuestion).where(
                        TestQuestion.vacancy_id == city_vacancy.id,
                        TestQuestion.test_id == test_id,
                        TestQuestion.is_active.is_(True),
                    ).order_by(TestQuestion.question_index)
                )
                questions = list(qs.all())
                if questions:
                    return questions, "city_vacancy"

        # 2. Global vacancy (city_id IS NULL)
        global_vacancy = await session.scalar(
            select(Vacancy).where(
                Vacancy.city_id.is_(None),
                Vacancy.is_active.is_(True),
            )
        )
        if global_vacancy:
            qs = await session.scalars(
                select(TestQuestion).where(
                    TestQuestion.vacancy_id == global_vacancy.id,
                    TestQuestion.test_id == test_id,
                    TestQuestion.is_active.is_(True),
                ).order_by(TestQuestion.question_index)
            )
            questions = list(qs.all())
            if questions:
                return questions, "global_vacancy"

        # 3. Global question bank (vacancy_id IS NULL)
        qs = await session.scalars(
            select(TestQuestion).where(
                TestQuestion.test_id == test_id,
                TestQuestion.vacancy_id.is_(None),
                TestQuestion.is_active.is_(True),
            ).order_by(TestQuestion.question_index)
        )
        return list(qs.all()), "global"
