from __future__ import annotations

from typing import Dict

from sqlalchemy import func, select

from backend.core.db import async_session
from backend.domain.models import City, Recruiter, Slot, SlotStatus

__all__ = ["dashboard_counts"]


async def dashboard_counts() -> Dict[str, int]:
    async with async_session() as session:
        rec_count = await session.scalar(select(func.count()).select_from(Recruiter))
        city_count = await session.scalar(select(func.count()).select_from(City))
        rows = (await session.execute(select(Slot.status, func.count()).group_by(Slot.status))).all()

    status_map: Dict[str, int] = {
        (status.value if hasattr(status, "value") else status): count for status, count in rows
    }
    total = sum(status_map.values())

    def _norm(name: str) -> str:
        obj = getattr(SlotStatus, name, name)
        return obj.value if hasattr(obj, "value") else obj

    return {
        "recruiters": rec_count or 0,
        "cities": city_count or 0,
        "slots_total": total,
        "slots_free": status_map.get(_norm("FREE"), 0),
        "slots_pending": status_map.get(_norm("PENDING"), 0),
        "slots_booked": status_map.get(_norm("BOOKED"), 0),
    }
