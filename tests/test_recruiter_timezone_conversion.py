"""
Тесты для проверки конвертации времени рекрутера в timezone города кандидата.

Сценарий: Рекрутер в Москве (UTC+3) создает слот для Новосибирска (UTC+7) на 10:00.
Ожидаемый результат: Слот сохраняется в UTC как 07:00, кандидату показывается 14:00.
"""
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from backend.apps.admin_ui.services.slots import create_slot, list_slots
from backend.apps.bot.services import slot_local_labels
from backend.core.db import async_session
from backend.domain.models import City, Recruiter, Slot


@pytest.mark.asyncio
async def test_recruiter_time_converts_to_candidate_timezone():
    """
    Проверяем, что время рекрутера корректно конвертируется для кандидата.

    Рекрутер в Москве (UTC+3) создает слот на 10:00 для Новосибирска (UTC+7).
    Ожидаем: UTC время = 07:00, кандидат видит 14:00 по Новосибирску.
    """
    target_day = date.today() + timedelta(days=30)

    async with async_session() as session:
        # Москва (UTC+3 летом)
        moscow_city = City(name="Москва", tz="Europe/Moscow", active=True)
        # Новосибирск (UTC+7 круглый год)
        novosibirsk_city = City(name="Новосибирск", tz="Asia/Novosibirsk", active=True)

        # Рекрутер в Москве
        recruiter = Recruiter(name="Moscow Recruiter", tz="Europe/Moscow", active=True)
        recruiter.cities.append(moscow_city)
        recruiter.cities.append(novosibirsk_city)

        session.add_all([moscow_city, novosibirsk_city, recruiter])
        await session.commit()
        await session.refresh(recruiter)
        await session.refresh(novosibirsk_city)

        recruiter_id = recruiter.id
        city_id = novosibirsk_city.id
        city_tz = novosibirsk_city.tz
        session.expunge_all()

    # Рекрутер создает слот на 10:00 по своему времени (Москва)
    success = await create_slot(
        recruiter_id=recruiter_id,
        date=str(target_day),
        time="10:00",
        city_id=city_id,
    )
    assert success, "Slot creation should succeed"

    # Проверяем, что слот сохранен с правильным UTC временем
    async with async_session() as session:
        slot = (
            await session.execute(
                Slot.__table__.select()
                .where(Slot.recruiter_id == recruiter_id)
                .where(Slot.city_id == city_id)
            )
        ).first()

    assert slot is not None, "Slot should be created"

    # 10:00 MSK (UTC+3) = 07:00 UTC
    slot_utc = slot.start_utc.replace(tzinfo=timezone.utc)
    assert slot_utc.hour == 7, f"Expected UTC hour 7, got {slot_utc.hour}"
    assert slot_utc.minute == 0, f"Expected UTC minute 0, got {slot_utc.minute}"

    # Кандидат должен видеть 14:00 по Новосибирску (UTC+7)
    labels = slot_local_labels(slot_utc, city_tz)
    assert labels["slot_time_local"] == "14:00", f"Expected 14:00 for candidate, got {labels['slot_time_local']}"


@pytest.mark.asyncio
async def test_same_timezone_no_conversion():
    """
    Проверяем, что для одного timezone конвертация работает корректно.

    Рекрутер и кандидат в Москве. Слот на 15:00 должен остаться 15:00.
    """
    target_day = date.today() + timedelta(days=30)

    async with async_session() as session:
        moscow_city = City(name="Test Moscow", tz="Europe/Moscow", active=True)
        recruiter = Recruiter(name="Test Moscow Recruiter", tz="Europe/Moscow", active=True)
        recruiter.cities.append(moscow_city)

        session.add_all([moscow_city, recruiter])
        await session.commit()
        await session.refresh(recruiter)
        await session.refresh(moscow_city)

        recruiter_id = recruiter.id
        city_id = moscow_city.id
        city_tz = moscow_city.tz
        session.expunge_all()

    success = await create_slot(
        recruiter_id=recruiter_id,
        date=str(target_day),
        time="15:00",
        city_id=city_id,
    )
    assert success

    async with async_session() as session:
        slot = (
            await session.execute(
                Slot.__table__.select()
                .where(Slot.recruiter_id == recruiter_id)
                .where(Slot.city_id == city_id)
            )
        ).first()

    assert slot is not None

    # 15:00 MSK = 12:00 UTC (летом UTC+3)
    slot_utc = slot.start_utc.replace(tzinfo=timezone.utc)
    assert slot_utc.hour == 12

    # Кандидат должен видеть 15:00 по Москве
    labels = slot_local_labels(slot_utc, city_tz)
    assert labels["slot_time_local"] == "15:00"


@pytest.mark.asyncio
async def test_ekaterinburg_timezone_conversion():
    """
    Проверяем конвертацию для Екатеринбурга (UTC+5).

    Рекрутер в Москве (UTC+3) создает слот на 09:00 для Екатеринбурга (UTC+5).
    Ожидаем: UTC = 06:00, кандидат видит 11:00.
    """
    target_day = date.today() + timedelta(days=30)

    async with async_session() as session:
        ekb_city = City(name="Екатеринбург", tz="Asia/Yekaterinburg", active=True)
        recruiter = Recruiter(name="Ekb Test Recruiter", tz="Europe/Moscow", active=True)
        recruiter.cities.append(ekb_city)

        session.add_all([ekb_city, recruiter])
        await session.commit()
        await session.refresh(recruiter)
        await session.refresh(ekb_city)

        recruiter_id = recruiter.id
        city_id = ekb_city.id
        city_tz = ekb_city.tz
        session.expunge_all()

    success = await create_slot(
        recruiter_id=recruiter_id,
        date=str(target_day),
        time="09:00",
        city_id=city_id,
    )
    assert success

    async with async_session() as session:
        slot = (
            await session.execute(
                Slot.__table__.select()
                .where(Slot.recruiter_id == recruiter_id)
                .where(Slot.city_id == city_id)
            )
        ).first()

    assert slot is not None

    # 09:00 MSK (UTC+3) = 06:00 UTC
    slot_utc = slot.start_utc.replace(tzinfo=timezone.utc)
    assert slot_utc.hour == 6

    # Кандидат должен видеть 11:00 по Екатеринбургу (UTC+5)
    labels = slot_local_labels(slot_utc, city_tz)
    assert labels["slot_time_local"] == "11:00"
