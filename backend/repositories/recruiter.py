"""Recruiter repository implementation with caching support."""

from __future__ import annotations

from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.core.repository.base import BaseRepository
from backend.core.result import DatabaseError, NotFoundError, Result, failure, success
from backend.core.cache import CacheKeys, CacheTTL
from backend.core.cache_decorators import cached, invalidate_cache
from backend.domain.models import Recruiter


class RecruiterRepository(BaseRepository[Recruiter]):
    """
    Repository for Recruiter entities with caching support.

    Caching strategy:
    - Individual recruiters: LONG TTL (stable data)
    - Active recruiters list: MEDIUM TTL (moderately dynamic)
    - City-specific lists: MEDIUM TTL
    - Invalidation on write operations (add/update/delete)
    """

    def __init__(self, session: AsyncSession):
        super().__init__(Recruiter, session)

    @cached(
        key_builder=lambda self, id: CacheKeys.recruiter(id),
        ttl=CacheTTL.LONG,
    )
    async def get(self, id: int) -> Result[Recruiter, NotFoundError | DatabaseError]:
        """
        Get recruiter by ID with caching.

        Args:
            id: Recruiter ID

        Returns:
            Result containing recruiter or error
        """
        return await super().get(id)

    @invalidate_cache("recruiters:*", "recruiter:{arg1}")
    async def add(self, entity: Recruiter) -> Result[Recruiter, DatabaseError]:
        """
        Add recruiter with cache invalidation.

        Args:
            entity: Recruiter entity

        Returns:
            Result containing added recruiter or error
        """
        return await super().add(entity)

    @invalidate_cache("recruiters:*", "recruiter:{arg1.id}")
    async def update(self, entity: Recruiter) -> Result[Recruiter, DatabaseError]:
        """
        Update recruiter with cache invalidation.

        Args:
            entity: Recruiter entity

        Returns:
            Result containing updated recruiter or error
        """
        return await super().update(entity)

    @invalidate_cache("recruiters:*", "recruiter:{arg1}")
    async def delete(self, id: int) -> Result[bool, DatabaseError]:
        """
        Delete recruiter with cache invalidation.

        Args:
            id: Recruiter ID

        Returns:
            Result indicating success or error
        """
        return await super().delete(id)

    @cached(
        key_builder=lambda self: CacheKeys.recruiters_active(),
        ttl=CacheTTL.MEDIUM,
    )
    async def get_active(self) -> Result[Sequence[Recruiter], DatabaseError]:
        """
        Get all active recruiters.

        Returns:
            Result containing list of active recruiters or error
        """
        try:
            stmt = (
                select(Recruiter)
                .where(Recruiter.active.is_(True))
                .order_by(Recruiter.name.asc())
            )
            result = await self.session.execute(stmt)
            recruiters = result.scalars().all()

            return success(recruiters)

        except Exception as e:
            return failure(
                DatabaseError(
                    operation="Recruiter.get_active",
                    message=str(e),
                    original_exception=e,
                )
            )

    @cached(
        key_builder=lambda self, city_id: CacheKeys.recruiters_for_city(city_id),
        ttl=CacheTTL.MEDIUM,
    )
    async def get_for_city(self, city_id: int) -> Result[Sequence[Recruiter], DatabaseError]:
        """
        Get active recruiters linked to a specific city.

        Args:
            city_id: City ID

        Returns:
            Result containing list of recruiters or error
        """
        try:
            stmt = (
                select(Recruiter)
                .join(Recruiter.cities)
                .where(
                    Recruiter.active.is_(True),
                    # Join condition already filters by city through relationship
                )
                .options(selectinload(Recruiter.cities))
                .order_by(Recruiter.name.asc())
            )
            result = await self.session.execute(stmt)
            recruiters = result.scalars().all()

            # Filter by city_id
            filtered = [r for r in recruiters if any(c.id == city_id for c in r.cities)]

            return success(filtered)

        except Exception as e:
            return failure(
                DatabaseError(
                    operation="Recruiter.get_for_city",
                    message=str(e),
                    original_exception=e,
                )
            )

    async def find_by_telegram_id(
        self, tg_chat_id: int
    ) -> Result[Recruiter | None, DatabaseError]:
        """
        Find recruiter by Telegram chat ID.

        Args:
            tg_chat_id: Telegram chat ID

        Returns:
            Result containing recruiter or None if not found, or error
        """
        try:
            stmt = select(Recruiter).where(Recruiter.tg_chat_id == tg_chat_id)
            result = await self.session.execute(stmt)
            recruiter = result.scalar_one_or_none()

            return success(recruiter)

        except Exception as e:
            return failure(
                DatabaseError(
                    operation="Recruiter.find_by_telegram_id",
                    message=str(e),
                    original_exception=e,
                )
            )
