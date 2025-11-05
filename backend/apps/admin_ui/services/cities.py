from __future__ import annotations

from typing import Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend.core.db import async_session
from backend.core.sanitizers import sanitize_plain_text
from backend.domain.models import City, Recruiter

from .templates import update_templates_for_city

__all__ = [
    "list_cities",
    "create_city",
    "update_city_settings",
    "delete_city",
    "api_cities_payload",
    "api_city_owners_payload",
    "normalize_city_timezone",
]


async def list_cities(order_by_name: bool = True) -> List[City]:
    async with async_session() as session:
        query = select(City).options(selectinload(City.recruiters))
        if order_by_name:
            query = query.order_by(City.name.asc())
        return (await session.scalars(query)).all()


def normalize_city_timezone(value: Optional[str]) -> str:
    tz_candidate = (value or "").strip()
    if not tz_candidate:
        return "Europe/Moscow"
    try:
        ZoneInfo(tz_candidate)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(
            "Укажите корректный идентификатор часового пояса (например, Europe/Moscow)"
        ) from exc
    return tz_candidate


async def create_city(name: str, tz: str) -> None:
    """Create a new city ensuring that basic validation is applied."""

    clean_name = sanitize_plain_text(name)
    if not clean_name:
        raise ValueError("Название города не может быть пустым")
    clean_tz = normalize_city_timezone(tz)

    async with async_session() as session:
        session.add(City(name=clean_name, tz=clean_tz))
        await session.commit()


async def update_city_settings(
    city_id: int,
    *,
    responsible_id: Optional[int],
    templates: Dict[str, Optional[str]],
    criteria: Optional[str],
    experts: Optional[str],
    plan_week: Optional[int],
    plan_month: Optional[int],
) -> Tuple[Optional[str], Optional[City], Optional[Recruiter]]:
    async with async_session() as session:
        try:
            city_result = await session.execute(
                select(City)
                .options(selectinload(City.recruiters))
                .where(City.id == city_id)
            )
            city = city_result.scalar_one_or_none()
            if not city:
                return "City not found", None, None

            assigned_recruiter: Optional[Recruiter] = None
            if responsible_id is not None:
                recruiter = await session.get(Recruiter, responsible_id)
                if not recruiter:
                    return "Recruiter not found", None, None
                assigned_recruiter = recruiter
                city.recruiters = [recruiter]
            else:
                city.recruiters = []

            clean_criteria = (criteria or "").strip() or None
            clean_experts = (experts or "").strip() or None
            city.criteria = clean_criteria
            city.experts = clean_experts

            normalized_week = plan_week if plan_week is None or plan_week >= 0 else None
            normalized_month = plan_month if plan_month is None or plan_month >= 0 else None
            city.plan_week = normalized_week
            city.plan_month = normalized_month

            error = await update_templates_for_city(city_id, templates, session=session)
            if error:
                await session.rollback()
                return error, None, None

            await session.commit()
            await session.refresh(city)
        except Exception:
            await session.rollback()
            raise
    return None, city, assigned_recruiter


async def delete_city(city_id: int) -> bool:
    async with async_session() as session:
        try:
            city = await session.get(City, city_id)
            if not city:
                return False
            await session.delete(city)
            await session.commit()
        except Exception:
            await session.rollback()
            raise
    return True


async def api_cities_payload() -> List[Dict[str, object]]:
    async with async_session() as session:
        cities = (
            await session.scalars(
                select(City)
                .options(selectinload(City.recruiters))
                .order_by(City.id.asc())
            )
        ).all()
    payload: List[Dict[str, object]] = []
    for city in cities:
        primary = _primary_recruiter(city)
        payload.append(
            {
                "id": city.id,
                "name": city.name_plain,
                "name_plain": city.name_plain,
                "display_name": str(city.display_name),
                "name_html": sanitize_plain_text(city.name_plain),
                "tz": getattr(city, "tz", None),
                "owner_recruiter_id": primary.id if primary else None,
                "criteria": getattr(city, "criteria", None),
                "experts": getattr(city, "experts", None),
                "plan_week": getattr(city, "plan_week", None),
                "plan_month": getattr(city, "plan_month", None),
            }
        )
    return payload


async def api_city_owners_payload() -> Dict[str, object]:
    async with async_session() as session:
        cities = (
            await session.scalars(
                select(City).options(selectinload(City.recruiters))
            )
        ).all()
    return {
        "ok": True,
        "owners": {
            city.id: (_primary_recruiter(city).id if _primary_recruiter(city) else None)
            for city in cities
        },
    }


def _primary_recruiter(city: City) -> Optional[Recruiter]:
    if not getattr(city, "recruiters", None):
        return None
    for recruiter in city.recruiters:
        if recruiter is not None:
            return recruiter
    return None
