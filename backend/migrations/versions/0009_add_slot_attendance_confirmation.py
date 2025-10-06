import sqlalchemy as sa
from sqlalchemy.engine import Connection


revision = "0009_add_slot_attendance_confirmation"
down_revision = "0008_add_slot_reminder_jobs"
branch_labels = None
depends_on = None


TABLE_NAME = "slots"
COLUMN_NAME = "attendance_confirmed_at"


def upgrade(conn: Connection) -> None:
    conn.execute(
        sa.text(
            f"ALTER TABLE {TABLE_NAME} ADD COLUMN {COLUMN_NAME} TIMESTAMP"
        )
    )


def downgrade(conn: Connection) -> None:  # pragma: no cover - symmetry only
    conn.execute(
        sa.text(
            f"ALTER TABLE {TABLE_NAME} DROP COLUMN {COLUMN_NAME}"
        )
    )
