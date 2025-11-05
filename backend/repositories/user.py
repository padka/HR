"""User and related entities repository implementation."""

from __future__ import annotations

from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.repository.base import BaseRepository
from backend.core.result import DatabaseError, Result, failure, success
from backend.domain.candidates.models import User, TestResult, AutoMessage


class UserRepository(BaseRepository[User]):
    """Repository for User (Candidate) entities."""

    def __init__(self, session: AsyncSession):
        super().__init__(User, session)

    async def find_by_telegram_id(
        self, telegram_id: int
    ) -> Result[User | None, DatabaseError]:
        """
        Find user by Telegram ID.

        Args:
            telegram_id: Telegram user ID

        Returns:
            Result containing user or None if not found, or error
        """
        try:
            stmt = select(User).where(User.telegram_id == telegram_id)
            result = await self.session.execute(stmt)
            user = result.scalar_one_or_none()

            return success(user)

        except Exception as e:
            return failure(
                DatabaseError(
                    operation="User.find_by_telegram_id",
                    message=str(e),
                    original_exception=e,
                )
            )

    async def get_active(self) -> Result[Sequence[User], DatabaseError]:
        """
        Get all active users.

        Returns:
            Result containing list of active users or error
        """
        try:
            stmt = select(User).where(User.is_active.is_(True))
            result = await self.session.execute(stmt)
            users = result.scalars().all()

            return success(users)

        except Exception as e:
            return failure(
                DatabaseError(
                    operation="User.get_active",
                    message=str(e),
                    original_exception=e,
                )
            )


class TestResultRepository(BaseRepository[TestResult]):
    """Repository for TestResult entities."""

    def __init__(self, session: AsyncSession):
        super().__init__(TestResult, session)

    async def get_for_user(
        self, telegram_id: int
    ) -> Result[Sequence[TestResult], DatabaseError]:
        """
        Get all test results for a user.

        Args:
            telegram_id: Telegram user ID

        Returns:
            Result containing list of test results or error
        """
        try:
            stmt = (
                select(TestResult)
                .where(TestResult.telegram_id == telegram_id)
                .order_by(TestResult.completed_at.desc())
            )
            result = await self.session.execute(stmt)
            results = result.scalars().all()

            return success(results)

        except Exception as e:
            return failure(
                DatabaseError(
                    operation="TestResult.get_for_user",
                    message=str(e),
                    original_exception=e,
                )
            )


class AutoMessageRepository(BaseRepository[AutoMessage]):
    """Repository for AutoMessage entities."""

    def __init__(self, session: AsyncSession):
        super().__init__(AutoMessage, session)

    async def get_active_for_user(
        self, telegram_id: int
    ) -> Result[Sequence[AutoMessage], DatabaseError]:
        """
        Get active messages for a user.

        Args:
            telegram_id: Telegram user ID

        Returns:
            Result containing list of active messages or error
        """
        try:
            stmt = (
                select(AutoMessage)
                .where(
                    AutoMessage.telegram_id == telegram_id,
                    AutoMessage.is_active.is_(True),
                )
                .order_by(AutoMessage.created_at.desc())
            )
            result = await self.session.execute(stmt)
            messages = result.scalars().all()

            return success(messages)

        except Exception as e:
            return failure(
                DatabaseError(
                    operation="AutoMessage.get_active_for_user",
                    message=str(e),
                    original_exception=e,
                )
            )
