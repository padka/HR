"""Per-city reminder policy service."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select

from backend.core.db import async_session
from backend.domain.models import CityReminderPolicy

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ReminderPolicyData:
    city_id: int
    confirm_6h_enabled: bool
    confirm_3h_enabled: bool
    confirm_2h_enabled: bool
    intro_remind_3h_enabled: bool
    quiet_hours_start: int
    quiet_hours_end: int
    is_custom: bool  # False = this is the global default, not a city override


GLOBAL_DEFAULTS = ReminderPolicyData(
    city_id=0,
    confirm_6h_enabled=True,
    confirm_3h_enabled=True,
    confirm_2h_enabled=True,
    intro_remind_3h_enabled=True,
    quiet_hours_start=22,
    quiet_hours_end=8,
    is_custom=False,
)


async def get_city_reminder_policy(city_id: int) -> ReminderPolicyData:
    """Return per-city policy if exists, otherwise return global defaults."""
    async with async_session() as session:
        row = await session.scalar(
            select(CityReminderPolicy).where(CityReminderPolicy.city_id == city_id)
        )
    if row is None:
        return GLOBAL_DEFAULTS
    return ReminderPolicyData(
        city_id=row.city_id,
        confirm_6h_enabled=row.confirm_6h_enabled,
        confirm_3h_enabled=row.confirm_3h_enabled,
        confirm_2h_enabled=row.confirm_2h_enabled,
        intro_remind_3h_enabled=row.intro_remind_3h_enabled,
        quiet_hours_start=row.quiet_hours_start,
        quiet_hours_end=row.quiet_hours_end,
        is_custom=True,
    )


async def upsert_city_reminder_policy(
    city_id: int,
    *,
    confirm_6h_enabled: bool = True,
    confirm_3h_enabled: bool = True,
    confirm_2h_enabled: bool = True,
    intro_remind_3h_enabled: bool = True,
    quiet_hours_start: int = 22,
    quiet_hours_end: int = 8,
) -> ReminderPolicyData:
    """Create or replace per-city reminder policy."""
    async with async_session() as session:
        row = await session.scalar(
            select(CityReminderPolicy).where(CityReminderPolicy.city_id == city_id)
        )
        if row is None:
            row = CityReminderPolicy(city_id=city_id)
            session.add(row)

        row.confirm_6h_enabled = confirm_6h_enabled
        row.confirm_3h_enabled = confirm_3h_enabled
        row.confirm_2h_enabled = confirm_2h_enabled
        row.intro_remind_3h_enabled = intro_remind_3h_enabled
        row.quiet_hours_start = max(0, min(23, quiet_hours_start))
        row.quiet_hours_end = max(0, min(23, quiet_hours_end))
        row.updated_at = datetime.now(timezone.utc)

        await session.commit()
        await session.refresh(row)

    return ReminderPolicyData(
        city_id=row.city_id,
        confirm_6h_enabled=row.confirm_6h_enabled,
        confirm_3h_enabled=row.confirm_3h_enabled,
        confirm_2h_enabled=row.confirm_2h_enabled,
        intro_remind_3h_enabled=row.intro_remind_3h_enabled,
        quiet_hours_start=row.quiet_hours_start,
        quiet_hours_end=row.quiet_hours_end,
        is_custom=True,
    )


async def delete_city_reminder_policy(city_id: int) -> bool:
    """Remove per-city override (resets to global defaults). Returns True if deleted."""
    async with async_session() as session:
        row = await session.scalar(
            select(CityReminderPolicy).where(CityReminderPolicy.city_id == city_id)
        )
        if row is None:
            return False
        await session.delete(row)
        await session.commit()
        return True
