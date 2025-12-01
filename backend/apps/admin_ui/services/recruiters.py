from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional, Sequence, Tuple
from urllib.parse import urlparse
import html

from sqlalchemy import case, func, select, delete, insert
from sqlalchemy.inspection import inspect as sa_inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from backend.apps.admin_ui.utils import format_optional_local
from backend.core.db import async_session
from backend.domain.models import City, Recruiter, Slot, SlotStatus, recruiter_city_association
from backend.core.sanitizers import sanitize_plain_text
from markupsafe import Markup

__all__ = [
    "list_recruiters",
    "create_recruiter",
    "get_recruiter_detail",
    "update_recruiter",
    "delete_recruiter",
    "build_recruiter_payload",
    "api_recruiters_payload",
    "api_get_recruiter",
    "RecruiterValidationError",
]


async def list_recruiters(order_by_name: bool = True) -> List[Dict[str, object]]:
    async with async_session() as session:
        query = select(Recruiter).options(selectinload(Recruiter.cities))
        if order_by_name:
            query = query.order_by(Recruiter.name.asc())
        recs = list((await session.scalars(query)).all())

        stats_map: Dict[int, Dict[str, object]] = {}

        if recs:
            rec_ids = [r.id for r in recs]
            status_lower = func.lower(Slot.status)
            stats_rows = (
                await session.execute(
                    select(
                        Slot.recruiter_id,
                        func.count().label("total"),
                        func.sum(case((status_lower == SlotStatus.FREE, 1), else_=0)).label("free"),
                        func.sum(case((status_lower == SlotStatus.PENDING, 1), else_=0)).label("pending"),
                        func.sum(
                            case(
                                (
                                    status_lower.in_(
                                        [SlotStatus.BOOKED, SlotStatus.CONFIRMED_BY_CANDIDATE]
                                    ),
                                    1,
                                ),
                                else_=0,
                            )
                        ).label("booked"),
                        func.min(case((status_lower == SlotStatus.FREE, Slot.start_utc), else_=None)).label(
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

        sorted_cities = sorted(
            rec.cities,
            key=lambda city: (getattr(city, "name_plain", "") or "").lower(),
        )
        cities_entries: List[Tuple[Markup, str]] = []
        for city in sorted_cities:
            name_markup: Markup
            if hasattr(city, "display_name"):
                name_markup = city.display_name
            else:
                name_markup = Markup(sanitize_plain_text(getattr(city, "name", "") or ""))
            cities_entries.append((name_markup, getattr(city, "tz", "")))
        out.append(
            {
                "rec": rec,
                "stats": stats,
                "next_free_local": next_local,
                "next_is_future": next_future,
                "cities": cities_entries,
                "city_ids": [city.id for city in sorted_cities],
                "cities_text": " ".join(
                    (getattr(city, "name_plain", "") or "").lower() for city in sorted_cities
                ),
                "cities_display": ", ".join(
                    sanitize_plain_text(city.name_plain)
                    for city in sorted_cities
                    if getattr(city, "name_plain", None)
                ),
            }
        )

    return out


async def create_recruiter(
    payload: Dict[str, object], *, cities: Optional[List[str]] = None
) -> Dict[str, object]:
    async with async_session() as session:
        try:
            selected_ids = _parse_city_ids(cities)
            recruiter = Recruiter(**payload)
            session.add(recruiter)

            # Flush to get recruiter.id
            await session.flush()

            if selected_ids:
                # Clear any existing associations (defensive)
                await session.execute(
                    delete(recruiter_city_association).where(
                        recruiter_city_association.c.recruiter_id == recruiter.id
                    )
                )
                # Directly insert into association table
                await session.execute(
                    insert(recruiter_city_association),
                    [{"recruiter_id": recruiter.id, "city_id": city_id} for city_id in selected_ids]
                )

            await session.commit()
            # Refresh with relationship loaded
            await session.refresh(recruiter, ["cities"])
        except IntegrityError as exc:  # pragma: no cover - defensive, regression covered by tests
            await session.rollback()
            return {"ok": False, "error": _integrity_error_payload(exc)}

    return {"ok": True, "recruiter_id": recruiter.id}


async def get_recruiter_detail(rec_id: int) -> Optional[Dict[str, object]]:
    async with async_session() as session:
        recruiter_result = await session.execute(
            select(Recruiter)
            .options(selectinload(Recruiter.cities))
            .where(Recruiter.id == rec_id)
        )
        recruiter = recruiter_result.scalar_one_or_none()
        if not recruiter:
            return None
        cities = (await session.scalars(select(City).order_by(City.name.asc()))).all()
        selected_ids = {city.id for city in recruiter.cities}
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
) -> Dict[str, object]:
    async with async_session() as session:
        recruiter_result = await session.execute(
            select(Recruiter)
            .options(selectinload(Recruiter.cities))
            .where(Recruiter.id == rec_id)
        )
        recruiter = recruiter_result.scalar_one_or_none()
        if not recruiter:
            return {
                "ok": False,
                "error": {"type": "not_found", "message": "Рекрутёр не найден."},
            }

        try:
            for key, value in payload.items():
                setattr(recruiter, key, value)

            selected_ids = _parse_city_ids(cities)

            # Clear all existing associations for this recruiter
            await session.execute(
                delete(recruiter_city_association).where(
                    recruiter_city_association.c.recruiter_id == rec_id
                )
            )

            # Insert new associations
            if selected_ids:
                await session.execute(
                    insert(recruiter_city_association),
                    [{"recruiter_id": rec_id, "city_id": city_id} for city_id in selected_ids]
                )

            await session.commit()
            # Refresh to get updated relationships
            await session.refresh(recruiter, ["cities"])
        except IntegrityError as exc:  # pragma: no cover - defensive, regression covered by tests
            await session.rollback()
            return {"ok": False, "error": _integrity_error_payload(exc)}

    return {"ok": True, "recruiter_id": rec_id}


async def delete_recruiter(rec_id: int) -> None:
    async with async_session() as session:
        recruiter = await session.get(Recruiter, rec_id)
        if not recruiter:
            return
        await session.execute(
            delete(recruiter_city_association).where(
                recruiter_city_association.c.recruiter_id == rec_id
            )
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

    telemost_field = _pick_field(
        allowed,
        ["telemost_url", "telemost", "meet_link", "meet_url", "video_link", "video_url", "link", "room_url"],
    )
    if telemost_field:
        link_raw = (telemost or "").strip()
        if link_raw:
            if not _is_valid_url(link_raw):
                raise RecruiterValidationError("telemost", "Ссылка: укажите корректный URL")
            payload[telemost_field] = link_raw
        else:
            payload[telemost_field] = None

    chat_field = _pick_field(allowed, ["tg_chat_id", "telegram_chat_id", "chat_id"])
    if chat_field:
        raw_chat = (tg_chat_id or "").strip()
        if raw_chat:
            if not raw_chat.isdigit():
                raise RecruiterValidationError("tg_chat_id", "chat_id: только цифры")
            payload[chat_field] = int(raw_chat)
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


def _integrity_error_payload(exc: IntegrityError) -> Dict[str, object]:
    message = "Не удалось сохранить рекрутёра: проверьте корректность данных."
    field: Optional[str] = None
    detail = str(getattr(exc, "orig", exc)).lower()
    if "tg_chat_id" in detail or "telegram" in detail:
        message = "Рекрутёр с таким Telegram chat ID уже существует."
        field = "tg_chat_id"

    payload: Dict[str, object] = {"type": "integrity_error", "message": message}
    if field:
        payload["field"] = field
    return payload


def _parse_city_ids(raw: Optional[List[str]]) -> List[int]:
    if not raw:
        return []
    seen: set[int] = set()
    result: List[int] = []
    for value in raw:
        if not isinstance(value, str):
            continue
        trimmed = value.strip()
        if not trimmed or not trimmed.isdigit():
            continue
        city_id = int(trimmed)
        if city_id in seen:
            continue
        seen.add(city_id)
        result.append(city_id)
    return result


async def api_recruiters_payload() -> List[Dict[str, object]]:
    async with async_session() as session:
        recs = (
            await session.scalars(
                select(Recruiter)
                .options(selectinload(Recruiter.cities))
                .order_by(Recruiter.id.asc())
            )
        ).all()
    return [
        {
            "id": r.id,
            "name": r.name,
            "tz": getattr(r, "tz", None),
            "tg_chat_id": getattr(r, "tg_chat_id", None),
            "active": getattr(r, "active", True),
            "city_ids": sorted(city.id for city in r.cities),
        }
        for r in recs
    ]


async def api_get_recruiter(recruiter_id: int) -> Optional[Dict[str, object]]:
    async with async_session() as session:
        recruiter = await session.scalar(
            select(Recruiter)
            .options(selectinload(Recruiter.cities))
            .where(Recruiter.id == recruiter_id)
        )
    if recruiter is None:
        return None
    return {
        "id": recruiter.id,
        "name": recruiter.name,
        "tz": getattr(recruiter, "tz", None),
        "tg_chat_id": getattr(recruiter, "tg_chat_id", None),
        "active": getattr(recruiter, "active", True),
        "city_ids": sorted(city.id for city in recruiter.cities),
    }


class RecruiterValidationError(ValueError):
    def __init__(self, field: str, message: str) -> None:
        super().__init__(message)
        self.field = field


def _is_valid_url(value: str) -> bool:
    try:
        parsed = urlparse(value)
    except ValueError:
        return False
    scheme = (parsed.scheme or "").lower()
    if scheme not in {"http", "https"}:
        return False
    if not parsed.netloc:
        return False
    return True
