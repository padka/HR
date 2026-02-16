from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from backend.core.cache import CacheKeys, CacheTTL, get_cache
from backend.core.db import async_session
from backend.core.sanitizers import sanitize_plain_text
from backend.domain.cities.models import CityExpert
from backend.domain.models import City, Recruiter, Slot, SlotStatus
from backend.domain.repositories import city_has_available_slots, slot_status_free_clause
from backend.domain.errors import CityAlreadyExistsError
from backend.apps.admin_ui.security import principal_ctx, Principal


__all__ = [
    "list_cities",
    "get_city",
    "create_city",
    "update_city_settings",
    "update_city_owner",
    "set_city_active",
    "delete_city",
    "api_cities_payload",
    "api_city_owners_payload",
    "normalize_city_timezone",
    "get_city_capacity",
    "city_experts_items",
]

_EXPERT_SPLIT_RE = re.compile(r"[\n,;]+")


def _clean_expert_name(value: str) -> str:
    # Normalise whitespace while keeping original characters.
    return " ".join((value or "").strip().split())


def parse_experts_text(value: Optional[str]) -> List[str]:
    text = (value or "").strip()
    if not text:
        return []
    parts = _EXPERT_SPLIT_RE.split(text)
    names: List[str] = []
    seen: set[str] = set()
    for part in parts:
        name = _clean_expert_name(part)
        if not name:
            continue
        key = name.casefold()
        if key in seen:
            continue
        seen.add(key)
        names.append(name)
    return names


def city_experts_items(city: City, *, include_inactive: bool = False) -> List[Dict[str, object]]:
    experts = list(getattr(city, "city_experts", []) or [])
    if experts:
        payload: List[Dict[str, object]] = []
        for expert in experts:
            if not include_inactive and not getattr(expert, "is_active", True):
                continue
            payload.append(
                {
                    "id": expert.id,
                    "name": expert.name,
                    "is_active": bool(getattr(expert, "is_active", True)),
                }
            )
        payload.sort(key=lambda row: int(row.get("id") or 0))
        return payload

    # Backward-compat: legacy string field used in older UIs and historical data.
    legacy = parse_experts_text(getattr(city, "experts", None))
    return [{"id": None, "name": name, "is_active": True} for name in legacy]


def _sync_city_experts_from_items(city: City, items: object) -> List[str]:
    if not isinstance(items, list):
        items = []

    existing = list(getattr(city, "city_experts", []) or [])
    by_id = {exp.id: exp for exp in existing if getattr(exp, "id", None) is not None}
    by_name = {str(exp.name).casefold(): exp for exp in existing if getattr(exp, "name", None)}

    keep_ids: set[int] = set()
    keep_name_keys: set[str] = set()

    for raw in items:
        if not isinstance(raw, dict):
            continue
        raw_name = raw.get("name")
        name = _clean_expert_name(str(raw_name or ""))
        if not name:
            continue

        key = name.casefold()
        if key in keep_name_keys:
            continue
        keep_name_keys.add(key)

        raw_id = raw.get("id")
        exp_id: Optional[int] = None
        if raw_id not in (None, "", "null"):
            try:
                exp_id = int(raw_id)
            except (TypeError, ValueError):
                exp_id = None

        is_active = raw.get("is_active")
        active = True if is_active is None else bool(is_active)

        expert: Optional[CityExpert] = None
        if exp_id is not None and exp_id in by_id:
            expert = by_id[exp_id]
        elif key in by_name:
            expert = by_name[key]

        if expert is None:
            expert = CityExpert(name=name, is_active=active, city_id=city.id)
            existing.append(expert)
        else:
            expert.name = name
            expert.is_active = active

        if getattr(expert, "id", None) is not None:
            keep_ids.add(int(expert.id))

    for expert in existing:
        if getattr(expert, "id", None) is None:
            continue
        if int(expert.id) not in keep_ids:
            # Keep history; missing from payload => archived.
            expert.is_active = False

    # Reattach updated list; relationship is configured with delete-orphan.
    city.city_experts = existing

    active_names = [exp.name for exp in existing if getattr(exp, "is_active", True) and getattr(exp, "name", None)]
    return active_names


