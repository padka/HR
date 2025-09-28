"""Minimal migration runner inspired by Alembic.

This module discovers migration modules located inside
``backend.migrations.versions`` and applies them sequentially while tracking
state in the ``alembic_version`` table. Each migration module should expose
``revision`` and ``down_revision`` identifiers along with ``upgrade`` and
``downgrade`` callables that accept a synchronous SQLAlchemy connection.
"""

from __future__ import annotations

import importlib
import pkgutil
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Iterable, List, Optional, Sequence

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine

from backend.core.settings import get_settings

MIGRATIONS_PACKAGE = "backend.migrations.versions"
VERSION_TABLE = "alembic_version"
VERSION_COLUMN = "version_num"


@dataclass(frozen=True)
class MigrationModule:
    """Container describing a single migration module."""

    revision: str
    down_revision: Optional[str]
    module: ModuleType


def _discover_migrations() -> List[MigrationModule]:
    package = importlib.import_module(MIGRATIONS_PACKAGE)
    package_path = Path(package.__file__).resolve().parent
    modules: List[MigrationModule] = []

    for module_info in pkgutil.iter_modules([str(package_path)]):
        if module_info.ispkg or module_info.name.startswith("_"):
            continue
        module = importlib.import_module(f"{MIGRATIONS_PACKAGE}.{module_info.name}")
        revision = getattr(module, "revision", None)
        if revision is None:
            raise RuntimeError(f"Migration {module_info.name} is missing 'revision'")
        down_revision = getattr(module, "down_revision", None)
        modules.append(MigrationModule(revision=revision, down_revision=down_revision, module=module))

    modules.sort(key=lambda item: item.revision)

    # Basic sanity check ensuring the chain is linear.
    previous_revision: Optional[str] = None
    for migration in modules:
        if migration.down_revision not in {previous_revision, None}:
            raise RuntimeError(
                "Migrations are out of order: "
                f"{migration.revision} declares down_revision={migration.down_revision}, "
                f"expected {previous_revision!r}."
            )
        previous_revision = migration.revision

    return modules


def _ensure_version_storage(conn: Connection) -> None:
    conn.execute(
        text(
            f"CREATE TABLE IF NOT EXISTS {VERSION_TABLE} "
            f"({VERSION_COLUMN} VARCHAR(64) PRIMARY KEY)"
        )
    )


def _get_current_revision(conn: Connection) -> Optional[str]:
    result = conn.execute(text(f"SELECT {VERSION_COLUMN} FROM {VERSION_TABLE} LIMIT 1"))
    row = result.first()
    return row[0] if row else None


def _set_current_revision(conn: Connection, revision: Optional[str]) -> None:
    conn.execute(text(f"DELETE FROM {VERSION_TABLE}"))
    if revision is not None:
        conn.execute(
            text(f"INSERT INTO {VERSION_TABLE} ({VERSION_COLUMN}) VALUES (:revision)"),
            {"revision": revision},
        )


def _slice_pending_migrations(
    migrations: Sequence[MigrationModule],
    current_revision: Optional[str],
    target_revision: Optional[str],
) -> Iterable[MigrationModule]:
    if not migrations:
        return []

    if target_revision is None:
        target_index = len(migrations) - 1
    else:
        try:
            target_index = next(i for i, item in enumerate(migrations) if item.revision == target_revision)
        except StopIteration as exc:  # pragma: no cover - defensive branch
            raise RuntimeError(f"Unknown migration revision: {target_revision}") from exc

    if current_revision is None:
        start_index = -1
    else:
        try:
            start_index = next(i for i, item in enumerate(migrations) if item.revision == current_revision)
        except StopIteration as exc:
            raise RuntimeError(
                f"Database is at unknown migration revision {current_revision!r}."
            ) from exc

    if target_index <= start_index:
        return []

    return migrations[start_index + 1 : target_index + 1]


def upgrade_to_head(engine_or_url: Engine | str | None = None) -> None:
    """Upgrade the database to the latest available migration."""

    migrations = _discover_migrations()
    if not migrations:
        return

    if engine_or_url is None:
        settings = get_settings()
        engine = create_engine(settings.database_url_sync, future=True)
        should_dispose = True
    elif isinstance(engine_or_url, Engine):
        engine = engine_or_url
        should_dispose = False
    else:
        engine = create_engine(engine_or_url, future=True)
        should_dispose = True

    try:
        with engine.begin() as conn:
            _ensure_version_storage(conn)
            current = _get_current_revision(conn)
            target = migrations[-1].revision
            for migration in _slice_pending_migrations(migrations, current, target):
                upgrade = getattr(migration.module, "upgrade", None)
                if upgrade is None:
                    raise RuntimeError(f"Migration {migration.revision} is missing upgrade()")
                upgrade(conn)
                _set_current_revision(conn, migration.revision)
    finally:
        if should_dispose:
            engine.dispose()
