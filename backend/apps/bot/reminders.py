"""Reminder scheduling service backed by APScheduler."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from enum import Enum
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError, available_timezones

from apscheduler.jobstores.base import JobLookupError
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.jobstores.redis import RedisJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from backend.apps.bot import templates
from backend.apps.bot.config import DEFAULT_TZ
from backend.apps.bot.keyboards import kb_attendance_confirm
from backend.apps.bot.metrics import (
    record_reminder_executed,
    record_reminder_scheduled,
    record_reminder_skipped,
)
from backend.core.db import async_session
from backend.domain.models import SlotReminderJob, SlotStatus
from backend.domain.repositories import add_outbox_notification, get_slot

logger = logging.getLogger(__name__)


_DEFAULT_ZONE = ZoneInfo(DEFAULT_TZ)
_ZONE_ALIASES = {name.lower(): name for name in available_timezones()}
_ZONE_ALIASES.setdefault(DEFAULT_TZ.lower(), DEFAULT_TZ)

_QUIET_HOURS_START = 22  # 22:00 local time
_QUIET_HOURS_END = 8     # 08:00 local time
_QUIET_GRACE = timedelta(minutes=1)


class ReminderKind(str, Enum):
    REMIND_24H = "remind_24h"
    REMIND_2H = "remind_2h"
    REMIND_1H = "remind_1h"
    CONFIRM_6H = "confirm_6h"
    CONFIRM_3H = "confirm_3h"
    CONFIRM_2H = "confirm_2h"


@dataclass(frozen=True)
class ReminderPlan:
    kind: ReminderKind
    run_at_utc: datetime
    run_at_local: datetime
    adjusted_reason: Optional[str] = None


class ReminderService:
    """Centralised reminder orchestration built on APScheduler."""

    def __init__(
        self,
        *,
        scheduler: AsyncIOScheduler,
    ) -> None:
        self._scheduler = scheduler
        self._lock = asyncio.Lock()

    def start(self) -> None:
        if not self._scheduler.running:
            self._scheduler.start()

    async def shutdown(self) -> None:
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)

    async def sync_jobs(self) -> None:
        """Ensure persisted jobs exist in the scheduler."""

        async with async_session() as session:
            result = await session.execute(SlotReminderJob.__table__.select())

        for row in result:
            job_id = row.job_id
            try:
                kind = ReminderKind(row.kind)
            except ValueError:
                logger.warning(
                    "Removing unknown reminder kind '%s' for slot %s", row.kind, row.slot_id
                )
                async with async_session() as session:
                    await session.execute(
                        SlotReminderJob.__table__.delete().where(
                            SlotReminderJob.job_id == job_id
                        )
                    )
                    await session.commit()
                continue
            if kind is ReminderKind.REMIND_1H:
                logger.info(
                    "reminder.schedule.skip",
                    extra={"slot_id": row.slot_id, "kind": row.kind, "reason": "disabled"},
                )
                async with async_session() as session:
                    await session.execute(
                        SlotReminderJob.__table__.delete().where(
                            SlotReminderJob.job_id == job_id
                        )
                    )
                    await session.commit()
                continue
            if self._scheduler.get_job(job_id) is None:
                run_at = _ensure_aware(row.scheduled_at)
                if run_at <= datetime.now(timezone.utc):
                    continue
                self._scheduler.add_job(
                    self._execute_job,
                    "date",
                    run_date=run_at,
                    id=job_id,
                    args=[row.slot_id, kind],
                    replace_existing=True,
                )

    async def schedule_for_slot(
        self, slot_id: int, *, skip_confirmation_prompts: bool = False
    ) -> None:
        async with self._lock:
            await self._cancel_jobs(slot_id)
            slot = await get_slot(slot_id)
            if not slot:
                return
            if slot.candidate_tg_id is None:
                return
            if (slot.status or "").lower() not in {
                SlotStatus.BOOKED,
                SlotStatus.CONFIRMED_BY_CANDIDATE,
            }:
                return

            plans = self._build_schedule(
                slot.start_utc,
                slot.candidate_tz or DEFAULT_TZ,
            )
            if skip_confirmation_prompts:
                confirm_kinds = {
                    ReminderKind.CONFIRM_6H,
                    ReminderKind.CONFIRM_3H,
                    ReminderKind.CONFIRM_2H,
                    ReminderKind.REMIND_2H,
                }
                plans = [plan for plan in plans if plan.kind not in confirm_kinds]
            if not plans:
                logger.info(
                    "reminder.schedule.empty",
                    extra={"slot_id": slot_id, "reason": "no_plans"},
                )
                return

            candidate_zone = _safe_zone(slot.candidate_tz)
            now_local = datetime.now(candidate_zone)

            immediate_map: Dict[str, ReminderPlan] = {}
            future_plans: List[ReminderPlan] = []

            for plan in plans:
                if plan.run_at_local <= now_local:
                    group = _immediate_group(plan.kind)
                    current = immediate_map.get(group)
                    if current is None or plan.run_at_local > current.run_at_local:
                        immediate_map[group] = plan
                else:
                    future_plans.append(plan)

            async with async_session() as session:
                for plan in sorted(immediate_map.values(), key=lambda item: item.run_at_local):
                    await record_reminder_scheduled(
                        plan.kind,
                        immediate=True,
                        adjusted=plan.adjusted_reason is not None,
                    )
                    await session.execute(
                        SlotReminderJob.__table__.delete().where(
                            SlotReminderJob.slot_id == slot_id,
                            SlotReminderJob.kind == plan.kind.value,
                        )
                    )
                    await session.commit()
                    logger.info(
                        "reminder.dispatch.immediate",
                        extra={
                            "slot_id": slot_id,
                            "kind": plan.kind.value,
                            "run_at_local": plan.run_at_local.isoformat(),
                            "adjusted": plan.adjusted_reason or "",
                        },
                    )
                    await self._execute_job(slot_id, plan.kind)

                for plan in sorted(future_plans, key=lambda item: item.run_at_local):
                    await record_reminder_scheduled(
                        plan.kind,
                        immediate=False,
                        adjusted=plan.adjusted_reason is not None,
                    )
                    job_id = self._job_id(slot_id, plan.kind)
                    self._scheduler.add_job(
                        self._execute_job,
                        "date",
                        run_date=_ensure_aware(plan.run_at_utc),
                        id=job_id,
                        args=[slot_id, plan.kind],
                        replace_existing=True,
                    )
                    await session.execute(
                        SlotReminderJob.__table__.delete().where(
                            SlotReminderJob.slot_id == slot_id,
                            SlotReminderJob.kind == plan.kind.value,
                        )
                    )
                    await session.execute(
                        SlotReminderJob.__table__.insert().values(
                            slot_id=slot_id,
                            kind=plan.kind.value,
                            job_id=job_id,
                            scheduled_at=_ensure_aware(plan.run_at_utc),
                            created_at=datetime.now(timezone.utc),
                            updated_at=datetime.now(timezone.utc),
                        )
                    )
                    logger.info(
                        "reminder.dispatch.scheduled",
                        extra={
                            "slot_id": slot_id,
                            "kind": plan.kind.value,
                            "run_at_local": plan.run_at_local.isoformat(),
                            "run_at_utc": plan.run_at_utc.isoformat(),
                            "adjusted": plan.adjusted_reason or "",
                            "job_id": job_id,
                        },
                    )
                await session.commit()

    async def cancel_for_slot(self, slot_id: int) -> None:
        async with self._lock:
            await self._cancel_jobs(slot_id)

    def stats(self) -> Dict[str, int]:
        jobs = self._scheduler.get_jobs()
        total = len(jobs)
        confirm_suffixes = {
            ReminderKind.CONFIRM_6H.value,
            ReminderKind.CONFIRM_3H.value,
            ReminderKind.CONFIRM_2H.value,
        }
        confirm = sum(
            1
            for job in jobs
            if job.id and any(job.id.endswith(suffix) for suffix in confirm_suffixes)
        )
        return {
            "total": total,
            "confirm_prompts": confirm,
            "reminders": total - confirm,
        }

    async def _cancel_jobs(self, slot_id: int) -> None:
        async with async_session() as session:
            result = await session.execute(
                SlotReminderJob.__table__.select().where(
                    SlotReminderJob.slot_id == slot_id
                )
            )
            job_ids = [row.job_id for row in result]
            if job_ids:
                await session.execute(
                    SlotReminderJob.__table__.delete().where(
                        SlotReminderJob.slot_id == slot_id
                    )
                )
                await session.commit()
            for job_id in job_ids:
                try:
                    self._scheduler.remove_job(job_id)
                except JobLookupError:
                    continue

    async def _execute_job(self, slot_id: int, kind: ReminderKind) -> None:
        async with async_session() as session:
            await session.execute(
                SlotReminderJob.__table__.delete().where(
                    SlotReminderJob.slot_id == slot_id,
                    SlotReminderJob.kind == kind.value,
                )
            )
            await session.commit()

        slot = await get_slot(slot_id)
        if not slot:
            await record_reminder_skipped(kind, "slot_missing")
            logger.info(
                "reminder.job.skip",
                extra={"slot_id": slot_id, "kind": kind.value, "reason": "slot_missing"},
            )
            return
        status = (slot.status or "").lower()
        if status not in {
            SlotStatus.PENDING,
            SlotStatus.BOOKED,
            SlotStatus.CONFIRMED_BY_CANDIDATE,
        }:
            await record_reminder_skipped(kind, "status_invalid")
            logger.info(
                "reminder.job.skip",
                extra={
                    "slot_id": slot_id,
                    "kind": kind.value,
                    "reason": f"status:{status}",
                },
            )
            return
        candidate_id = slot.candidate_tg_id
        if candidate_id is None:
            await record_reminder_skipped(kind, "candidate_missing")
            logger.info(
                "reminder.job.skip",
                extra={
                    "slot_id": slot_id,
                    "kind": kind.value,
                    "reason": "candidate_missing",
                },
            )
            return

        if kind is ReminderKind.REMIND_1H:
            await record_reminder_skipped(kind, "disabled")
            logger.info(
                "reminder.job.skip",
                extra={"slot_id": slot_id, "kind": kind.value, "reason": "disabled"},
            )
            return

        reminder_kind = kind.value
        try:  # defer import to avoid circular dependency during module load
            from backend.apps.bot.services import get_notification_service
        except Exception:
            await record_reminder_skipped(kind, "service_import_error")
            logger.warning("Notification service missing; skipping reminder for slot %s", slot_id)
            return

        try:
            notification_service = get_notification_service()
        except RuntimeError:
            await record_reminder_skipped(kind, "service_unconfigured")
            logger.warning("Notification service not configured; skipping reminder for slot %s", slot_id)
            return

        try:
            outbox_entry = await add_outbox_notification(
                notification_type="slot_reminder",
                booking_id=slot_id,
                candidate_tg_id=candidate_id,
                payload={"reminder_kind": reminder_kind},
            )
            enqueued = await notification_service._enqueue_outbox(
                outbox_entry.id,
                attempt=outbox_entry.attempts,
            )
            if enqueued:
                await record_reminder_executed(kind)
                logger.info(
                    "reminder.job.enqueued",
                    extra={
                        "slot_id": slot_id,
                        "kind": reminder_kind,
                        "outbox_id": outbox_entry.id,
                    },
                )
            else:
                await record_reminder_skipped(kind, "enqueue_failed")
                logger.warning(
                    "Reminder enqueue failed for slot %s",
                    slot_id,
                    extra={"slot_id": slot_id, "kind": reminder_kind},
                )
        except Exception:
            await record_reminder_skipped(kind, "enqueue_exception")
            logger.exception("Failed to enqueue reminder for slot %s", slot_id)

    def _build_schedule(self, start_utc: datetime, tz: Optional[str]) -> List[ReminderPlan]:
        zone = _safe_zone(tz)
        start_local = start_utc.astimezone(zone)
        targets: List[tuple[ReminderKind, timedelta]] = [
            (ReminderKind.REMIND_24H, timedelta(hours=24)),
            (ReminderKind.CONFIRM_6H, timedelta(hours=6)),
            (ReminderKind.CONFIRM_3H, timedelta(hours=3)),
            (ReminderKind.CONFIRM_2H, timedelta(hours=2)),
        ]
        plans: List[ReminderPlan] = []
        seen: set[ReminderKind] = set()
        for kind, delta in targets:
            if kind in seen:
                continue
            seen.add(kind)
            local_time = start_local - delta
            adjusted_local, reason = _apply_quiet_hours(local_time)
            run_at_utc = adjusted_local.astimezone(timezone.utc)
            plans.append(
                ReminderPlan(
                    kind=kind,
                    run_at_utc=run_at_utc,
                    run_at_local=adjusted_local,
                    adjusted_reason=reason,
                )
            )
        plans.sort(key=lambda plan: plan.run_at_local)
        return plans

    def _job_id(self, slot_id: int, kind: ReminderKind) -> str:
        return f"slot:{slot_id}:{kind.value}"


_reminder_service: Optional[ReminderService] = None


def configure_reminder_service(service: ReminderService) -> None:
    global _reminder_service
    _reminder_service = service
    service.start()


def get_reminder_service() -> ReminderService:
    if _reminder_service is None:
        raise RuntimeError("Reminder service is not configured")
    return _reminder_service


def create_scheduler(redis_url: Optional[str]) -> AsyncIOScheduler:
    if redis_url:
        jobstores = {"default": RedisJobStore.from_url(redis_url)}
    else:
        jobstores = {"default": MemoryJobStore()}
    return AsyncIOScheduler(jobstores=jobstores, timezone="UTC")


__all__ = [
    "ReminderService",
    "ReminderKind",
    "configure_reminder_service",
    "get_reminder_service",
    "create_scheduler",
]


def _safe_zone(tz: Optional[str]) -> ZoneInfo:
    if not tz:
        return _DEFAULT_ZONE
    return _resolve_zone(tz)


def _in_quiet_hours(local_dt: datetime) -> bool:
    if _QUIET_HOURS_START == _QUIET_HOURS_END:
        return False
    start_hour = _QUIET_HOURS_START % 24
    end_hour = _QUIET_HOURS_END % 24
    minutes = local_dt.hour * 60 + local_dt.minute
    start_minutes = start_hour * 60
    end_minutes = end_hour * 60
    if start_minutes < end_minutes:
        return start_minutes <= minutes < end_minutes
    return minutes >= start_minutes or minutes < end_minutes


def _apply_quiet_hours(local_dt: datetime) -> tuple[datetime, Optional[str]]:
    if _QUIET_HOURS_START == _QUIET_HOURS_END:
        return local_dt, None
    if not _in_quiet_hours(local_dt):
        return local_dt, None

    start_hour = _QUIET_HOURS_START % 24
    end_hour = _QUIET_HOURS_END % 24
    boundary = local_dt.replace(
        hour=start_hour,
        minute=0,
        second=0,
        microsecond=0,
    )
    if _QUIET_HOURS_START > _QUIET_HOURS_END:
        if local_dt.hour > start_hour or (
            local_dt.hour == start_hour and local_dt.minute >= 0
        ):
            adjusted = boundary - _QUIET_GRACE
        else:
            adjusted = (boundary - timedelta(days=1)) - _QUIET_GRACE
    else:
        adjusted = boundary - _QUIET_GRACE
    return adjusted, "quiet_hours"


@lru_cache(maxsize=None)
def _resolve_zone(label: str) -> ZoneInfo:
    cleaned = label.strip()
    if not cleaned:
        return _DEFAULT_ZONE

    candidates = []
    seen: set[str] = set()

    def add(value: Optional[str]) -> None:
        if not value:
            return
        if value not in seen:
            seen.add(value)
            candidates.append(value)

    add(cleaned)
    add(cleaned.replace(" ", ""))
    add(cleaned.replace(" ", "_"))
    add(cleaned.replace("-", "_"))
    if "/" in cleaned:
        parts = cleaned.split("/")
        add("/".join(part.capitalize() for part in parts))
        add("/".join(part.title() for part in parts))

    add(cleaned.title())
    add(cleaned.upper())
    add(cleaned.lower())

    for candidate in list(candidates):
        canonical = _ZONE_ALIASES.get(candidate.lower())
        if canonical:
            add(canonical)

    for candidate in candidates:
        lookup = _ZONE_ALIASES.get(candidate.lower())
        target = lookup or candidate
        try:
            return ZoneInfo(target)
        except ZoneInfoNotFoundError:
            continue
    return _DEFAULT_ZONE


def _slot_local_labels(dt_utc: datetime, tz: str) -> Dict[str, str]:
    local_dt = dt_utc.astimezone(_safe_zone(tz))
    return {
        "slot_date_local": local_dt.strftime("%d.%m"),
        "slot_time_local": local_dt.strftime("%H:%M"),
        "slot_datetime_local": local_dt.strftime("%d.%m %H:%M"),
    }


def _fmt_dt_local(dt_utc: datetime, tz: str) -> str:
    return dt_utc.astimezone(_safe_zone(tz)).strftime("%d.%m %H:%M")


def _ensure_aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _immediate_group(kind: ReminderKind) -> str:
    if kind in {
        ReminderKind.CONFIRM_6H,
        ReminderKind.CONFIRM_3H,
        ReminderKind.CONFIRM_2H,
        ReminderKind.REMIND_2H,
    }:
        return "confirm"
    if kind in {
        ReminderKind.REMIND_24H,
    }:
        return "reminder"
    return kind.value
