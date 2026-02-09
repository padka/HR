"""Message template repository implementation."""

from __future__ import annotations

from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.repository.base import BaseRepository
from backend.core.result import DatabaseError, Result, failure, success
from backend.domain.models import MessageTemplate


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
