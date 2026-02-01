"""
Unit of Work pattern implementation for transaction management.

The Unit of Work pattern coordinates changes across multiple repositories
within a single transaction, ensuring atomicity of complex operations.

Example:
    async with UnitOfWork() as uow:
        # All operations within this block share the same transaction
        user = await uow.users.get(user_id)
        user.name = "New Name"
        await uow.users.update(user)

        order = Order(user_id=user.id)
        await uow.orders.add(order)

        # Commit all changes atomically
        await uow.commit()
        # Or rollback on error (automatic on exception)
"""

from __future__ import annotations

import logging
from types import TracebackType
from typing import Any, Type

from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.db import new_async_session
from backend.domain.models import (
    City,
    Recruiter,
    Slot,
    MessageTemplate,
)
from backend.domain.candidates.models import User, TestResult, AutoMessage

logger = logging.getLogger(__name__)


class UnitOfWork:
    """
    Unit of Work for coordinating database operations.

    Manages a single database session and provides access to
    all repositories, ensuring all operations within a context
    are part of the same transaction.

    Example:
        async with UnitOfWork() as uow:
            user = await uow.users.get(1)
            if user.is_success():
                user_obj = user.unwrap()
                user_obj.active = False
                await uow.users.update(user_obj)
                await uow.commit()
    """

    def __init__(self, session: AsyncSession | None = None):
        """
        Initialize Unit of Work.

        Args:
            session: Optional existing session. If not provided, creates new one.
        """
        self._session = session
        self._should_close = session is None
        self._repositories_initialized = False

    async def __aenter__(self) -> UnitOfWork:
        """Enter async context and initialize session."""
        if self._session is None:
            self._session = new_async_session()

        # Lazy initialization of repositories
        if not self._repositories_initialized:
            self._init_repositories()
            self._repositories_initialized = True

        return self

    async def __aexit__(
        self,
        exc_type: Type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """
        Exit async context.

        Automatically rolls back on exception, commits on success.
        """
        try:
            if exc_type is not None:
                # Exception occurred, rollback
                await self.rollback()
                logger.warning(
                    f"Transaction rolled back due to {exc_type.__name__}: {exc_val}"
                )
            else:
                # No exception, try to commit
                pass  # Don't auto-commit, let caller decide

        finally:
            if self._should_close and self._session:
                await self._session.close()
                self._session = None

    def _init_repositories(self) -> None:
        """
        Initialize all repositories.

        This is called lazily on first access to ensure session is available.
        Import repositories here to avoid circular imports.
        """
        from backend.repositories import (
            RecruiterRepository,
            CityRepository,
            SlotRepository,
            UserRepository,
            TestResultRepository,
            AutoMessageRepository,
            MessageTemplateRepository,
        )

        if self._session is None:
            raise RuntimeError("Session not initialized. Use async with UnitOfWork().")

        self.recruiters = RecruiterRepository(self._session)
        self.cities = CityRepository(self._session)
        self.slots = SlotRepository(self._session)
        self.users = UserRepository(self._session)
        self.test_results = TestResultRepository(self._session)
        self.auto_messages = AutoMessageRepository(self._session)
        self.message_templates = MessageTemplateRepository(self._session)

    @property
    def session(self) -> AsyncSession:
        """
        Get the current database session.

        Returns:
            The async session

        Raises:
            RuntimeError: If session not initialized
        """
        if self._session is None:
            raise RuntimeError("Session not initialized. Use async with UnitOfWork().")
        return self._session

    async def commit(self) -> None:
        """
        Commit the current transaction.

        All pending changes across all repositories will be persisted.

        Raises:
            RuntimeError: If session not initialized
        """
        if self._session is None:
            raise RuntimeError("Session not initialized. Use async with UnitOfWork().")

        try:
            await self._session.commit()
            logger.debug("Transaction committed successfully")
        except Exception as e:
            logger.error(f"Error committing transaction: {e}", exc_info=True)
            await self.rollback()
            raise

    async def rollback(self) -> None:
        """
        Rollback the current transaction.

        All pending changes will be discarded.

        Raises:
            RuntimeError: If session not initialized
        """
        if self._session is None:
            raise RuntimeError("Session not initialized. Use async with UnitOfWork().")

        try:
            await self._session.rollback()
            logger.debug("Transaction rolled back")
        except Exception as e:
            logger.error(f"Error rolling back transaction: {e}", exc_info=True)
            raise

    async def flush(self) -> None:
        """
        Flush pending changes to database without committing.

        Useful for getting IDs of newly created entities.

        Raises:
            RuntimeError: If session not initialized
        """
        if self._session is None:
            raise RuntimeError("Session not initialized. Use async with UnitOfWork().")

        await self._session.flush()

    async def refresh(self, entity: Any) -> None:
        """
        Refresh entity from database.

        Args:
            entity: Entity to refresh

        Raises:
            RuntimeError: If session not initialized
        """
        if self._session is None:
            raise RuntimeError("Session not initialized. Use async with UnitOfWork().")

        await self._session.refresh(entity)


# Factory function for easier testing
def create_uow(session: AsyncSession | None = None) -> UnitOfWork:
    """
    Factory function to create Unit of Work.

    Args:
        session: Optional session to use

    Returns:
        New UnitOfWork instance
    """
    return UnitOfWork(session)
