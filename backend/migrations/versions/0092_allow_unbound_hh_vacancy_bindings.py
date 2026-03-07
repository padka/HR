"""Allow storing HH vacancies before they are linked to internal vacancies."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.engine import Connection

revision = "0092_allow_unbound_hh_vacancy_bindings"
down_revision = "0091_add_hh_integration_foundation"
branch_labels = None
depends_on = None


def upgrade(conn: Connection) -> None:
    if conn.dialect.name == "postgresql":
        conn.execute(
            sa.text(
                "ALTER TABLE external_vacancy_bindings "
                "ALTER COLUMN vacancy_id DROP NOT NULL"
            )
        )


def downgrade(conn: Connection) -> None:  # pragma: no cover
    if conn.dialect.name == "postgresql":
        conn.execute(
            sa.text(
                "DELETE FROM external_vacancy_bindings "
                "WHERE vacancy_id IS NULL"
            )
        )
        conn.execute(
            sa.text(
                "ALTER TABLE external_vacancy_bindings "
                "ALTER COLUMN vacancy_id SET NOT NULL"
            )
        )
