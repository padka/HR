from __future__ import annotations

from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.inspection import inspect as sa_inspect

from backend.core.db import async_session
from backend.domain.models import City, Recruiter

from .templates import update_templates_for_city

__all__ = [
    "list_cities",
    "create_city",
    "update_city_settings",
    "get_city",
    "delete_city",
    "city_owner_field_name",
    "api_cities_payload",
    "api_city_owners_payload",
]


async def list_cities(order_by_name: bool = True) -> List[City]:
    async with async_session() as session:
        query = select(City)
        if order_by_name:
            query = query.order_by(City.name.asc())
        return (await session.scalars(query)).all()


async def create_city(name: str, tz: str) -> None:
    """Create a new city ensuring that basic validation is applied."""

    clean_name = (name or "").strip()
    clean_tz = (tz or "").strip()
    if not clean_tz:
        clean_tz = "Europe/Moscow"

    async with async_session() as session:
        session.add(City(name=clean_name, tz=clean_tz))
        await session.commit()


def city_owner_field_name() -> Optional[str]:
    inspector = sa_inspect(City)
    attrs = set(inspector.attrs.keys())
    cols = set(getattr(inspector, "columns", {}).keys()) if hasattr(inspector, "columns") else set()
    allowed = attrs | cols
    for name in ["responsible_recruiter_id", "owner_id", "recruiter_id", "manager_id"]:
        if name in allowed:
            return name
    return None


async def get_city(city_id: int) -> Optional[City]:
    async with async_session() as session:
        return await session.get(City, city_id)


async def update_city_settings(
    city_id: int,
    *,
    name: Optional[str] = None,
    tz: Optional[str] = None,
    active: Optional[bool] = None,
    responsible_id: Optional[int],
    templates: Dict[str, Optional[str]],
    criteria: Optional[str],
    experts: Optional[str],
    plan_week: Optional[int],
    plan_month: Optional[int],
) -> Optional[str]:
    owner_field = city_owner_field_name()
    async with async_session() as session:
        try:
            city = await session.get(City, city_id)
            if not city:
                return "City not found"

            if name is not None:
                clean_name = name.strip()
                if clean_name:
                    city.name = clean_name

            if tz is not None:
                clean_tz = tz.strip()
                if clean_tz:
                    city.tz = clean_tz

            if active is not None:
                city.active = bool(active)

            if responsible_id is not None:
                recruiter = await session.get(Recruiter, responsible_id)
                if not recruiter:
                    return "Recruiter not found"

            if owner_field:
                setattr(city, owner_field, responsible_id)

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
                return error

            await session.commit()
        except Exception:
            await session.rollback()
            raise
    return None


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
    owner_field = city_owner_field_name()
    async with async_session() as session:
        cities = (await session.scalars(select(City).order_by(City.id.asc()))).all()
    return [
        {
            "id": c.id,
            "name": c.name,
            "tz": getattr(c, "tz", None),
            "owner_recruiter_id": getattr(c, owner_field) if owner_field else None,
            "criteria": getattr(c, "criteria", None),
            "experts": getattr(c, "experts", None),
            "plan_week": getattr(c, "plan_week", None),
            "plan_month": getattr(c, "plan_month", None),
        }
        for c in cities
    ]


async def api_city_owners_payload() -> Dict[str, object]:
    owner_field = city_owner_field_name()
    if not owner_field:
        return {"ok": False, "error": "Owner field is missing on City model."}
    async with async_session() as session:
        cities = (await session.scalars(select(City))).all()
    return {
        "ok": True,
        "owners": {c.id: getattr(c, owner_field, None) for c in cities},
    }
