from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.sql.schema import MetaData

logger = logging.getLogger(__name__)


def _quoted(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _default_sql(column) -> str | None:
    if column.server_default is not None:
        arg = getattr(column.server_default, "arg", None)
        if isinstance(arg, str):
            return f" DEFAULT {arg}"
        if hasattr(arg, "text") and isinstance(arg.text, str):
            text_value = arg.text.strip()
            # SQLite rejects many function defaults on ALTER ADD COLUMN.
            if "(" in text_value and ")" in text_value:
                return None
            return f" DEFAULT {text_value}"
    default = getattr(column.default, "arg", None)
    if default is None or callable(default):
        return None
    if isinstance(default, bool):
        return f" DEFAULT {1 if default else 0}"
    if isinstance(default, (int, float)):
        return f" DEFAULT {default}"
    if isinstance(default, str):
        return " DEFAULT " + "'" + default.replace("'", "''") + "'"
    return None


def _column_sql(column, dialect) -> str:
    type_sql = column.type.compile(dialect=dialect)
    parts = [_quoted(column.name), type_sql]
    default_sql = _default_sql(column)
    if default_sql:
        parts.append(default_sql.strip())
    elif not column.nullable and not column.primary_key:
        # Existing SQLite rows cannot satisfy a new NOT NULL column without a default.
        # For dev recovery prefer schema availability over strict historical nullability.
        logger.warning(
            "SQLite dev repair relaxing NOT NULL for %s.%s (no safe default)",
            column.table.name,
            column.name,
        )
    elif not column.nullable and column.primary_key:
        parts.append("NOT NULL")
    elif not column.nullable:
        parts.append("NOT NULL")
    return " ".join(parts)


def repair_sqlite_schema(*, engine: Engine, metadata: MetaData) -> None:
    """Best-effort SQLite schema repair for development/test databases.

    SQLite does not support many ALTER patterns used by the main migration path,
    and `metadata.create_all()` does not add newly introduced columns to existing tables.
    This helper only adds missing columns/tables and never drops or rewrites data.
    """

    metadata.create_all(bind=engine)

    with engine.begin() as conn:
        inspector = inspect(conn)
        table_names = set(inspector.get_table_names())
        for table in metadata.sorted_tables:
            if table.name not in table_names:
                continue
            existing_columns = {column["name"] for column in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name in existing_columns:
                    continue
                ddl = f"ALTER TABLE {_quoted(table.name)} ADD COLUMN {_column_sql(column, conn.dialect)}"
                logger.info("SQLite dev repair applying: %s", ddl)
                conn.execute(text(ddl))

