"""Sync workflow_status from legacy candidate_status where NULL.

This migration populates workflow_status based on candidate_status values
for records that don't have workflow_status set. This helps unify the
dual status system.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.engine import Connection

from backend.migrations.utils import table_exists

revision = "0056_sync_workflow_status_from_legacy"
down_revision = "0055_add_performance_indexes"
branch_labels = None
depends_on = None


# Mapping from legacy candidate_status to new workflow_status
LEGACY_TO_WORKFLOW = {
    "waiting_slot": "waiting_for_slot",
    "stalled_waiting_slot": "waiting_for_slot",
    "interview_scheduled": "interview_scheduled",
    "interview_confirmed": "interview_confirmed",
    "interview_declined": "rejected",
    "test2_sent": "test_sent",
    "test2_completed": "onboarding_day_scheduled",
    "test2_failed": "rejected",
    "intro_day_scheduled": "onboarding_day_confirmed",
    "intro_day_confirmed_preliminary": "onboarding_day_confirmed",
    "intro_day_declined_invitation": "rejected",
    "intro_day_declined_day_of": "rejected",
    "hired": "onboarding_day_confirmed",
    "not_hired": "rejected",
}


def upgrade(conn: Connection) -> None:
    if not table_exists(conn, "users"):
        return

    # Update workflow_status based on candidate_status where workflow_status is NULL
    for legacy_status, workflow_status in LEGACY_TO_WORKFLOW.items():
        conn.execute(
            sa.text(
                """
                UPDATE users
                SET workflow_status = :workflow_status
                WHERE workflow_status IS NULL
                  AND candidate_status = :legacy_status
                """
            ),
            {"workflow_status": workflow_status, "legacy_status": legacy_status},
        )

    # For any remaining records without workflow_status, set default
    conn.execute(
        sa.text(
            """
            UPDATE users
            SET workflow_status = 'waiting_for_slot'
            WHERE workflow_status IS NULL
              AND candidate_status IS NOT NULL
            """
        )
    )


def downgrade(conn: Connection) -> None:  # pragma: no cover
    # We don't clear workflow_status on downgrade as it may have been set
    # through the new workflow system independently
    pass
