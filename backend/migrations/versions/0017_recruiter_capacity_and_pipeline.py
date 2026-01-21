"""Restore missing recruiter capacity and pipeline migration."""

from __future__ import annotations

from sqlalchemy.engine import Connection

revision = "0017_recruiter_capacity_and_pipeline"
down_revision = "0017_bot_message_logs"
branch_labels = None
depends_on = None


def upgrade(conn: Connection) -> None:
    """No-op migration maintained for historical compatibility."""
    # The original revision has been removed from the repository, yet existing
    # databases still report ``0017_recruiter_capacity_and_pipeline`` in the
    # ``alembic_version`` table.  Leaving a stub migration keeps the revision
    # chain intact so the lightweight runner can recognise the current state
    # instead of crashing during startup.
    return None


def downgrade(conn: Connection) -> None:  # pragma: no cover - symmetry with upgrade
    """No-op downgrade matching :func:`upgrade`."""
    return None
