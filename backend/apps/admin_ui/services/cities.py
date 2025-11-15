from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from backend.core.cache import CacheKeys, CacheTTL, get_cache
from backend.core.db import async_session
from backend.core.sanitizers import sanitize_plain_text
from backend.domain.models import City, Recruiter, Slot, SlotStatus
from backend.domain.repositories import city_has_available_slots

from .templates import update_templates_for_city

__all__ = [
    "list_cities",
    "create_city",
    "update_city_settings",
    "delete_city",
    "api_cities_payload",
    "api_city_owners_payload",
    "normalize_city_timezone",
    "get_city_capacity",
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
    tz: Optional[str] = None,
    active: Optional[bool] = None,
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

            if tz is not None:
                try:
                    city.tz = normalize_city_timezone(tz)
                except ValueError as exc:
                    await session.rollback()
                    return str(exc), None, None
            if active is not None:
                city.active = bool(active)

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


async def get_city_capacity(city_id: int) -> Optional[Dict[str, object]]:
    """Get capacity information for a city including slot availability.

    Returns a dictionary with:
    - has_available_slots: boolean indicating if there are any free slots
    - total_free_slots: count of available slots
    - city: basic city info (id, name, tz)

    Returns None if city is not found.
    Cached for 5 minutes (CacheTTL.SHORT).
    """
    # Try to get from cache first
    try:
        cache = get_cache()
        cache_key = CacheKeys.city_capacity(city_id)
        result = await cache.get(cache_key)
        if result.is_success and result.unwrap() is not None:
            return result.unwrap()
    except RuntimeError:
        # Cache not initialized (e.g., in tests), skip caching
        pass

    async with async_session() as session:
        city = await session.get(City, city_id)
        if not city:
            return None

        # Check if city has available slots
        has_slots = await city_has_available_slots(city_id)

        # Count total free slots
        now_utc = datetime.now(timezone.utc)
        total_free = await session.scalar(
            select(func.count())
            .select_from(Slot)
            .where(
                Slot.city_id == city_id,
                func.lower(Slot.status) == SlotStatus.FREE,
                Slot.start_utc > now_utc,
            )
        )

        capacity_data = {
            "has_available_slots": has_slots,
            "total_free_slots": total_free or 0,
            "city": {
                "id": city.id,
                "name": city.name_plain,
                "tz": getattr(city, "tz", None),
                "active": getattr(city, "active", None),
            },
        }

        # Cache the result for 5 minutes
        try:
            cache = get_cache()
            cache_key = CacheKeys.city_capacity(city_id)
            await cache.set(cache_key, capacity_data, ttl=CacheTTL.SHORT)
        except RuntimeError:
            # Cache not initialized, skip caching
            pass

        return capacity_data
