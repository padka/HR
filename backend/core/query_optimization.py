"""Query optimization utilities for improved performance.

This module provides:
- Eager loading helpers
- Query result caching
- Batch loading utilities
- N+1 query prevention
"""

from __future__ import annotations

import logging
from typing import Any, Sequence, TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload, subqueryload
from sqlalchemy.sql import Select

logger = logging.getLogger(__name__)

T = TypeVar("T")


class QueryOptimizer:
    """
    Query optimization helper for SQLAlchemy queries.

    Provides methods to add eager loading, optimize joins,
    and prevent N+1 queries.
    """

    @staticmethod
    def with_eager_load(
        stmt: Select, *relationships: str, strategy: str = "selectinload"
    ) -> Select:
        """
        Add eager loading to query.

        Args:
            stmt: SQLAlchemy select statement
            *relationships: Relationship names to load
            strategy: Loading strategy ("selectinload", "joinedload", "subqueryload")

        Returns:
            Statement with eager loading applied

        Example:
            stmt = select(Slot)
            stmt = QueryOptimizer.with_eager_load(
                stmt,
                "recruiter",
                "city",
                strategy="selectinload"
            )
        """
        load_strategy = {
            "selectinload": selectinload,
            "joinedload": joinedload,
            "subqueryload": subqueryload,
        }.get(strategy, selectinload)

        for relationship in relationships:
            # Handle nested relationships (e.g., "recruiter.cities")
            parts = relationship.split(".")
            loader = load_strategy(parts[0])

            for part in parts[1:]:
                loader = loader.selectinload(part)

            stmt = stmt.options(loader)

        return stmt

    @staticmethod
    def with_joined_load(stmt: Select, *relationships: str) -> Select:
        """
        Add joined eager loading (single query with JOINs).

        Best for one-to-one or many-to-one relationships.

        Args:
            stmt: SQLAlchemy select statement
            *relationships: Relationship names to load

        Returns:
            Statement with joined loading

        Example:
            stmt = select(Slot)
            stmt = QueryOptimizer.with_joined_load(stmt, "recruiter", "city")
        """
        return QueryOptimizer.with_eager_load(stmt, *relationships, strategy="joinedload")

    @staticmethod
    def with_select_in_load(stmt: Select, *relationships: str) -> Select:
        """
        Add select-in eager loading (separate queries with IN clause).

        Best for one-to-many or many-to-many relationships.

        Args:
            stmt: SQLAlchemy select statement
            *relationships: Relationship names to load

        Returns:
            Statement with select-in loading

        Example:
            stmt = select(Recruiter)
            stmt = QueryOptimizer.with_select_in_load(stmt, "cities", "slots")
        """
        return QueryOptimizer.with_eager_load(stmt, *relationships, strategy="selectinload")

    @staticmethod
    async def execute_with_logging(
        session: AsyncSession,
        stmt: Select,
        log_slow_queries: bool = True,
        slow_query_threshold_ms: float = 100.0,
    ) -> Any:
        """
        Execute query with performance logging.

        Args:
            session: Database session
            stmt: Query statement
            log_slow_queries: Whether to log slow queries
            slow_query_threshold_ms: Threshold for slow query warning (milliseconds)

        Returns:
            Query result
        """
        import time

        start_time = time.time()

        result = await session.execute(stmt)

        elapsed_ms = (time.time() - start_time) * 1000

        if log_slow_queries and elapsed_ms > slow_query_threshold_ms:
            logger.warning(
                f"Slow query detected: {elapsed_ms:.2f}ms "
                f"(threshold: {slow_query_threshold_ms}ms)"
            )

        return result