def _sync_city_experts_from_text(city: City, value: Optional[str]) -> List[str]:
    desired = [{"id": None, "name": name, "is_active": True} for name in parse_experts_text(value)]
    return _sync_city_experts_from_items(city, desired)


async def list_cities(order_by_name: bool = True, principal: Optional[Principal] = None) -> List[City]:
    principal = principal or principal_ctx.get()
    if principal is None:
        raise RuntimeError("principal is required for list_cities")
    async with async_session() as session:
        query = select(City).options(selectinload(City.recruiters), selectinload(City.city_experts))
        if principal and principal.type == "recruiter":
            query = query.join(City.recruiters).where(Recruiter.id == principal.id)
        if order_by_name:
            query = query.order_by(City.name.asc())
        cities = (await session.scalars(query)).all()
        changed = False
        for city in cities:
            if city.recruiters:
                primary = city.recruiters[0]
                if city.responsible_recruiter_id != primary.id:
                    city.responsible_recruiter_id = primary.id
                    changed = True
            elif city.responsible_recruiter_id:
                recruiter = await session.get(Recruiter, city.responsible_recruiter_id)
                if recruiter:
                    city.recruiters = [recruiter]
                    changed = True
        if changed:
            await session.commit()
        return cities


async def get_city(city_id: int, principal: Optional[Principal] = None) -> Optional[City]:
    principal = principal or principal_ctx.get()
    if principal is None:
        raise RuntimeError("principal is required for get_city")
    async with async_session() as session:
        query = (
            select(City)
            .options(selectinload(City.recruiters), selectinload(City.city_experts))
            .where(City.id == city_id)
        )
        if principal and principal.type == "recruiter":
            query = query.join(City.recruiters).where(Recruiter.id == principal.id)
        result = await session.execute(query)
        city = result.scalar_one_or_none()
        if not city:
            return None
        if city.recruiters:
            primary = city.recruiters[0]
            if city.responsible_recruiter_id != primary.id:
                city.responsible_recruiter_id = primary.id
                await session.commit()
        elif city.responsible_recruiter_id:
            recruiter = await session.get(Recruiter, city.responsible_recruiter_id)
            if recruiter:
                city.recruiters = [recruiter]
                await session.commit()
        return city


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


async def create_city(
    name: str,
    tz: str,
    *,
    recruiter_ids: Optional[List[int]] = None,
) -> Optional[City]:
    """Create a new city ensuring that basic validation is applied."""

    clean_name = sanitize_plain_text(name)
    if not clean_name:
        raise ValueError("Название города не может быть пустым")
    clean_tz = normalize_city_timezone(tz)

    async with async_session() as session:
        city = City(name=clean_name, tz=clean_tz)
        session.add(city)
        try:
            await session.flush()
            if recruiter_ids:
                recruiters_list = list(
                    await session.scalars(select(Recruiter).where(Recruiter.id.in_(recruiter_ids)))
                )
                if recruiters_list:
                    await session.refresh(city, attribute_names=["recruiters"])
                    city.recruiters = recruiters_list
                    city.responsible_recruiter = recruiters_list[0]
            await session.commit()
            await session.refresh(city)
            return city
        except IntegrityError as exc:
            await session.rollback()
            raise CityAlreadyExistsError(clean_name) from exc


