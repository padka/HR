import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from .db import init_db, SessionLocal
from .models import City, Recruiter, Slot, SlotStatus


async def seed():
    await init_db()

    async with SessionLocal() as s:
        # --- Cities (idempotent) ---
        tz_map = {
            "Москва": "Europe/Moscow",
            "Новосибирск": "Asia/Novosibirsk",
            "Алматы": "Asia/Almaty",
            "Самара": "Europe/Samara",
        }
        existing = {c.name: c for c in (await s.scalars(select(City))).all()}
        for name, tz in tz_map.items():
            if name not in existing:
                s.add(City(name=name, tz=tz, active=True))
        await s.commit()

        # --- Recruiter Михаил (idempotent) ---
        rec = await s.scalar(select(Recruiter).where(Recruiter.name == "Михаил"))
        if not rec:
            rec = Recruiter(
                name="Михаил",
                tz="Europe/Moscow",
                active=True,
                telemost_url="https://telemost.yandex.ru/j/REPLACE_ME",
                tg_chat_id=None,  # привяжем позже /iam_mih
            )
            s.add(rec)
            await s.commit()
            await s.refresh(rec)

        # --- Пара свободных слотов вперёд на сегодня ---
        now = datetime.now(timezone.utc)
        for h in (3, 5):
            start = (now + timedelta(hours=h)).replace(minute=0, second=0, microsecond=0)
            exists = await s.scalar(select(Slot).where(Slot.recruiter_id == rec.id, Slot.start_utc == start))
            if not exists:
                s.add(Slot(recruiter_id=rec.id, start_utc=start, status=SlotStatus.FREE))
        await s.commit()

    print("DB initialized & seeded.")


if __name__ == "__main__":
    asyncio.run(seed())