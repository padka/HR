from __future__ import annotations

from typing import Optional

from sqlalchemy import inspect
from sqlalchemy.engine import Connection


def table_exists(conn: Connection, table_name: str) -> bool:
    """Проверить существование таблицы в текущей БД."""
    inspector = inspect(conn)
    return table_name in inspector.get_table_names()


def column_exists(conn: Connection, table_name: str, column_name: str) -> bool:
    """Проверить существование колонки в таблице."""
    inspector = inspect(conn)
    for col in inspector.get_columns(table_name):
        if col.get("name") == column_name:
            return True
    return False


def index_exists(conn: Connection, table_name: str, index_name: str) -> bool:
    """Проверить существование индекса по имени."""
    inspector = inspect(conn)
    try:
        indexes = inspector.get_indexes(table_name)
    except Exception:
        # На всякий случай не валимся, если диалект что-то не умеет
        return False

    for idx in indexes:
        if idx.get("name") == index_name:
            return True
    return False
