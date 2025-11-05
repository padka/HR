"""Introduce recruiter-to-city link table for managing assignments."""

from __future__ import annotations

from typing import Iterable, Tuple

import sqlalchemy as sa
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy import inspect
from sqlalchemy.engine import Connection


revision = "0015_recruiter_city_links"
down_revision = "0014_notification_outbox_and_templates"
branch_labels = None
depends_on = None

TABLE_NAME = "recruiter_cities"


def _get_operations(conn: Connection) -> Tuple[Operations, MigrationContext, Connection]:
    engine = getattr(conn, "engine", None)
    standalone_conn = engine.connect() if engine is not None else conn
    if engine is not None and engine.dialect.name == "sqlite" and standalone_conn is not conn:
        standalone_conn.close()
        standalone_conn = conn
    context = MigrationContext.configure(connection=standalone_conn)
    return Operations(context), context, standalone_conn


def _table_exists(conn: Connection, table_name: str) -> bool:
    insp = inspect(conn)
    try:
        insp.get_table_names()
    except Exception:
        return False
    return table_name in insp.get_table_names()


def _column_exists(conn: Connection, table: str, column: str) -> bool:
    insp = inspect(conn)
    try:
        return any(col["name"] == column for col in insp.get_columns(table))
    except Exception:
        return False


def _iter_city_links(conn: Connection) -> Iterable[Tuple[int, int]]:
    rows = conn.execute(
        sa.text(
            "SELECT id AS city_id, responsible_recruiter_id AS recruiter_id "
            "FROM cities WHERE responsible_recruiter_id IS NOT NULL"
        )
    )
    for row in rows:
        recruiter_id = row.recruiter_id
        city_id = row.city_id
        if recruiter_id is None or city_id is None:
            continue
        yield int(recruiter_id), int(city_id)


def _insert_link(conn: Connection, recruiter_id: int, city_id: int) -> None:
    existing = conn.execute(
        sa.text(
            "SELECT 1 FROM recruiter_cities WHERE city_id = :city_id"
        ),
        {"city_id": city_id},
    ).first()
    if existing:
        return
    conn.execute(
        sa.text(
            "INSERT INTO recruiter_cities (recruiter_id, city_id) "
            "VALUES (:recruiter_id, :city_id)"
        ),
        {"recruiter_id": recruiter_id, "city_id": city_id},
    )


def _drop_city_owner_column(
    op: Operations, context: MigrationContext, conn: Connection
) -> None:
    if not _column_exists(conn, "cities", "responsible_recruiter_id"):
        return
    dialect_name = conn.dialect.name
    if dialect_name == "sqlite":
        with context.begin_transaction():
            with op.batch_alter_table("cities", recreate="always") as batch_op:
                batch_op.drop_column("responsible_recruiter_id")
    else:
        conn.execute(sa.text("ALTER TABLE cities DROP COLUMN responsible_recruiter_id"))


def upgrade(conn: Connection) -> None:
    op, context, standalone_conn = _get_operations(conn)
    table_exists = _table_exists(standalone_conn, TABLE_NAME)

    with context.begin_transaction():
        if not table_exists:
            op.create_table(
                TABLE_NAME,
                sa.Column("recruiter_id", sa.Integer(), nullable=False),
                sa.Column("city_id", sa.Integer(), nullable=False),
                sa.ForeignKeyConstraint(
                    ["recruiter_id"], ["recruiters.id"], ondelete="CASCADE"
                ),
                sa.ForeignKeyConstraint(["city_id"], ["cities.id"], ondelete="CASCADE"),
                sa.PrimaryKeyConstraint("recruiter_id", "city_id"),
                sa.UniqueConstraint("city_id", name="uq_recruiter_city_unique_city"),
            )
        else:
            # Ensure unique constraint exists even if table was created manually.
            inspector = inspect(standalone_conn)
            constraints = {
                uc["name"] for uc in inspector.get_unique_constraints(TABLE_NAME)
            }
            if "uq_recruiter_city_unique_city" not in constraints:
                op.create_unique_constraint(
                    "uq_recruiter_city_unique_city", TABLE_NAME, ["city_id"]
                )

    # Populate newly created links from legacy column.
    if _column_exists(standalone_conn, "cities", "responsible_recruiter_id"):
        for recruiter_id, city_id in _iter_city_links(standalone_conn):
            _insert_link(standalone_conn, recruiter_id, city_id)

    # Drop legacy column if present.
    _drop_city_owner_column(op, context, standalone_conn)


def downgrade(conn: Connection) -> None:  # pragma: no cover - legacy support
    if not _column_exists(conn, "cities", "responsible_recruiter_id"):
        conn.execute(
            sa.text("ALTER TABLE cities ADD COLUMN responsible_recruiter_id INTEGER")
        )

    if _table_exists(conn, TABLE_NAME):
        rows = conn.execute(sa.text("SELECT recruiter_id, city_id FROM recruiter_cities"))
        for recruiter_id, city_id in rows:
            conn.execute(
                sa.text(
                    "UPDATE cities SET responsible_recruiter_id = :rid WHERE id = :cid"
                ),
                {"rid": recruiter_id, "cid": city_id},
            )
        conn.execute(sa.text("DROP TABLE recruiter_cities"))
