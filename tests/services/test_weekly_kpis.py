from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import delete, func, select

from backend.apps.admin_ui.services.kpis import (
    compute_weekly_snapshot,
    get_week_window,
    get_weekly_kpis,
    list_weekly_history,
    reset_weekly_cache,
    store_weekly_snapshot,
)
from backend.core.db import async_session
from backend.domain.candidates.models import TestResult, User
from backend.domain.models import City, KPIWeekly, Recruiter, Slot, SlotStatus


@pytest.mark.asyncio
async def test_week_window_uses_sunday_boundary(monkeypatch):
    monkeypatch.setenv("COMPANY_TZ", "Europe/Moscow")
    reference = datetime(2024, 3, 26, 12, tzinfo=timezone.utc)
    window = get_week_window(now=reference)

    assert window.week_start_local.weekday() == 6  # Sunday
    assert window.week_start_local.hour == 0
    assert window.week_start_local.minute == 0
    assert getattr(window.tz, "key", str(window.tz)) == "Europe/Moscow"


@pytest.mark.asyncio
async def test_weekly_kpis_compute_unique_counts(monkeypatch):
    monkeypatch.setenv("COMPANY_TZ", "Europe/Moscow")
    await reset_weekly_cache()

    now = datetime(2024, 3, 28, 9, tzinfo=timezone.utc)
    window = get_week_window(now=now)
    previous_week_start = window.week_start_date - timedelta(days=7)

    async with async_session() as session:
        await session.execute(
            delete(KPIWeekly).where(
                KPIWeekly.week_start.in_([window.week_start_date, previous_week_start])
            )
        )
        await session.execute(
            delete(TestResult).where(TestResult.user_id >= 1_000_000)
        )
        await session.execute(delete(User).where(User.telegram_id >= 1_000_000))
        await session.execute(delete(Slot).where(Slot.candidate_tg_id >= 9_000_000))
        await session.execute(delete(Recruiter).where(Recruiter.name == "KPI Demo"))
        await session.execute(delete(City).where(City.name == "KPI City"))
        await session.commit()

    async with async_session() as session:
        recruiter = Recruiter(name="KPI Demo", tz="Europe/Moscow", active=True)
        city = City(name="KPI City", tz="Europe/Moscow", active=True)
        session.add_all([recruiter, city])
        await session.flush()

        users = []
        for idx, fio in enumerate(["Анна", "Павел", "Наталья"], start=1):
            user = User(
                telegram_id=1_000_000 + idx,
                fio=f"{fio} KPI",
                city="Москва",
                is_active=True,
                last_activity=now,
            )
            session.add(user)
            await session.flush()
            users.append(user)

        session.add_all(
            [
                TestResult(
                    user_id=users[0].id,
                    raw_score=20,
                    final_score=88.0,
                    rating="A",
                    total_time=1200,
                    created_at=window.week_start_utc + timedelta(days=1),
                ),
                TestResult(
                    user_id=users[0].id,
                    raw_score=22,
                    final_score=92.0,
                    rating="A",
                    total_time=1180,
                    created_at=window.week_start_utc + timedelta(days=2),
                ),
                TestResult(
                    user_id=users[1].id,
                    raw_score=18,
                    final_score=80.0,
                    rating="B",
                    total_time=1320,
                    created_at=window.week_start_utc + timedelta(days=3),
                ),
                TestResult(
                    user_id=users[2].id,
                    raw_score=17,
                    final_score=76.0,
                    rating="C",
                    total_time=1420,
                    created_at=window.week_start_utc - timedelta(days=3),
                ),
            ]
        )

        slots = [
            Slot(
                recruiter_id=recruiter.id,
                city_id=city.id,
                start_utc=window.week_start_utc + timedelta(days=1),
                status=SlotStatus.PENDING,
                purpose="interview",
                candidate_tg_id=9_000_001,
                candidate_fio="Мария Лебедева",
                candidate_tz="Europe/Moscow",
                created_at=window.week_start_utc + timedelta(days=1),
                updated_at=window.week_start_utc + timedelta(days=1),
            ),
            Slot(
                recruiter_id=recruiter.id,
                city_id=city.id,
                start_utc=window.week_start_utc + timedelta(days=2, hours=3),
                status=SlotStatus.CONFIRMED_BY_CANDIDATE,
                purpose="interview",
                candidate_tg_id=9_000_002,
                candidate_fio="Софья Егорова",
                candidate_tz="Europe/Samara",
                created_at=window.week_start_utc + timedelta(days=2),
                updated_at=window.week_start_utc + timedelta(days=2, hours=2),
            ),
            Slot(
                recruiter_id=recruiter.id,
                city_id=city.id,
                start_utc=window.week_start_utc + timedelta(days=3, hours=4),
                status=SlotStatus.BOOKED,
                purpose="interview",
                candidate_tg_id=9_000_003,
                candidate_fio="Дмитрий Титов",
                candidate_tz="Europe/Moscow",
                interview_outcome="success",
                created_at=window.week_start_utc + timedelta(days=3),
                updated_at=window.week_start_utc + timedelta(days=3, hours=5),
            ),
            Slot(
                recruiter_id=recruiter.id,
                city_id=city.id,
                start_utc=window.week_start_utc + timedelta(days=5, hours=1),
                status=SlotStatus.CONFIRMED_BY_CANDIDATE,
                purpose="intro_day",
                candidate_tg_id=9_000_004,
                candidate_fio="Ирина Ким",
                candidate_tz="Europe/Moscow",
                created_at=window.week_start_utc + timedelta(days=5),
                updated_at=window.week_start_utc + timedelta(days=5, hours=1),
            ),
        ]
        session.add_all(slots)

        await session.commit()

    snapshot_prev = await compute_weekly_snapshot(previous_week_start, tz_name="Europe/Moscow")
    await store_weekly_snapshot(snapshot_prev)
    await reset_weekly_cache()

    async with async_session() as session:
        unique_users = await session.scalar(
            select(func.count(func.distinct(TestResult.user_id))).where(
                TestResult.created_at >= window.week_start_utc,
                TestResult.created_at < window.week_end_utc,
            )
        )
    assert unique_users == 2

    data = await get_weekly_kpis(now=now)
    metrics = {card["key"]: card for card in data["current"]["metrics"]}

    assert metrics["tested"]["value"] == 2
    assert metrics["completed_test"]["value"] == 2
    assert metrics["booked"]["value"] == 3
    assert metrics["confirmed"]["value"] == 1
    assert metrics["interview_passed"]["value"] == 1
    assert metrics["intro_day"]["value"] == 1

    assert metrics["tested"]["trend"]["display"] == "↑ 100%"
    assert metrics["intro_day"]["trend"]["display"] == "—"

    booked_details = metrics["booked"]["details"]
    assert any(item["candidate"] == "Мария Лебедева" for item in booked_details)
    assert any(item["candidate"] == "Софья Егорова" for item in booked_details)

    snapshot_current = await compute_weekly_snapshot(window.week_start_date, tz_name="Europe/Moscow")
    await store_weekly_snapshot(snapshot_current)

    history = await list_weekly_history(limit=4)
    weeks = {entry["week_start"] for entry in history}
    assert window.week_start_date.isoformat() in weeks
    assert previous_week_start.isoformat() in weeks


