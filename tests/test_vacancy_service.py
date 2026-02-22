"""Tests for vacancy CRUD and question resolution chain."""

import pytest

from backend.apps.admin_ui.services.vacancies import (
    create_vacancy,
    delete_vacancy,
    get_vacancy,
    get_vacancy_questions,
    list_vacancies,
    resolve_questions_for_city,
    update_vacancy,
)
from backend.core.db import async_session
from backend.domain.models import City, TestQuestion, Vacancy


@pytest.mark.asyncio
async def test_create_and_list_global_vacancy():
    ok, errors, vacancy = await create_vacancy(
        title="Продавец-консультант",
        slug="seller-global-test",
        city_id=None,
    )
    assert ok, errors
    assert vacancy is not None

    try:
        vacancies = await list_vacancies()
        ids = [v.id for v in vacancies]
        assert vacancy.id in ids

        # Global vacancy has no city
        matching = [v for v in vacancies if v.id == vacancy.id]
        assert matching[0].city_id is None
        assert matching[0].city_name is None
    finally:
        await delete_vacancy(vacancy.id)


@pytest.mark.asyncio
async def test_create_vacancy_validates_slug():
    ok, errors, _ = await create_vacancy(
        title="Test",
        slug="UPPERCASE IS INVALID",
    )
    assert not ok
    assert any("slug" in e for e in errors)


@pytest.mark.asyncio
async def test_create_vacancy_validates_duplicate_slug():
    ok1, _, v1 = await create_vacancy(title="First", slug="unique-slug-dup-test")
    assert ok1
    try:
        ok2, errors2, _ = await create_vacancy(title="Second", slug="unique-slug-dup-test")
        assert not ok2
        assert any("slug" in e.lower() or "уже" in e for e in errors2)
    finally:
        if v1:
            await delete_vacancy(v1.id)


@pytest.mark.asyncio
async def test_update_vacancy():
    ok, _, vacancy = await create_vacancy(title="Original", slug="update-test-vac")
    assert ok

    try:
        ok2, errors2, updated = await update_vacancy(
            vacancy.id, title="Updated Title", is_active=False
        )
        assert ok2, errors2
        assert updated.title == "Updated Title"
        assert updated.is_active is False
    finally:
        await delete_vacancy(vacancy.id)


@pytest.mark.asyncio
async def test_resolve_questions_global_fallback():
    """When no vacancies exist, falls back to global question bank."""
    ok, _, vacancy = await create_vacancy(title="Fallback test", slug="fallback-vacancy-t")
    assert ok

    # Add a question to the vacancy for test1
    async with async_session() as session:
        q = TestQuestion(
            test_id="test1",
            question_index=99,
            title="Fallback question",
            payload='{"type": "text"}',
            is_active=True,
            vacancy_id=vacancy.id,
        )
        session.add(q)
        await session.commit()
        await session.refresh(q)
        q_id = q.id

    try:
        # No city → resolves global vacancy
        questions, source = await resolve_questions_for_city("test1", city_id=None)
        # Our vacancy is global (city_id=None) and has questions → should be "global_vacancy"
        assert source == "global_vacancy"
        q_ids = [qq.id for qq in questions]
        assert q_id in q_ids
    finally:
        async with async_session() as session:
            q = await session.get(TestQuestion, q_id)
            if q:
                await session.delete(q)
                await session.commit()
        await delete_vacancy(vacancy.id)


@pytest.mark.asyncio
async def test_resolve_questions_city_vacancy_takes_precedence():
    """City-specific vacancy takes precedence over global vacancy."""
    async with async_session() as session:
        city = City(name="VacancyTestCity", tz="Europe/Moscow", active=True)
        session.add(city)
        await session.commit()
        await session.refresh(city)
        city_id = city.id

    global_ok, _, global_vacancy = await create_vacancy(
        title="Global", slug="global-v-city-test"
    )
    city_ok, _, city_vacancy = await create_vacancy(
        title="City-specific", slug="city-v-city-test", city_id=city_id
    )
    assert global_ok and city_ok

    async with async_session() as session:
        qg = TestQuestion(test_id="test1", question_index=1, title="Global Q", payload='{}', is_active=True, vacancy_id=global_vacancy.id)
        qc = TestQuestion(test_id="test1", question_index=1, title="City Q", payload='{}', is_active=True, vacancy_id=city_vacancy.id)
        session.add_all([qg, qc])
        await session.commit()
        await session.refresh(qg)
        await session.refresh(qc)
        qg_id, qc_id = qg.id, qc.id

    try:
        questions, source = await resolve_questions_for_city("test1", city_id=city_id)
        assert source == "city_vacancy"
        q_ids = [q.id for q in questions]
        assert qc_id in q_ids
        assert qg_id not in q_ids
    finally:
        async with async_session() as session:
            for qid in (qg_id, qc_id):
                row = await session.get(TestQuestion, qid)
                if row:
                    await session.delete(row)
            await session.commit()
        await delete_vacancy(global_vacancy.id)
        await delete_vacancy(city_vacancy.id)
        async with async_session() as session:
            city_row = await session.get(City, city_id)
            if city_row:
                await session.delete(city_row)
            await session.commit()
