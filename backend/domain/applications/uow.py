from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Protocol

from sqlalchemy.orm import Session

_EXPLICIT_TX_KEY = "rs_applications_explicit_tx_depth"


class TransactionRequiredError(RuntimeError):
    """Raised when a repository operation requires an explicit transaction scope."""


class ApplicationUnitOfWork(Protocol):
    def begin(self) -> Iterator[ApplicationUnitOfWork]:
        ...

    def ensure_transaction(self) -> None:
        ...

    def commit(self) -> None:
        ...

    def rollback(self) -> None:
        ...


class SqlAlchemyApplicationUnitOfWork:
    """Explicit transaction boundary for Phase B adapters.

    The adapter tracks an explicit transaction marker in ``session.info`` so
    repositories can reject accidental SQLAlchemy autobegin scopes.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    @contextmanager
    def begin(self) -> Iterator[SqlAlchemyApplicationUnitOfWork]:
        depth = int(self._session.info.get(_EXPLICIT_TX_KEY, 0))
        if depth > 0 or self._session.in_transaction():
            transaction = self._session.begin_nested()
        else:
            transaction = self._session.begin()

        self._session.info[_EXPLICIT_TX_KEY] = depth + 1
        try:
            with transaction:
                yield self
        finally:
            remaining = max(int(self._session.info.get(_EXPLICIT_TX_KEY, 1)) - 1, 0)
            if remaining:
                self._session.info[_EXPLICIT_TX_KEY] = remaining
            else:
                self._session.info.pop(_EXPLICIT_TX_KEY, None)

    def ensure_transaction(self) -> None:
        explicit_depth = int(self._session.info.get(_EXPLICIT_TX_KEY, 0))
        if explicit_depth <= 0 or not self._session.in_transaction():
            raise TransactionRequiredError(
                "explicit transaction scope is required; use SqlAlchemyApplicationUnitOfWork.begin()"
            )

    def commit(self) -> None:
        self.ensure_transaction()
        self._session.commit()

    def rollback(self) -> None:
        if self._session.in_transaction():
            self._session.rollback()


__all__ = [
    "ApplicationUnitOfWork",
    "SqlAlchemyApplicationUnitOfWork",
    "TransactionRequiredError",
]
