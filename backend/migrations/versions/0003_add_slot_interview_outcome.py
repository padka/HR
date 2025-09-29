"""Add interview outcome to slots"""

revision = "0003_add_slot_interview_outcome"
down_revision = "0002_seed_defaults"
branch_labels = None
depends_on = None

def upgrade(conn) -> None:
    conn.exec_driver_sql("ALTER TABLE slots ADD COLUMN interview_outcome VARCHAR(20)")


def downgrade(conn) -> None:
    conn.exec_driver_sql("ALTER TABLE slots DROP COLUMN interview_outcome")