class BatchLoader:
    """
    Batch loading utility to prevent N+1 queries.

    Usage:
        loader = BatchLoader(session)
        users = await loader.load_many(User, [1, 2, 3])
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def load_many(
        self,
        model: type[T],
        ids: Sequence[int],
        relationships: Sequence[str] = (),
    ) -> dict[int, T]:
        """
        Load multiple entities by ID in single query.

        Args:
            model: SQLAlchemy model class
            ids: List of entity IDs
            relationships: Relationships to eager load

        Returns:
            Dictionary mapping ID to entity

        Example:
            loader = BatchLoader(session)
            users = await loader.load_many(User, [1, 2, 3], ["orders"])
            user_1 = users[1]
        """
        if not ids:
            return {}

        stmt = select(model).where(model.id.in_(ids))

        # Add eager loading
        for relationship in relationships:
            stmt = stmt.options(selectinload(relationship))

        result = await self.session.execute(stmt)
        entities = result.scalars().all()

        # Build ID -> entity mapping
        return {entity.id: entity for entity in entities}


class QueryCache:
    """
    In-memory query result cache for session lifetime.

    Useful for avoiding repeated queries within same request.

    Usage:
        cache = QueryCache()
        user = await cache.get_or_load(session, User, user_id)
    """

    def __init__(self):
        self._cache: dict[tuple[type, int], Any] = {}

    async def get_or_load(
        self,
        session: AsyncSession,
        model: type[T],
        entity_id: int,
    ) -> T | None:
        """
        Get entity from cache or load from database.

        Args:
            session: Database session
            model: Model class
            entity_id: Entity ID

        Returns:
            Entity or None if not found
        """
        cache_key = (model, entity_id)

        if cache_key in self._cache:
            return self._cache[cache_key]

        # Load from database
        stmt = select(model).where(model.id == entity_id)
        result = await session.execute(stmt)
        entity = result.scalar_one_or_none()

        if entity is not None:
            self._cache[cache_key] = entity

        return entity

    def clear(self) -> None:
        """Clear cache."""
        self._cache.clear()


# Pre-configured query builders for common patterns
class OptimizedQueries:
    """Pre-configured optimized queries for common use cases."""

    @staticmethod
    def slots_with_relations() -> Select:
        """
        Get slots with all related data (recruiter, city).

        Optimized with select-in loading to avoid N+1 queries.
        """
        from backend.domain.models import Slot

        stmt = select(Slot).options(
            selectinload(Slot.recruiter),
            selectinload(Slot.city),
        )

        return stmt

    @staticmethod
    def recruiters_with_cities() -> Select:
        """
        Get recruiters with their cities.

        Optimized with select-in loading for many-to-many relationship.
        """
        from backend.domain.models import Recruiter

        stmt = select(Recruiter).options(selectinload(Recruiter.cities))

        return stmt

    @staticmethod
    def users_with_test_results() -> Select:
        """
        Get users with their test results.

        Optimized with select-in loading for one-to-many relationship.
        """
        from backend.domain.candidates.models import User

        stmt = select(User).options(
            selectinload(User.test_results),
            selectinload(User.auto_messages),
        )

        return stmt


# Performance monitoring
class QueryStats:
    """Track query statistics for performance monitoring."""

    def __init__(self):
        self.query_count = 0
        self.total_time_ms = 0.0
        self.slow_queries = 0
        self.slow_query_threshold_ms = 100.0

    def record_query(self, elapsed_ms: float) -> None:
        """Record query execution time."""
        self.query_count += 1
        self.total_time_ms += elapsed_ms

        if elapsed_ms > self.slow_query_threshold_ms:
            self.slow_queries += 1

    @property
    def avg_query_time_ms(self) -> float:
        """Get average query time."""
        if self.query_count == 0:
            return 0.0
        return self.total_time_ms / self.query_count

    def reset(self) -> None:
        """Reset statistics."""
        self.query_count = 0
        self.total_time_ms = 0.0
        self.slow_queries = 0

    def __str__(self) -> str:
        """String representation of stats."""
        return (
            f"Queries: {self.query_count}, "
            f"Total time: {self.total_time_ms:.2f}ms, "
            f"Avg time: {self.avg_query_time_ms:.2f}ms, "
            f"Slow queries: {self.slow_queries}"
        )