async def update_city_settings(
    city_id: int,
    *,
    name: Optional[str],
    recruiter_ids: Optional[List[int]] = None,
    responsible_id: Optional[int] = None,
    criteria: Optional[str],
    experts: Optional[str],
    experts_items: Optional[object] = None,
    plan_week: Optional[int],
    plan_month: Optional[int],
    tz: Optional[str] = None,
    active: Optional[bool] = None,
    intro_address: Optional[str] = None,
    contact_name: Optional[str] = None,
    contact_phone: Optional[str] = None,
) -> Tuple[Optional[str], Optional[City], Optional[Recruiter]]:
    async with async_session() as session:
        try:
            city_result = await session.execute(
                select(City)
                .options(selectinload(City.recruiters), selectinload(City.city_experts))
                .where(City.id == city_id)
            )
            city = city_result.scalar_one_or_none()
            if not city:
                return "City not found", None, None

            assigned_recruiter: Optional[Recruiter] = None

            # Support both responsible_id (single, backward compat) and recruiter_ids (list)
            effective_ids: List[int] = []
            if responsible_id is not None:
                effective_ids = [responsible_id]
            elif recruiter_ids is not None:
                effective_ids = recruiter_ids

            if effective_ids:
                recruiters_list = list(
                    await session.scalars(select(Recruiter).where(Recruiter.id.in_(effective_ids)))
                )
                if not recruiters_list:
                    return "Recruiter not found", None, None
                city.recruiters = recruiters_list
                assigned_recruiter = recruiters_list[0]  # Primary recruiter
                city.responsible_recruiter = assigned_recruiter
            else:
                city.recruiters = []
                city.responsible_recruiter_id = None

            clean_criteria = (criteria or "").strip() or None
            clean_experts = (experts or "").strip() or None
            city.criteria = clean_criteria
            # Experts: sync structured city_experts and keep legacy text field in sync.
            if experts_items is not None:
                active_names = _sync_city_experts_from_items(city, experts_items)
            else:
                active_names = _sync_city_experts_from_text(city, clean_experts)
            city.experts = "\n".join(active_names) if active_names else None
            city.intro_address = (intro_address or "").strip() or None
            city.contact_name = (contact_name or "").strip() or None
            city.contact_phone = (contact_phone or "").strip() or None

            normalized_week = plan_week if plan_week is None or plan_week >= 0 else None
            normalized_month = plan_month if plan_month is None or plan_month >= 0 else None
            city.plan_week = normalized_week
            city.plan_month = normalized_month

            if name is not None:
                clean_name = sanitize_plain_text(name)
                if not clean_name:
                    await session.rollback()
                    return "Название города не может быть пустым", None, None
                city.name = clean_name

            if tz is not None:
                try:
                    city.tz = normalize_city_timezone(tz)
                except ValueError as exc:
                    await session.rollback()
                    return str(exc), None, None
            if active is not None:
                city.active = bool(active)

            try:
                await session.commit()
            except IntegrityError as exc:
                await session.rollback()
                detail = str(getattr(exc, "orig", exc)).lower()
                if "uq_city_name" in detail or "unique" in detail:
                    return "Город с таким названием уже существует", None, None
                raise
            await session.refresh(city)
        except Exception:
            await session.rollback()
            raise
    return None, city, assigned_recruiter


async def update_city_owner(
    city_id: int, responsible_id: Optional[int]
) -> Tuple[Optional[str], Optional[City], Optional[Recruiter]]:
    async with async_session() as session:
        try:
            city = await session.get(City, city_id)
            if not city:
                return "City not found", None, None
            recruiter_obj: Optional[Recruiter] = None
            if responsible_id is not None:
                recruiter_obj = await session.get(Recruiter, responsible_id)
                if not recruiter_obj:
                    return "Recruiter not found", None, None
                city.recruiters = [recruiter_obj]
                city.responsible_recruiter = recruiter_obj
            else:
                city.recruiters = []
                city.responsible_recruiter_id = None
            await session.commit()
            await session.refresh(city)
        except Exception:
            await session.rollback()
            raise
    return None, city, recruiter_obj


async def set_city_active(city_id: int, active: bool) -> Tuple[Optional[str], Optional[City]]:
    async with async_session() as session:
        try:
            city = await session.get(City, city_id)
            if not city:
                return "City not found", None
            city.active = bool(active)
            await session.commit()
            await session.refresh(city)
        except Exception:
            await session.rollback()
            raise
    return None, city


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
        recruiters_payload = [
            {"id": recruiter.id, "name": recruiter.name}
            for recruiter in (city.recruiters or [])
            if recruiter is not None
        ]
        payload.append(
            {
                "id": city.id,
                "name": city.name_plain,
                "name_plain": city.name_plain,
                "display_name": str(city.display_name),
                "name_html": sanitize_plain_text(city.name_plain),
                "tz": getattr(city, "tz", None),
                "owner_recruiter_id": primary.id if primary else None,
                "active": getattr(city, "active", True),
                "criteria": getattr(city, "criteria", None),
                "experts": getattr(city, "experts", None),
                "plan_week": getattr(city, "plan_week", None),
                "plan_month": getattr(city, "plan_month", None),
                "recruiters": recruiters_payload,
                "recruiter_count": len(recruiters_payload),
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
                slot_status_free_clause(Slot),
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
