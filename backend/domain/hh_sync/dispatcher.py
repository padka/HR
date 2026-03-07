"""Dispatch hh.ru sync events to the outbox for processing via n8n."""

from __future__ import annotations

import logging
from typing import Optional, TYPE_CHECKING

from backend.domain.hh_sync.mapping import get_hh_target_status
from backend.domain.hh_sync.models import HHSyncLog

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
    from backend.domain.candidates.models import User
    from backend.domain.candidates.status import CandidateStatus

log = logging.getLogger(__name__)


async def dispatch_hh_status_sync(
    candidate: "User",
    new_status: "CandidateStatus",
    *,
    session: "AsyncSession",
) -> Optional[int]:
    """Create an outbox entry for hh.ru status synchronization.

    Only creates an entry if:
    - The candidate has an hh_negotiation_id (linked to hh.ru)
    - The new status maps to an hh.ru negotiation action

    Args:
        candidate: The User ORM instance.
        new_status: The new CandidateStatus being set.
        session: SQLAlchemy async session for writing outbox + audit log.

    Returns:
        The OutboxNotification.id if created, or None if no sync needed.
    """
    from backend.domain.models import OutboxNotification  # avoid circular import

    hh_target = get_hh_target_status(new_status)
    if hh_target is None:
        return None

    if not candidate.hh_negotiation_id:
        log.debug(
            "hh_sync: skipping candidate=%s (no hh_negotiation_id)",
            candidate.id,
        )
        return None

    # Skip if candidate was already synced to the same hh status
    if candidate.hh_sync_status == "synced":
        # Check if the last synced hh_status was already the same target
        # (e.g. INTERVIEW_SCHEDULED -> invitation, then INTERVIEW_CONFIRMED -> invitation)
        # We still sync to ensure hh.ru state is correct (idempotent PUT)
        pass

    payload = {
        "negotiation_id": candidate.hh_negotiation_id,
        "vacancy_id": candidate.hh_vacancy_id,
        "target_status": hh_target,
        "candidate_id": candidate.id,
        "rs_status": new_status.value,
        "candidate_name": candidate.fio,
    }

    outbox = OutboxNotification(
        type="hh_status_sync",
        payload_json=payload,
        status="pending",
    )
    session.add(outbox)

    # Audit log entry
    sync_log = HHSyncLog(
        candidate_id=candidate.id,
        event_type="status_sync",
        rs_status=new_status.value,
        hh_status=hh_target,
        request_payload=payload,
        status="pending",
    )
    session.add(sync_log)

    # Mark candidate sync as pending
    candidate.hh_sync_status = "pending"
    candidate.hh_sync_error = None

    await session.flush()

    log.info(
        "hh_sync: dispatched outbox=%s for candidate=%s status=%s->hh:%s",
        outbox.id,
        candidate.id,
        new_status.value,
        hh_target,
    )
    return outbox.id


__all__ = ["dispatch_hh_status_sync"]
