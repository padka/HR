from __future__ import annotations

from collections import defaultdict
from typing import Optional, Dict, List

from sqlalchemy import select, or_

from backend.apps.admin_ui.security import Principal
from backend.core.db import async_session
from backend.core.sanitizers import sanitize_plain_text
from backend.domain.models import City, RecruiterPlanEntry, recruiter_city_association


async def get_recruiter_plan(recruiter_id: int) -> List[Dict[str, object]]:
    async with async_session() as session:
        city_rows = await session.execute(
            select(City.id, City.name, City.tz, City.plan_week, City.plan_month)
            .outerjoin(recruiter_city_association, recruiter_city_association.c.city_id == City.id)
            .where(
                or_(
                    recruiter_city_association.c.recruiter_id == recruiter_id,
                    City.responsible_recruiter_id == recruiter_id,
                )
            )
            .group_by(City.id, City.name, City.tz, City.plan_week, City.plan_month)
            .order_by(City.name.asc())
        )
        cities = city_rows.all()
        city_ids = [row.id for row in cities]

        entries_by_city: Dict[int, List[RecruiterPlanEntry]] = defaultdict(list)
        if city_ids:
            entry_rows = await session.execute(
                select(RecruiterPlanEntry)
                .where(
                    RecruiterPlanEntry.recruiter_id == recruiter_id,
                    RecruiterPlanEntry.city_id.in_(city_ids),
                )
                .order_by(RecruiterPlanEntry.created_at.desc())
            )
            for entry in entry_rows.scalars().all():
                entries_by_city[entry.city_id].append(entry)

    payload: List[Dict[str, object]] = []
    for city_id, name, tz, plan_week, plan_month in cities:
        entries = entries_by_city.get(city_id, [])
        filled_count = len(entries)
        remaining_week = plan_week - filled_count if plan_week is not None else None
        remaining_month = plan_month - filled_count if plan_month is not None else None
        payload.append(
            {
                "city_id": city_id,
                "city_name": name,
                "tz": tz,
                "plan_week": plan_week,
                "plan_month": plan_month,
                "filled_count": filled_count,
                "remaining_week": remaining_week,
                "remaining_month": remaining_month,
                "entries": [
                    {
                        "id": entry.id,
                        "last_name": entry.last_name,
                        "created_at": entry.created_at.isoformat() if entry.created_at else None,
                    }
                    for entry in entries
                ],
            }
        )
    return payload


async def add_recruiter_plan_entry(recruiter_id: int, city_id: int, last_name: str) -> Dict[str, object]:
    clean = sanitize_plain_text(last_name or "").strip()
    if not clean:
        raise ValueError("last_name is required")

    async with async_session() as session:
        city = await session.scalar(
            select(City)
            .outerjoin(recruiter_city_association, recruiter_city_association.c.city_id == City.id)
            .where(
                City.id == city_id,
                or_(
                    recruiter_city_association.c.recruiter_id == recruiter_id,
                    City.responsible_recruiter_id == recruiter_id,
                ),
            )
        )
        if city is None:
            raise LookupError("city_not_found")

        entry = RecruiterPlanEntry(
            recruiter_id=recruiter_id,
            city_id=city_id,
            last_name=clean,
        )
        session.add(entry)
        await session.commit()
        await session.refresh(entry)

    return {
        "id": entry.id,
        "last_name": entry.last_name,
        "created_at": entry.created_at.isoformat() if entry.created_at else None,
    }


async def delete_recruiter_plan_entry(recruiter_id: int, entry_id: int) -> bool:
    async with async_session() as session:
        entry = await session.scalar(
            select(RecruiterPlanEntry).where(
                RecruiterPlanEntry.id == entry_id,
                RecruiterPlanEntry.recruiter_id == recruiter_id,
            )
        )
        if entry is None:
            return False
        await session.delete(entry)
        await session.commit()
        return True
