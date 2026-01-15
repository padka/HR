"""Slot repository implementation with caching and query optimization."""

from __future__ import annotations

from datetime import datetime
from typing import Sequence

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.core.repository.base import BaseRepository
from backend.core.result import DatabaseError, NotFoundError, Result, failure, success
from backend.core.cache import CacheKeys, CacheTTL
from backend.core.cache_decorators import cached, invalidate_cache
from backend.core.query_optimization import QueryOptimizer
from backend.domain.models import Slot, SlotStatus


class SlotRepository(BaseRepository[Slot]):
    """
    Repository for Slot entities with caching and optimization.

    Caching strategy:
    - Individual slots: SHORT TTL (frequently changing)
    - Free slots list: SHORT TTL (dynamic data)
    - Invalidation on status changes
    """

    def __init__(self, session: AsyncSession):
        super().__init__(Slot, session)

    @cached(
        key_builder=lambda self, id: CacheKeys.slot(id),
        ttl=CacheTTL.SHORT,
    )
    async def get(self, id: int) -> Result[Slot, NotFoundError | DatabaseError]:
        """Get slot by ID with caching and eager loading."""
        # Override to add eager loading
        try:
            stmt = (
                select(Slot)
                .where(Slot.id == id)
                .options(
                    selectinload(Slot.recruiter),
                    selectinload(Slot.city),
                )
            )
            result = await self.session.execute(stmt)
            slot = result.scalar_one_or_none()

            if slot is None:
                return failure(
                    NotFoundError(
                        entity_type="Slot",
                        entity_id=id,
                        message=f"Slot with id {id} not found",
                    )
                )

            return success(slot)

        except Exception as e:
            return failure(
                DatabaseError(
                    operation="Slot.get",
                    message=str(e),
                    original_exception=e,
                )
            )

    @invalidate_cache("slots:*", "slot:{arg1.id}")
    async def update(self, entity: Slot) -> Result[Slot, DatabaseError]:
        """Update slot with cache invalidation."""
        return await super().update(entity)

    @invalidate_cache("slots:*", "slot:{arg1}")
    async def delete(self, id: int) -> Result[bool, DatabaseError]:
        """Delete slot with cache invalidation."""
        return await super().delete(id)

    @cached(
        key_builder=lambda self, recruiter_id, after: CacheKeys.slots_free_for_recruiter(recruiter_id),
        ttl=CacheTTL.SHORT,
    )
    async def get_free_for_recruiter(
        self,
        recruiter_id: int,
        after: datetime,
    ) -> Result[Sequence[Slot], DatabaseError]:
        """
        Get free slots for a recruiter after a given datetime.

        Args:
            recruiter_id: Recruiter ID
            after: Only return slots after this datetime

        Returns:
            Result containing list of free slots or error
        """
        try:
            stmt = (
                select(Slot)
                .where(
                    and_(
                        Slot.recruiter_id == recruiter_id,
                        Slot.status == SlotStatus.FREE,
                        Slot.start_utc > after,
                    )
                )
                .options(
                    selectinload(Slot.recruiter),
                    selectinload(Slot.city),
                )
                .order_by(Slot.start_utc.asc())
            )
            result = await self.session.execute(stmt)
            slots = result.scalars().all()

            return success(slots)

        except Exception as e:
            return failure(
                DatabaseError(
                    operation="Slot.get_free_for_recruiter",
                    message=str(e),
                    original_exception=e,
                )
            )

    async def get_upcoming_for_candidate(
        self,
        telegram_id: int,
        after: datetime,
    ) -> Result[Sequence[Slot], DatabaseError]:
        """
        Get upcoming slots for a candidate.

        Args:
            telegram_id: Telegram user ID
            after: Only return slots after this datetime

        Returns:
            Result containing list of slots or error
        """
        try:
            stmt = (
                select(Slot)
                .where(
                    and_(
                        Slot.candidate_tg_id == telegram_id,
                        Slot.start_utc > after,
                    )
                )
                .options(
                    selectinload(Slot.recruiter),
                    selectinload(Slot.city),
                )
                .order_by(Slot.start_utc.asc())
            )
            result = await self.session.execute(stmt)
            slots = result.scalars().all()

            return success(slots)

        except Exception as e:
            return failure(
                DatabaseError(
                    operation="Slot.get_upcoming_for_candidate",
                    message=str(e),
                    original_exception=e,
                )
            )
