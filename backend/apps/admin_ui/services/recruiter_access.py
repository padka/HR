from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.db import async_session
from backend.domain.candidates.models import User
from backend.domain.models import City, recruiter_city_association
from backend.domain.repositories import resolve_city_id_and_tz_by_plain_name


async def _recruiter_can_access_city(
    session: AsyncSession,
    *,
    recruiter_id: int,
    city_id: int,
) -> bool:
    linked_city = await session.scalar(
        select(recruiter_city_association.c.city_id).where(
            recruiter_city_association.c.recruiter_id == recruiter_id,
            recruiter_city_association.c.city_id == city_id,
        ).limit(1)
    )
    if linked_city is not None:
        return True

    city = await session.get(City, city_id)
    return bool(city and city.responsible_recruiter_id == recruiter_id)


async def recruiter_can_access_candidate(
    recruiter: Any,
    candidate: User,
    *,
    session: AsyncSession | None = None,
) -> bool:
    if recruiter is None or candidate is None:
        return False

    if getattr(recruiter, "is_admin", False) is True:
        return True

    recruiter_id = getattr(recruiter, "id", None)
    if recruiter_id is None:
        return False

    owner_id = getattr(candidate, "responsible_recruiter_id", None)
    if owner_id == recruiter_id:
        return True
    if owner_id is not None:
        return False

    city_name = (getattr(candidate, "city", None) or "").strip()
    if not city_name:
        return False

    city_id, _ = await resolve_city_id_and_tz_by_plain_name(city_name)
    if city_id is None:
        return False

    if session is not None:
        return await _recruiter_can_access_city(session, recruiter_id=recruiter_id, city_id=city_id)

    async with async_session() as own_session:
        return await _recruiter_can_access_city(
            own_session,
            recruiter_id=recruiter_id,
            city_id=city_id,
        )


async def get_candidate_for_recruiter(
    candidate_id: int,
    recruiter: Any,
    *,
    session: AsyncSession | None = None,
    detach: bool = False,
) -> User | None:
    async def _load(active_session: AsyncSession) -> User | None:
        result = await active_session.execute(select(User).where(User.id == candidate_id))
        candidate = result.scalar_one_or_none()
        if candidate is None:
            return None
        allowed = await recruiter_can_access_candidate(recruiter, candidate, session=active_session)
        if not allowed:
            return None
        if detach:
            active_session.expunge(candidate)
        return candidate

    if session is not None:
        return await _load(session)

    async with async_session() as own_session:
        return await _load(own_session)

