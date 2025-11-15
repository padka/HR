"""
Result Pattern implementation for type-safe error handling.

This module provides a Railway-Oriented Programming approach to error handling,
allowing you to chain operations without explicit exception handling.

Example:
    result = await repository.get_user(user_id)
    match result:
        case Success(user):
            print(f"Found user: {user.name}")
        case Failure(error):
            print(f"Error: {error}")
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Callable, Generic, TypeVar, Union, cast

T = TypeVar("T")
E = TypeVar("E")
U = TypeVar("U")


_DATACLASS_SLOTS: dict[str, bool] = {"slots": True} if sys.version_info >= (3, 10) else {}


@dataclass(frozen=True, **_DATACLASS_SLOTS)
class Success(Generic[T]):
    """Represents a successful operation result."""

    value: T

    def is_success(self) -> bool:
        return True

    def is_failure(self) -> bool:
        return False

    def unwrap(self) -> T:
        """Extract the success value."""
        return self.value

    def unwrap_or(self, _default: T) -> T:
        """Extract value or return default (returns value)."""
        return self.value

    def map(self, func: Callable[[T], U]) -> Result[U, E]:
        """Transform the success value."""
        try:
            return Success(func(self.value))
        except Exception as e:
            return Failure(cast(E, e))

    def flat_map(self, func: Callable[[T], Result[U, E]]) -> Result[U, E]:
        """Chain operations that return Results."""
        try:
            return func(self.value)
        except Exception as e:
            return Failure(cast(E, e))

    def __repr__(self) -> str:
        return f"Success({self.value!r})"


@dataclass(frozen=True, **_DATACLASS_SLOTS)
class Failure(Generic[E]):
    """Represents a failed operation result."""

    error: E

    def is_success(self) -> bool:
        return False

    def is_failure(self) -> bool:
        return True

    def unwrap(self) -> T:
        """Raises the error when trying to extract value."""
        if isinstance(self.error, Exception):
            raise self.error
        raise RuntimeError(f"Operation failed: {self.error}")

    def unwrap_or(self, default: T) -> T:
        """Extract value or return default (returns default)."""
        return default

    def map(self, _func: Callable[[T], U]) -> Result[U, E]:
        """Skip transformation on failure."""
        return cast(Result[U, E], self)

    def flat_map(self, _func: Callable[[T], Result[U, E]]) -> Result[U, E]:
        """Skip chaining on failure."""
        return cast(Result[U, E], self)

    def __repr__(self) -> str:
        return f"Failure({self.error!r})"


# Type alias for Result
Result = Union[Success[T], Failure[E]]


# Helper functions for cleaner code
def success(value: T) -> Success[T]:
    """Create a Success result."""
    return Success(value)


def failure(error: E) -> Failure[E]:
    """Create a Failure result."""
    return Failure(error)


# Common error types
@dataclass(frozen=True, **_DATACLASS_SLOTS)
class NotFoundError:
    """Entity not found error."""

    entity_type: str
    entity_id: str | int
    message: str | None = None

    def __str__(self) -> str:
        if self.message:
            return self.message
        return f"{self.entity_type} with id={self.entity_id} not found"


@dataclass(frozen=True, **_DATACLASS_SLOTS)
class ValidationError:
    """Validation failed error."""

    field: str
    message: str
    value: str | None = None

    def __str__(self) -> str:
        if self.value:
            return f"{self.field}: {self.message} (got: {self.value})"
        return f"{self.field}: {self.message}"


@dataclass(frozen=True, **_DATACLASS_SLOTS)
class DatabaseError:
    """Database operation error."""

    operation: str
    message: str
    original_exception: Exception | None = None

    def __str__(self) -> str:
        return f"Database error during {self.operation}: {self.message}"


@dataclass(frozen=True, **_DATACLASS_SLOTS)
class ConflictError:
    """Conflict error (e.g., duplicate key, constraint violation)."""

    entity_type: str
    message: str
    conflicting_field: str | None = None

    def __str__(self) -> str:
        if self.conflicting_field:
            return f"{self.entity_type} conflict on {self.conflicting_field}: {self.message}"
        return f"{self.entity_type} conflict: {self.message}"


# Async support
async def async_success(value: T) -> Success[T]:
    """Create a Success result asynchronously."""
    return Success(value)


async def async_failure(error: E) -> Failure[E]:
    """Create a Failure result asynchronously."""
    return Failure(error)


# Utility for collecting results
def collect_results(results: list[Result[T, E]]) -> Result[list[T], E]:
    """
    Collect a list of Results into a single Result.

    If all results are Success, returns Success with list of values.
    If any result is Failure, returns the first Failure.
    """
    values: list[T] = []
    for result in results:
        if result.is_failure():
            return cast(Result[list[T], E], result)
        values.append(result.unwrap())
    return Success(values)
