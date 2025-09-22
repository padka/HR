import asyncio
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select

from .db import init_db, SessionLocal
from .models import Recruiter, City, Template, Slot, SlotStatus


async def seed():
    await init_db()
    async with SessionLocal() as session:
        # 1) Рекрутёр Михаил
        rec = await session.scalar(select(Recruiter).where(Recruiter.name == "Михаил"))
        if not rec:
            rec = Recruiter(
                name="Михаил",
                tg_chat_id=7588303412,  # при необходимости поменяешь
                tz="Europe/Moscow",
                telemost_url="https://telemost.yandex.ru/j/REPLACE_ME",
                active=True,
            )
            session.add(rec)
            await session.flush()

        # 2) Города (IANA таймзоны)
        def get_or_create_city(name: str, tz: str):
            return session.scalar(select(City).where(City.name == name)), tz

        cities_want = [
            ("Сочи", "Europe/Moscow"),
            ("Новосибирск", "Asia/Novosibirsk"),
            ("Алматы", "Asia/Almaty"),
            ("Самара", "Europe/Samara"),
        ]
        city_objs = {}
        for name, tz in cities_want:
            city = await session.scalar(select(City).where(City.name == name))
            if not city:
                city = City(name=name, tz=tz, active=True)
                session.add(city)
                await session.flush()
            city_objs[name] = city

        # 3) Шаблоны по городам (минимальный набор)
        base_templates = {
            "approved": "✅ Ваша встреча подтверждена на {dt_local}. Рекрутёр: {recruiter}. Детали придут отдельно.",
            "confirm_2h": "⏰ Напоминание: встреча через 2 часа — {dt_local}. Подтвердите участие кнопкой ниже.",
            "reminder_1h": "⏰ Напоминание: встреча через 1 час — {dt_local}.",
            "decline": "К сожалению, слот недоступен. Давайте подберём другое время.",
            "link_after_confirm": "🔗 Ссылка на Яндекс.Телемост: {link}\\nВстречаемся {dt_local}.",
        }
        for city in city_objs.values():
            for key, content in base_templates.items():
                exists = await session.scalar(
                    select(Template).where(Template.city_id == city.id, Template.key == key)
                )
                if not exists:
                    session.add(Template(city_id=city.id, key=key, content=content))

        # 4) Пара слотов у Михаила (в UTC). Создадим на сегодня+3ч и сегодня+5ч по МСК.
        msk = ZoneInfo("Europe/Moscow")
        now_msk = datetime.now(msk)
        desired = [
            (now_msk + timedelta(hours=3)).replace(minute=0, second=0, microsecond=0),
            (now_msk + timedelta(hours=5)).replace(minute=0, second=0, microsecond=0),
            (now_msk + timedelta(days=1, hours=2)).replace(minute=0, second=0, microsecond=0),
        ]
        for dt_local in desired:
            start_utc = dt_local.astimezone(timezone.utc)
            exists = await session.scalar(
                select(Slot).where(
                    Slot.recruiter_id == rec.id,
                    Slot.start_utc == start_utc,
                )
            )
            if not exists:
                session.add(
                    Slot(
                        recruiter_id=rec.id,
                        city_id=city_objs["Сочи"].id,  # по умолчанию Сочи/МСК
                        start_utc=start_utc,
                        duration_min=60,
                        status=SlotStatus.FREE,
                    )
                )

        await session.commit()
    print("✅ Seed complete")


if __name__ == "__main__":
    asyncio.run(seed())