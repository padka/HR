from datetime import datetime, timedelta, timezone

from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from backend.apps.bot.reminders import ReminderKind, ReminderService


def _service() -> ReminderService:
    scheduler = AsyncIOScheduler(jobstores={"default": MemoryJobStore()}, timezone="UTC")
    return ReminderService(scheduler=scheduler)


def test_interview_schedule_contains_2h_3h_6h():
    svc = _service()
    start = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)
    plans = svc._build_schedule(start, "Europe/Moscow", "interview")
    kinds = {plan.kind for plan in plans}
    assert kinds == {
        ReminderKind.CONFIRM_6H,
        ReminderKind.CONFIRM_3H,
        ReminderKind.CONFIRM_2H,
    }
    assert any(plan.run_at_utc == start - timedelta(hours=2) for plan in plans)


def test_quiet_hours_adjustment_moves_to_previous_evening():
    svc = _service()
    # 06:00 local -> All reminders (6h→0:00, 3h→3:00, 2h→4:00) fall into quiet hours (22-08)
    # All get adjusted to 21:30 previous day, but duplicate prevention keeps only 6h
    start_local = datetime(2025, 1, 2, 6, 0, tzinfo=timezone(timedelta(hours=3)))
    start_utc = start_local.astimezone(timezone.utc)
    plans = svc._build_schedule(start_utc, "Europe/Moscow", "interview")

    # Duplicate prevention: only 6h reminder survives when all collide at 21:30
    assert len(plans) == 1
    six_hour_plan = plans[0]
    assert six_hour_plan.kind == ReminderKind.CONFIRM_6H
    # Quiet hours push to 21:30 previous day (22:00 - 30min grace)
    expected_local = start_local.replace(day=1, hour=21, minute=30)  # previous day
    assert six_hour_plan.run_at_local == expected_local
    assert six_hour_plan.adjusted_reason == "quiet_hours"