@pytest.mark.asyncio
async def test_weekly_kpis_respects_performance_budget(monkeypatch):
    monkeypatch.setenv("COMPANY_TZ", "Europe/Moscow")
    await reset_weekly_cache()

    reference = datetime(2024, 4, 2, 8, tzinfo=timezone.utc)
    window = get_week_window(now=reference)

    async with async_session() as session:
        recruiter = Recruiter(name="Perf Recruiter", tz="Europe/Moscow", active=True)
        city = City(name="Perf City", tz="Europe/Moscow", active=True)
        session.add_all([recruiter, city])
        await session.flush()

        entries = []
        for index in range(200):
            user = User(
                telegram_id=2_000_000 + index,
                fio=f"Candidate {index}",
                city="Москва",
                is_active=True,
                last_activity=reference,
            )
            session.add(user)
            await session.flush()
            entries.append(
                TestResult(
                    user_id=user.id,
                    raw_score=10,
                    final_score=75.0,
                    rating="B",
                    total_time=900,
                    created_at=window.week_start_utc + timedelta(minutes=index * 15),
                )
            )
            session.add(
                Slot(
                    recruiter_id=recruiter.id,
                    city_id=city.id,
                    start_utc=window.week_start_utc + timedelta(minutes=index * 15),
                    status=SlotStatus.PENDING,
                    purpose="interview",
                    candidate_tg_id=9_500_000 + index,
                    candidate_fio=f"Perf {index}",
                    candidate_tz="Europe/Moscow",
                    created_at=window.week_start_utc + timedelta(minutes=index * 15),
                    updated_at=window.week_start_utc + timedelta(minutes=index * 15),
                )
            )
        session.add_all(entries)
        await session.commit()

    await reset_weekly_cache()
    start = time.perf_counter()
    await get_weekly_kpis()
    elapsed_ms = (time.perf_counter() - start) * 1000
    assert elapsed_ms < 500, f"Expected <500ms, got {elapsed_ms:.2f}ms"
