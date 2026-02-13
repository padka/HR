"""SQLAlchemy table metadata for analytics_events.

In production (PostgreSQL), this table is created and maintained via migrations.
In local dev/test/e2e with SQLite we often rely on `Base.metadata.create_all`,
so we register the table here to avoid runtime insert/query errors.
"""

from __future__ import annotations

from sqlalchemy import BigInteger, Column, DateTime, Integer, String, Table, Text, Index
from sqlalchemy.sql import func

from backend.domain.base import Base


analytics_events = Table(
    "analytics_events",
    Base.metadata,
    Column("id", Integer, primary_key=True),
    Column("event_name", String(100), nullable=False),
    Column("user_id", BigInteger, nullable=True),
    Column("candidate_id", Integer, nullable=True),
    Column("city_id", Integer, nullable=True),
    Column("slot_id", Integer, nullable=True),
    Column("booking_id", Integer, nullable=True),
    Column("metadata", Text, nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
)

Index("idx_analytics_events_event_name", analytics_events.c.event_name)
Index("idx_analytics_events_candidate_id", analytics_events.c.candidate_id)
Index("idx_analytics_events_created_at", analytics_events.c.created_at)
Index("idx_analytics_events_user_id", analytics_events.c.user_id)

