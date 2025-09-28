from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional, Sequence, Tuple

from sqlalchemy import case, func, select, update
from sqlalchemy.inspection import inspect as sa_inspect

from backend.apps.admin_ui.utils import format_optional_local
from backend.core.db import async_session
from backend.domain.models import City, Recruiter, Slot, SlotStatus

__all__ = [
    "list_recruiters",
    "create_recruiter",
    "get_recruiter_detail",
    "update_recruiter",
    "delete_recruiter",
    "build_recruiter_payload",
    "api_recruiters_payload",
]


async def list_recruiters(order_by_name: bool = True) -> List[Dict[str, object]]:
    async with async_session() as session:
        query = select(Recruiter)
        if order_by_name:
            query = query.order_by(Recruiter.name.asc())
        recs = list((await session.scalars(query)).all())

        stats_map: Dict[int, Dict[str, object]] = {}
        city_map: Dict[int, List[Tuple[str, str]]] = {}

        if recs:
            rec_ids = [r.id for r in recs]
            stats_rows = (
                await session.execute(
                    select(
                        Slot.recruiter_id,
                        func.count().label("total"),
                        func.sum(case((Slot.status == SlotStatus.FREE, 1), else_=0)).label("free"),
                        func.sum(case((Slot.status == SlotStatus.PENDING, 1), else_=0)).label("pending"),
                        func.sum(case((Slot.status == SlotStatus.BOOKED, 1), else_=0)).label("booked"),
                        func.min(case((Slot.status == SlotStatus.FREE, Slot.start_utc), else_=None)).label(
                            "next_free"
                        ),
                    )
                    .where(Slot.recruiter_id.in_(rec_ids))
                    .group_by(Slot.recruiter_id)
                )
            ).all()

            stats_map = {
                row.recruiter_id: {
                    "total": int(row.total or 0),
                    "free": int(row.free or 0),
                    "pending": int(row.pending or 0),
                    "booked": int(row.booked or 0),
                    "next_free": row.next_free,
                }
                for row in stats_rows
            }

            city_rows = (
                await session.execute(
                    select(City.id, City.name, City.tz, City.responsible_recruiter_id)
                    .where(City.responsible_recruiter_id.in_(rec_ids))
                    .order_by(City.name.asc())
                )
            ).all()

            for row in city_rows:
                city_map.setdefault(row.responsible_recruiter_id, []).append((row.name, row.tz))

    now = datetime.now(timezone.utc)
    out = []
    for rec in recs:
        stats = stats_map.get(
            rec.id,
            {"total": 0, "free": 0, "pending": 0, "booked": 0, "next_free": None},
        )
        next_dt = stats.get("next_free")
        if isinstance(next_dt, datetime) and next_dt.tzinfo is None:
            next_dt = next_dt.replace(tzinfo=timezone.utc)
        if isinstance(next_dt, datetime):
            stats["next_free"] = next_dt
            next_local = format_optional_local(next_dt, getattr(rec, "tz", None))
            next_future = next_dt > now
        else:
            next_local = None
            next_future = False

        out.append(
            {
                "rec": rec,
                "stats": stats,
                "next_free_local": next_local,
                "next_is_future": next_future,
                "cities": city_map.get(rec.id, []),
                "cities_text": " ".join(name.lower() for name, _ in city_map.get(rec.id, [])),
            }
        )

    return out


async def create_recruiter(payload: Dict[str, object], *, cities: Optional[List[str]] = None) -> None:
    async with async_session() as session:
        recruiter = Recruiter(**payload)
        session.add(recruiter)
        await session.commit()
        await session.refresh(recruiter)

        selected: List[int] = []
        if cities:
            for cid in cities:
                if cid and cid.strip().isdigit():
                    selected.append(int(cid.strip()))
        if selected:
            await session.execute(
                update(City)
                .where(City.id.in_(selected))
                .values(responsible_recruiter_id=recruiter.id)
            )
            await session.commit()


async def get_recruiter_detail(rec_id: int) -> Optional[Dict[str, object]]:
    async with async_session() as session:
        recruiter = await session.get(Recruiter, rec_id)
        if not recruiter:
            return None
        cities = (await session.scalars(select(City).order_by(City.name.asc()))).all()
        selected_ids = {c.id for c in cities if c.responsible_recruiter_id == rec_id}
    return {
        "recruiter": recruiter,
        "cities": cities,
        "selected_ids": selected_ids,
    }


async def update_recruiter(
    rec_id: int,
    payload: Dict[str, object],
    *,
    cities: Optional[List[str]] = None,
) -> bool:
    async with async_session() as session:
        recruiter = await session.get(Recruiter, rec_id)
        if not recruiter:
            return False

        for key, value in payload.items():
            setattr(recruiter, key, value)

        selected: List[int] = []
        if cities:
            for cid in cities:
                if cid and cid.strip().isdigit():
                    selected.append(int(cid.strip()))

        await session.execute(
            update(City)
            .where(City.responsible_recruiter_id == rec_id)
            .values(responsible_recruiter_id=None)
        )
        if selected:
            await session.execute(
                update(City)
                .where(City.id.in_(selected))
                .values(responsible_recruiter_id=rec_id)
            )

        await session.commit()

    return True


async def delete_recruiter(rec_id: int) -> None:
    async with async_session() as session:
        recruiter = await session.get(Recruiter, rec_id)
        if not recruiter:
            return
        await session.execute(
            update(City)
            .where(City.responsible_recruiter_id == rec_id)
            .values(responsible_recruiter_id=None)
        )
        await session.delete(recruiter)
        await session.commit()


def build_recruiter_payload(
    *,
    name: str,
    tz: str,
    telemost: Optional[str],
    tg_chat_id: Optional[str],
    active: Optional[str],
) -> Dict[str, object]:
    allowed = set(sa_inspect(Recruiter).attrs.keys())
    payload: Dict[str, object] = {"name": name.strip()}

    tz_field = _pick_field(allowed, ["tz", "timezone", "tz_name", "time_zone"])
    if tz_field:
        payload[tz_field] = tz.strip() if tz else "Europe/Moscow"

    link = (telemost or "").strip() or None
    telemost_field = _pick_field(
        allowed,
        ["telemost_url", "telemost", "meet_link", "meet_url", "video_link", "video_url", "link", "room_url"],
    )
    if telemost_field:
        payload[telemost_field] = link

    chat_field = _pick_field(allowed, ["tg_chat_id", "telegram_chat_id", "chat_id"])
    if chat_field:
        if tg_chat_id and tg_chat_id.strip().isdigit():
            payload[chat_field] = int(tg_chat_id.strip())
        else:
            payload[chat_field] = None

    active_field = _pick_field(allowed, ["active", "is_active", "enabled"])
    if active_field:
        payload[active_field] = True if active else False

    return payload


def _pick_field(allowed: Sequence[str], candidates: Sequence[str]) -> Optional[str]:
    for name in candidates:
        if name in allowed:
            return name
    return None


async def api_recruiters_payload() -> List[Dict[str, object]]:
    async with async_session() as session:
        recs = (await session.scalars(select(Recruiter).order_by(Recruiter.id.asc()))).all()
    return [
        {
            "id": r.id,
            "name": r.name,
            "tz": getattr(r, "tz", None),
            "tg_chat_id": getattr(r, "tg_chat_id", None),
            "active": getattr(r, "active", True),
        }
        for r in recs
    ]
