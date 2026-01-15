"""
Base Repository implementation with common CRUD operations.

This generic repository provides standard data access patterns with
type-safe error handling using the Result pattern.
"""

from __future__ import annotations

import logging
from typing import Any, Generic, Sequence, Type, TypeVar, cast

from sqlalchemy import delete as sa_delete
from sqlalchemy import exists as sa_exists
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.result import (
    DatabaseError,
    NotFoundError,
    Result,
    failure,
    success,
)
from backend.domain.base import Base

logger = logging.getLogger(__name__)

T_Model = TypeVar("T_Model", bound=Base)


class BaseRepository(Generic[T_Model]):
    """
    Generic repository providing CRUD operations for any SQLAlchemy model.

    Type Parameters:
        T_Model: The SQLAlchemy model type this repository manages

    Example:
        class UserRepository(BaseRepository[User]):
            def __init__(self, session: AsyncSession):
                super().__init__(User, session)

            async def find_by_email(self, email: str) -> Result[User, NotFoundError]:
                # Custom query
                ...
    """

    def __init__(self, model: Type[T_Model], session: AsyncSession):
        """
        Initialize repository.

        Args:
            model: SQLAlchemy model class
            session: Async database session
        """
        self.model = model
        self.session = session

    @property
    def model_name(self) -> str:
        """Get the model name for error messages."""
        return self.model.__name__

    async def get(self, id: int) -> Result[T_Model, NotFoundError | DatabaseError]:
        """
        Get entity by ID.

        Args:
            id: Primary key value

        Returns:
            Result containing entity or error
        """
        try:
            stmt = select(self.model).where(self.model.id == id)
            result = await self.session.execute(stmt)
            entity = result.scalar_one_or_none()

            if entity is None:
                return failure(
                    NotFoundError(
                        entity_type=self.model_name,
                        entity_id=id,
                    )
                )

            return success(entity)

        except SQLAlchemyError as e:
            logger.error(
                f"Database error in {self.model_name}.get(id={id})",
                exc_info=True,
            )
            return failure(
                DatabaseError(
                    operation=f"{self.model_name}.get",
                    message=str(e),
                    original_exception=e,
                )
            )

    async def get_all(
        self,
        limit: int | None = None,
        offset: int | None = None,
        order_by: Any | None = None,
    ) -> Result[Sequence[T_Model], DatabaseError]:
        """
        Get all entities with optional pagination.

        Args:
            limit: Maximum number of results
            offset: Number of results to skip
            order_by: SQLAlchemy order_by clause

        Returns:
            Result containing list of entities or error
        """
        try:
            stmt = select(self.model)

            if order_by is not None:
                stmt = stmt.order_by(order_by)

            if limit is not None:
                stmt = stmt.limit(limit)

            if offset is not None:
                stmt = stmt.offset(offset)

            result = await self.session.execute(stmt)
            entities = result.scalars().all()

            return success(entities)

        except SQLAlchemyError as e:
            logger.error(
                f"Database error in {self.model_name}.get_all()",
                exc_info=True,
            )
            return failure(
                DatabaseError(
                    operation=f"{self.model_name}.get_all",
                    message=str(e),
                    original_exception=e,
                )
            )

    async def add(self, entity: T_Model) -> Result[T_Model, DatabaseError]:
        """
        Add new entity to the database.

        Args:
            entity: Entity to add

        Returns:
            Result containing added entity (with ID) or error
        """
        try:
            self.session.add(entity)
            await self.session.flush()  # Get ID without committing
            await self.session.refresh(entity)  # Ensure all fields are loaded

            return success(entity)

        except IntegrityError as e:
            logger.warning(
                f"Integrity error in {self.model_name}.add(): {e}",
                exc_info=False,
            )
            return failure(
                DatabaseError(
                    operation=f"{self.model_name}.add",
                    message=f"Constraint violation: {e.orig}",
                    original_exception=e,
                )
            )

        except SQLAlchemyError as e:
            logger.error(
                f"Database error in {self.model_name}.add()",
                exc_info=True,
            )
            return failure(
                DatabaseError(
                    operation=f"{self.model_name}.add",
                    message=str(e),
                    original_exception=e,
                )
            )

    async def update(self, entity: T_Model) -> Result[T_Model, DatabaseError]:
        """
        Update existing entity in the database.

        Args:
            entity: Entity to update (must have ID)

        Returns:
            Result containing updated entity or error
        """
        try:
            merged = await self.session.merge(entity)
            await self.session.flush()
            await self.session.refresh(merged)

            return success(merged)

        except IntegrityError as e:
            logger.warning(
                f"Integrity error in {self.model_name}.update(): {e}",
                exc_info=False,
            )
            return failure(
                DatabaseError(
                    operation=f"{self.model_name}.update",
                    message=f"Constraint violation: {e.orig}",
                    original_exception=e,
                )
            )

        except SQLAlchemyError as e:
            logger.error(
                f"Database error in {self.model_name}.update()",
                exc_info=True,
            )
            return failure(
                DatabaseError(
                    operation=f"{self.model_name}.update",
                    message=str(e),
                    original_exception=e,
                )
            )

    async def delete(self, id: int) -> Result[bool, DatabaseError]:
        """
        Delete entity by ID.

        Args:
            id: Primary key value

        Returns:
            Result containing True if deleted, False if not found, or error
        """
        try:
            stmt = sa_delete(self.model).where(self.model.id == id)
            result = await self.session.execute(stmt)
            await self.session.flush()

            deleted = result.rowcount > 0
            return success(deleted)

        except SQLAlchemyError as e:
            logger.error(
                f"Database error in {self.model_name}.delete(id={id})",
                exc_info=True,
            )
            return failure(
                DatabaseError(
                    operation=f"{self.model_name}.delete",
                    message=str(e),
                    original_exception=e,
                )
            )

    async def exists(self, id: int) -> Result[bool, DatabaseError]:
        """
        Check if entity exists by ID.

        Args:
            id: Primary key value

        Returns:
            Result containing True if exists, False otherwise, or error
        """
        try:
            stmt = select(sa_exists().where(self.model.id == id))
            result = await self.session.execute(stmt)
            exists_result = result.scalar()

            return success(bool(exists_result))

        except SQLAlchemyError as e:
            logger.error(
                f"Database error in {self.model_name}.exists(id={id})",
                exc_info=True,
            )
            return failure(
                DatabaseError(
                    operation=f"{self.model_name}.exists",
                    message=str(e),
                    original_exception=e,
                )
            )

    async def count(self) -> Result[int, DatabaseError]:
        """
        Count total number of entities.

        Returns:
            Result containing count or error
        """
        try:
            stmt = select(func.count()).select_from(self.model)
            result = await self.session.execute(stmt)
            count = result.scalar()

            return success(count or 0)

        except SQLAlchemyError as e:
            logger.error(
                f"Database error in {self.model_name}.count()",
                exc_info=True,
            )
            return failure(
                DatabaseError(
                    operation=f"{self.model_name}.count",
                    message=str(e),
                    original_exception=e,
                )
            )
