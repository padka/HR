"""City repository implementation."""

from __future__ import annotations

from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.repository.base import BaseRepository
from backend.core.result import DatabaseError, Result, failure, success
from backend.domain.models import City


class CityRepository(BaseRepository[City]):
    """Repository for City entities."""

    def __init__(self, session: AsyncSession):
        super().__init__(City, session)

    async def get_active(self) -> Result[Sequence[City], DatabaseError]:
        """
        Get all active cities.

        Returns:
            Result containing list of active cities or error
        """
        try:
            stmt = select(City).where(City.active.is_(True)).order_by(City.name.asc())
            result = await self.session.execute(stmt)
            cities = result.scalars().all()

            return success(cities)

        except Exception as e:
            return failure(
                DatabaseError(
                    operation="City.get_active",
                    message=str(e),
                    original_exception=e,
                )
            )

    async def find_by_name(self, name: str) -> Result[City | None, DatabaseError]:
        """
        Find city by name.

        Args:
            name: City name

        Returns:
            Result containing city or None if not found, or error
        """
        try:
            stmt = select(City).where(City.name == name)
            result = await self.session.execute(stmt)
            city = result.scalar_one_or_none()

            return success(city)

        except Exception as e:
            return failure(
                DatabaseError(
                    operation="City.find_by_name",
                    message=str(e),
                    original_exception=e,
                )
            )
