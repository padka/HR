"""Add interview outcome to slots"""

from alembic import op
import sqlalchemy as sa


revision = "0003_add_slot_interview_outcome"
down_revision = "0002_seed_defaults"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "slots",
        sa.Column("interview_outcome", sa.String(length=20), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("slots", "interview_outcome")

