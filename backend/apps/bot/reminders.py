"""Reminder scheduling service backed by APScheduler."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from enum import Enum
from typing import Callable, Dict, List, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError, available_timezones

try:  # pragma: no cover - optional dependency handling
    from apscheduler.jobstores.base import JobLookupError
    from apscheduler.jobstores.memory import MemoryJobStore
    from apscheduler.jobstores.redis import RedisJobStore
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

    APSCHEDULER_AVAILABLE = True
except Exception:  # pragma: no cover - fallback when apscheduler is missing
    APSCHEDULER_AVAILABLE = False

    class JobLookupError(Exception):  # type: ignore[override]
        """Fallback error mirroring APScheduler's JobLookupError."""

        pass

    @dataclass
    class _StubJob:  # pragma: no cover - lightweight scheduler artefact
        id: str
        func: Optional[Callable[..., object]]
        args: List[object]
        next_run_time: Optional[datetime]

    class AsyncIOScheduler:  # type: ignore[override]
        """Minimal scheduler stub used when APScheduler is unavailable."""

        def __init__(self, *_, **__):
            self._jobs: Dict[str, _StubJob] = {}
            self.running = False

        def start(self) -> None:
            self.running = True

        def shutdown(self, wait: bool = False) -> None:  # pragma: no cover - trivial
            self.running = False
            self._jobs.clear()

        def add_job(
            self,
            func,
            trigger,
            *,
            run_date: Optional[datetime] = None,
            id: Optional[str] = None,
            args: Optional[List[object]] = None,
            replace_existing: bool = False,
            **_: object,
        ) -> _StubJob:
            if id is None:
                raise ValueError("Stub scheduler requires explicit job id")
            if not replace_existing and id in self._jobs:
                raise RuntimeError(f"Job {id} already exists")
            job = _StubJob(id=id, func=func, args=list(args or []), next_run_time=run_date)
            self._jobs[id] = job
            return job

        def remove_job(self, job_id: str) -> None:
            if job_id not in self._jobs:
                raise JobLookupError(job_id)
            self._jobs.pop(job_id, None)

        def get_job(self, job_id: str) -> Optional[_StubJob]:
            return self._jobs.get(job_id)

        def get_jobs(self) -> List[_StubJob]:
            return list(self._jobs.values())

    class MemoryJobStore:  # type: ignore[override]
        def __init__(self, *_, **__):
            return None

    class RedisJobStore:  # type: ignore[override]
        @classmethod
        def from_url(cls, *_args, **_kwargs):  # pragma: no cover - stub guard
            raise RuntimeError(
                "APScheduler with redis extra is required for Redis job store",
            )

from backend.apps.bot import templates
from backend.apps.bot.config import DEFAULT_TZ
from backend.apps.bot.keyboards import kb_attendance_confirm
from backend.core.db import async_session
from backend.domain.models import SlotReminderJob, SlotStatus
from backend.domain.repositories import get_slot

logger = logging.getLogger(__name__)


_DEFAULT_ZONE = ZoneInfo(DEFAULT_TZ)
_ZONE_ALIASES = {name.lower(): name for name in available_timezones()}
_ZONE_ALIASES.setdefault(DEFAULT_TZ.lower(), DEFAULT_TZ)


class ReminderKind(str, Enum):
    REMIND_24H = "remind_24h"
    REMIND_2H = "remind_2h"
    REMIND_1H = "remind_1h"
    CONFIRM_6H = "confirm_6h"
    CONFIRM_2H = "confirm_2h"


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

            reminders = self._build_schedule(
                slot.start_utc,
                slot.candidate_tz or DEFAULT_TZ,
            )
            if skip_confirmation_prompts:
                confirm_kinds = {
                    ReminderKind.CONFIRM_6H,
                    ReminderKind.CONFIRM_2H,
                    ReminderKind.REMIND_2H,
                }
                reminders = [
                    item for item in reminders if item[0] not in confirm_kinds
                ]
            if not reminders:
                return

            candidate_zone = _safe_zone(slot.candidate_tz)
            now_local = datetime.now(candidate_zone)

            async with async_session() as session:
                immediate: Dict[str, tuple[ReminderKind, datetime, datetime]] = {}
                future: List[tuple[ReminderKind, datetime, datetime]] = []

                for kind, run_at_utc, run_at_local in reminders:
                    if run_at_local <= now_local:
                        group = _immediate_group(kind)
                        current = immediate.get(group)
                        if current is None or run_at_local > current[2]:
                            immediate[group] = (kind, run_at_utc, run_at_local)
                    else:
                        future.append((kind, run_at_utc, run_at_local))

                for kind, run_at_utc, _run_at_local in sorted(
                    immediate.values(), key=lambda item: item[2]
                ):
                    await session.execute(
                        SlotReminderJob.__table__.delete().where(
                            SlotReminderJob.slot_id == slot_id,
                            SlotReminderJob.kind == kind.value,
                        )
                    )
                    await session.commit()
                    await self._execute_job(slot_id, kind)

                for kind, run_at_utc, _run_at_local in future:
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
        confirm_suffixes = {
            ReminderKind.CONFIRM_6H.value,
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
            return
        status = (slot.status or "").lower()
        if status not in {
            SlotStatus.PENDING,
            SlotStatus.BOOKED,
            SlotStatus.CONFIRMED_BY_CANDIDATE,
        }:
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

        confirm_templates = {
            ReminderKind.CONFIRM_6H: "confirm_6h",
            ReminderKind.CONFIRM_2H: "confirm_2h",
            # Historical jobs stored as ``remind_2h`` should now behave like confirmations.
            ReminderKind.REMIND_2H: "confirm_2h",
        }
        if kind in confirm_templates:
            text = await templates.tpl(
                getattr(slot, "candidate_city_id", None),
                confirm_templates[kind],
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
            (ReminderKind.CONFIRM_2H, timedelta(hours=2)),
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
    if not APSCHEDULER_AVAILABLE:
        if redis_url:
            logger.warning(
                "APScheduler is not installed; Redis job store is unavailable. Using stub scheduler.",
            )
        return AsyncIOScheduler()

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
        ReminderKind.CONFIRM_2H,
        ReminderKind.REMIND_2H,
    }:
        return "confirm"
    if kind in {
        ReminderKind.REMIND_24H,
        ReminderKind.REMIND_1H,
    }:
        return "reminder"
    return kind.value
