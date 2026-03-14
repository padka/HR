"""Compatibility shim for a locally stamped candidate portal revision.

The local development database can already be stamped with
``0095_add_candidate_portal_journey`` from a branch that is not present in the
current repository snapshot. We keep this no-op bridge so migration discovery
remains linear and existing local databases can continue upgrading safely.
"""

from __future__ import annotations

from sqlalchemy.engine import Connection

revision = "0095_add_candidate_portal_journey"
down_revision = "0094_add_candidate_chat_archive_state"
branch_labels = None
depends_on = None


def upgrade(conn: Connection) -> None:  # pragma: no cover
    del conn


def downgrade(conn: Connection) -> None:  # pragma: no cover
    del conn
