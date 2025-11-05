"""
Protocol definitions for repository and unit of work interfaces.

These protocols define the contracts that repositories and units of work must implement.
"""

from __future__ import annotations

from typing import Any, Generic, Protocol, Sequence, TypeVar

from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.result import Result, NotFoundError, DatabaseError

T = TypeVar("T")
T_Model = TypeVar("T_Model")


class IRepository(Protocol, Generic[T_Model]):
    """Repository protocol defining the contract for data access."""

    async def get(self, id: int) -> Result[T_Model, NotFoundError | DatabaseError]:
        """Get entity by ID."""
        ...

    async def get_all(
        self, limit: int | None = None, offset: int | None = None
    ) -> Result[Sequence[T_Model], DatabaseError]:
        """Get all entities with optional pagination."""
        ...

    async def add(self, entity: T_Model) -> Result[T_Model, DatabaseError]:
        """Add new entity."""
        ...

    async def update(self, entity: T_Model) -> Result[T_Model, DatabaseError]:
        """Update existing entity."""
        ...

    async def delete(self, id: int) -> Result[bool, DatabaseError]:
        """Delete entity by ID."""
        ...

    async def exists(self, id: int) -> Result[bool, DatabaseError]:
        """Check if entity exists."""
        ...


class IUnitOfWork(Protocol):
    """Unit of Work protocol defining transaction management contract."""

    async def __aenter__(self) -> IUnitOfWork:
        """Enter async context."""
        ...

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit async context."""
        ...

    async def commit(self) -> None:
        """Commit the current transaction."""
        ...

    async def rollback(self) -> None:
        """Rollback the current transaction."""
        ...

    @property
    def session(self) -> AsyncSession:
        """Get the current session."""
        ...
