"""Template repositories implementation."""

from __future__ import annotations

from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.repository.base import BaseRepository
from backend.core.result import DatabaseError, Result, failure, success
from backend.domain.models import Template, MessageTemplate


class TemplateRepository(BaseRepository[Template]):
    """Repository for Template entities."""

    def __init__(self, session: AsyncSession):
        super().__init__(Template, session)

    async def get_for_city(self, city_id: int) -> Result[Sequence[Template], DatabaseError]:
        """
        Get all templates for a specific city.

        Args:
            city_id: City ID

        Returns:
            Result containing list of templates or error
        """
        try:
            stmt = select(Template).where(Template.city_id == city_id)
            result = await self.session.execute(stmt)
            templates = result.scalars().all()

            return success(templates)

        except Exception as e:
            return failure(
                DatabaseError(
                    operation="Template.get_for_city",
                    message=str(e),
                    original_exception=e,
                )
            )

    async def find_by_key(
        self, city_id: int, key: str
    ) -> Result[Template | None, DatabaseError]:
        """
        Find template by city and key.

        Args:
            city_id: City ID
            key: Template key

        Returns:
            Result containing template or None if not found, or error
        """
        try:
            stmt = select(Template).where(
                Template.city_id == city_id, Template.key == key
            )
            result = await self.session.execute(stmt)
            template = result.scalar_one_or_none()

            return success(template)

        except Exception as e:
            return failure(
                DatabaseError(
                    operation="Template.find_by_key",
                    message=str(e),
                    original_exception=e,
                )
            )


class MessageTemplateRepository(BaseRepository[MessageTemplate]):
    """Repository for MessageTemplate entities."""

    def __init__(self, session: AsyncSession):
        super().__init__(MessageTemplate, session)

    async def get_active(self) -> Result[Sequence[MessageTemplate], DatabaseError]:
        """
        Get all active message templates.

        Returns:
            Result containing list of active templates or error
        """
        try:
            stmt = select(MessageTemplate).where(MessageTemplate.is_active.is_(True))
            result = await self.session.execute(stmt)
            templates = result.scalars().all()

            return success(templates)

        except Exception as e:
            return failure(
                DatabaseError(
                    operation="MessageTemplate.get_active",
                    message=str(e),
                    original_exception=e,
                )
            )
