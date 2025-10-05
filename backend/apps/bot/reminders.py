"""Reminder scheduling service backed by APScheduler."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo

from apscheduler.jobstores.base import JobLookupError
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.jobstores.redis import RedisJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from backend.apps.bot import templates
from backend.apps.bot.config import DEFAULT_TZ
from backend.apps.bot.keyboards import kb_attendance_confirm
from backend.core.db import async_session
from backend.domain.models import SlotReminderJob, SlotStatus
from backend.domain.repositories import get_slot

logger = logging.getLogger(__name__)


class ReminderKind(str, Enum):
    REMIND_24H = "remind_24h"
    REMIND_2H = "remind_2h"
    REMIND_1H = "remind_1h"
    CONFIRM_6H = "confirm_6h"


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

    async def schedule_for_slot(self, slot_id: int) -> None:
        async with self._lock:
            await self._cancel_jobs(slot_id)
            slot = await get_slot(slot_id)
            if not slot:
                return
            if slot.candidate_tg_id is None:
                return
            if (slot.status or "").lower() not in {
                SlotStatus.PENDING,
                SlotStatus.BOOKED,
            }:
                return

            reminders = self._build_schedule(
                slot.start_utc,
                slot.candidate_tz or DEFAULT_TZ,
            )
            if not reminders:
                return

            candidate_zone = _safe_zone(slot.candidate_tz)
            now_local = datetime.now(candidate_zone)

            async with async_session() as session:
                for kind, run_at_utc, run_at_local in reminders:
                    if run_at_local <= now_local:
                        await session.execute(
                            SlotReminderJob.__table__.delete().where(
                                SlotReminderJob.slot_id == slot_id,
                                SlotReminderJob.kind == kind.value,
                            )
                        )
                        await session.commit()
                        await self._execute_job(slot_id, kind)
                        continue
                    job_id = self._job_id(slot_id, kind)
                    self._scheduler.add_job(
                        self._execute_job,
                        "date",
                        run_date=_ensure_aware(run_at_utc),
                        id=job_id,
                        args=[slot_id, kind],
                        replace_existing=True,
                    )
                    await session.execute(
                        SlotReminderJob.__table__.delete().where(
                            SlotReminderJob.slot_id == slot_id,
                            SlotReminderJob.kind == kind.value,
                        )
                    )
                    await session.execute(
                        SlotReminderJob.__table__.insert().values(
                            slot_id=slot_id,
                            kind=kind.value,
                            job_id=job_id,
                            scheduled_at=_ensure_aware(run_at_utc),
                            created_at=datetime.now(timezone.utc),
                            updated_at=datetime.now(timezone.utc),
                        )
                    )
                await session.commit()

    async def cancel_for_slot(self, slot_id: int) -> None:
        async with self._lock:
            await self._cancel_jobs(slot_id)

    def stats(self) -> Dict[str, int]:
        jobs = self._scheduler.get_jobs()
        total = len(jobs)
        confirm = sum(
            1
            for job in jobs
            if job.id and job.id.endswith(ReminderKind.CONFIRM_6H.value)
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
            return
        status = (slot.status or "").lower()
        if status not in {SlotStatus.PENDING, SlotStatus.BOOKED}:
            return
        candidate_id = slot.candidate_tg_id
        if candidate_id is None:
            return

        tz = slot.candidate_tz or DEFAULT_TZ
        labels = _slot_local_labels(slot.start_utc, tz)
        try:
            from backend.apps.bot.services import get_bot  # type: ignore
        except Exception:
            logger.warning("Bot not configured; skipping reminder for slot %s", slot_id)
            return

        try:
            bot = get_bot()
        except Exception:
            logger.warning("Bot not configured; skipping reminder for slot %s", slot_id)
            return

        if kind == ReminderKind.CONFIRM_6H:
            text = await templates.tpl(
                getattr(slot, "candidate_city_id", None),
                "confirm_6h",
                candidate_fio=getattr(slot, "candidate_fio", "") or "",
                dt=_fmt_dt_local(slot.start_utc, tz),
                **labels,
            )
            try:
                await bot.send_message(
                    candidate_id,
                    text,
                    reply_markup=kb_attendance_confirm(slot_id),
                )
            except Exception:  # pragma: no cover - network errors
                logger.exception("Failed to send confirmation prompt")
            return

        template_key = {
            ReminderKind.REMIND_24H: "reminder_24h",
            ReminderKind.REMIND_2H: "reminder_2h",
            ReminderKind.REMIND_1H: "reminder_1h",
        }[kind]

        text = await templates.tpl(
            getattr(slot, "candidate_city_id", None),
            template_key,
            candidate_fio=getattr(slot, "candidate_fio", "") or "",
            dt=_fmt_dt_local(slot.start_utc, tz),
            **labels,
        )
        if not text:
            return
        try:
            await bot.send_message(candidate_id, text)
        except Exception:  # pragma: no cover - network errors
            logger.exception("Failed to send reminder %s for slot %s", kind, slot_id)

    def _build_schedule(
        self, start_utc: datetime, tz: Optional[str]
    ) -> List[tuple[ReminderKind, datetime, datetime]]:
        zone = _safe_zone(tz)
        start_local = start_utc.astimezone(zone)
        targets: List[tuple[ReminderKind, timedelta]] = [
            (ReminderKind.REMIND_24H, timedelta(hours=24)),
            (ReminderKind.CONFIRM_6H, timedelta(hours=6)),
            (ReminderKind.REMIND_2H, timedelta(hours=2)),
            (ReminderKind.REMIND_1H, timedelta(hours=1)),
        ]
        schedule: List[tuple[ReminderKind, datetime, datetime]] = []
        for kind, delta in targets:
            local_time = start_local - delta
            schedule.append((kind, local_time.astimezone(timezone.utc), local_time))
        return schedule

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
    try:
        return ZoneInfo(tz or DEFAULT_TZ)
    except Exception:  # pragma: no cover - invalid timezone fallback
        return ZoneInfo(DEFAULT_TZ)


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
