from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import backend.apps.bot.services.base as bot_base_module
import pytest
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from backend.apps.admin_ui.services.notifications_ops import retry_outbox_notification
from backend.apps.bot.broker import BrokerMessage, InMemoryNotificationBroker
from backend.apps.bot.reminders import ReminderKind, ReminderService
from backend.apps.bot.services import NotificationService, reset_template_provider
from backend.apps.bot.services.base import BookingNotificationStatus
from backend.apps.bot.services.slot_flow import capture_slot_snapshot
from backend.core.db import async_session
from backend.core.messenger.channel_state import (
    get_messenger_channel_health,
    mark_messenger_channel_healthy,
    set_messenger_channel_degraded,
)
from backend.core.messenger.protocol import MessengerPlatform, MessengerProtocol
from backend.core.messenger.registry import MessengerRegistry
from backend.domain.candidates.models import User
from backend.domain.candidates.status import CandidateStatus
from backend.domain.models import (
    MessageTemplate,
    NotificationLog,
    OutboxNotification,
    Recruiter,
    Slot,
    SlotStatus,
)
from backend.domain.repositories import (
    OutboxItem,
    add_outbox_notification,
    claim_outbox_batch,
)
from sqlalchemy import delete, select


@pytest.fixture(autouse=True)
def _reset_messenger_registry():
    import backend.core.messenger.registry as registry_module

    previous = registry_module._registry
    registry_module._registry = MessengerRegistry()
    yield
    registry_module._registry = previous


@pytest.fixture(autouse=True)
def _reset_notification_templates():
    reset_template_provider()
    yield
    reset_template_provider()


class _RecordingMaxAdapter(MessengerProtocol):
    platform = MessengerPlatform.MAX

    def __init__(self) -> None:
        self.messages: list[tuple[int | str, str]] = []

    async def configure(self, **kwargs):
        return None

    async def send_message(
        self,
        chat_id,
        text,
        *,
        buttons=None,
        parse_mode=None,
        correlation_id=None,
    ):
        del buttons, parse_mode, correlation_id
        self.messages.append((chat_id, text))
        return SimpleNamespace(success=True, message_id="max-message-1", error=None)


async def _seed_max_rejection_case(*, telegram_id: int | None) -> dict[str, int | str | None]:
    async with async_session() as session:
        recruiter = Recruiter(name="MAX Reject Recruiter", tz="Europe/Moscow", active=True)
        session.add(recruiter)
        await session.flush()

        candidate = User(
            fio="MAX Reject Candidate",
            city="Москва",
            source="max",
            messenger_platform="max",
            max_user_id=f"max-user-{telegram_id or 1}",
            telegram_id=telegram_id,
            telegram_user_id=telegram_id,
            candidate_status=CandidateStatus.WAITING_SLOT,
        )
        session.add(candidate)
        await session.flush()

        slot = Slot(
            recruiter_id=recruiter.id,
            city_id=None,
            candidate_city_id=None,
            purpose="interview",
            tz_name="Europe/Moscow",
            start_utc=datetime.now(UTC) + timedelta(hours=3),
            duration_min=60,
            status=SlotStatus.BOOKED,
            candidate_id=candidate.candidate_id,
            candidate_tg_id=telegram_id,
            candidate_fio=candidate.fio,
            candidate_tz="Europe/Moscow",
        )
        session.add(slot)
        await session.commit()
        await session.refresh(slot)

        return {
            "candidate_id": candidate.candidate_id,
            "candidate_pk": candidate.id,
            "telegram_id": telegram_id,
            "max_user_id": candidate.max_user_id,
            "slot_id": slot.id,
        }


async def _ensure_candidate_rejection_template() -> None:
    async with async_session() as session:
        await session.execute(
            delete(MessageTemplate).where(
                MessageTemplate.key == "candidate_rejection",
                MessageTemplate.locale == "ru",
                MessageTemplate.channel == "tg",
            )
        )
        session.add(
            MessageTemplate(
                key="candidate_rejection",
                locale="ru",
                channel="tg",
                body_md="Спасибо за время, которое вы уделили интервью.",
                version=1,
                is_active=True,
                updated_at=datetime.now(UTC),
            )
        )
        await session.commit()
    reset_template_provider()


async def _seed_max_delivery_slot(*, purpose: str = "interview") -> dict[str, int | str]:
    async with async_session() as session:
        recruiter = Recruiter(name="MAX Reminder Recruiter", tz="Europe/Moscow", active=True)
        session.add(recruiter)
        await session.flush()

        candidate = User(
            fio="MAX Reminder Candidate",
            city="Москва",
            source="max",
            messenger_platform="max",
            max_user_id="max-reminder-user",
            telegram_id=None,
            telegram_user_id=None,
            candidate_status=(
                CandidateStatus.INTRO_DAY_SCHEDULED if purpose == "intro_day" else CandidateStatus.INTERVIEW_SCHEDULED
            ),
        )
        session.add(candidate)
        await session.flush()

        slot = Slot(
            recruiter_id=recruiter.id,
            city_id=None,
            candidate_city_id=None,
            purpose=purpose,
            tz_name="Europe/Moscow",
            start_utc=datetime.now(UTC) + timedelta(hours=3),
            duration_min=60,
            status=SlotStatus.BOOKED,
            candidate_id=candidate.candidate_id,
            candidate_tg_id=None,
            candidate_fio=candidate.fio,
            candidate_tz="Europe/Moscow",
            intro_address="ул. Пример, 1" if purpose == "intro_day" else None,
            intro_contact="Ирина, +7 999 000-00-00" if purpose == "intro_day" else None,
        )
        session.add(slot)
        await session.commit()
        await session.refresh(slot)
        return {
            "slot_id": int(slot.id),
            "candidate_public_id": str(candidate.candidate_id),
            "candidate_pk": int(candidate.id),
            "max_user_id": str(candidate.max_user_id),
        }


@pytest.mark.asyncio
async def test_retry_marks_failed_when_exceeds_max_attempts():
    now = datetime.now(UTC) + timedelta(hours=4)
    async with async_session() as session:
        recruiter = Recruiter(name="Notif Rec", tg_chat_id=987654321, tz="Europe/Moscow", active=True)
        session.add(recruiter)
        await session.flush()
        slot = Slot(
            recruiter_id=recruiter.id,
            city_id=None,
            candidate_city_id=None,
            purpose="interview",
            tz_name="Europe/Moscow",
            start_utc=now,
            duration_min=60,
            status=SlotStatus.BOOKED,
            candidate_tg_id=777001,
            candidate_fio="Notif User",
        )
        session.add(slot)
        await session.commit()

    entry = await add_outbox_notification(
        notification_type="slot_reminder",
        booking_id=slot.id,
        candidate_tg_id=slot.candidate_tg_id,
        payload={"msg": "hi"},
    )
    item = OutboxItem(
        id=entry.id,
        booking_id=entry.booking_id,
        type=entry.type,
        payload=entry.payload_json or {},
        candidate_tg_id=entry.candidate_tg_id,
        recruiter_tg_id=entry.recruiter_tg_id,
        attempts=entry.attempts,
        created_at=entry.created_at,
    )

    service = NotificationService(
        scheduler=AsyncIOScheduler(jobstores={"default": MemoryJobStore()}, timezone="UTC"),
        broker=InMemoryNotificationBroker(),
        max_attempts=1,
    )
    service._current_message = BrokerMessage(id="msg-1", payload={"attempt": 1, "max_attempts": 1})

    await service._schedule_retry(
        item,
        attempt=1,
        log_type="slot_reminder",
        notification_type="slot_reminder",
        error="boom",
        rendered=None,
        candidate_tg_id=slot.candidate_tg_id,
    )

    async with async_session() as session:
        log = await session.scalar(select(NotificationLog).where(NotificationLog.booking_id == slot.id))
    assert log is not None
    assert log.last_error is not None


@pytest.mark.asyncio
async def test_claim_outbox_batch_skips_degraded_channels():
    telegram_entry = await add_outbox_notification(
        notification_type="slot_reminder",
        booking_id=None,
        candidate_tg_id=7001,
        payload={"msg": "telegram"},
        messenger_channel="telegram",
    )
    second_entry = await add_outbox_notification(
        notification_type="slot_reminder",
        booking_id=None,
        candidate_tg_id=7002,
        payload={"msg": "telegram-2"},
        messenger_channel="telegram",
    )

    try:
        await set_messenger_channel_degraded("telegram", reason="telegram:invalid_token")
        claimed = await claim_outbox_batch(batch_size=10)

        claimed_ids = {item.id for item in claimed}
        assert telegram_entry.id not in claimed_ids
        assert second_entry.id not in claimed_ids
    finally:
        await mark_messenger_channel_healthy("telegram")


@pytest.mark.asyncio
async def test_retry_outbox_notification_requeues_dead_letter_and_keeps_channel_degraded():
    entry = await add_outbox_notification(
        notification_type="slot_reminder",
        booking_id=None,
        candidate_tg_id=7101,
        payload={"msg": "telegram"},
        messenger_channel="telegram",
    )

    async with async_session() as session:
        stored = await session.get(OutboxNotification, entry.id)
        assert stored is not None
        stored.status = "dead_letter"
        stored.attempts = 3
        stored.last_error = "invalid token"
        stored.failure_class = "misconfiguration"
        stored.failure_code = "invalid_token"
        stored.provider_message_id = "provider-1"
        stored.dead_lettered_at = datetime.now(UTC)
        await session.commit()

    await set_messenger_channel_degraded("telegram", reason="telegram:invalid_token")

    ok, reason = await retry_outbox_notification(entry.id)
    assert ok is True
    assert reason is None

    async with async_session() as session:
        refreshed = await session.get(OutboxNotification, entry.id)

    assert refreshed is not None
    assert refreshed.status == "pending"
    assert refreshed.attempts == 0
    assert refreshed.last_error is None
    assert refreshed.failure_class is None
    assert refreshed.failure_code is None
    assert refreshed.provider_message_id is None
    assert refreshed.dead_lettered_at is None

    channel_health = await get_messenger_channel_health()
    assert channel_health["telegram"]["status"] == "degraded"


@pytest.mark.asyncio
@pytest.mark.parametrize("telegram_id", [None, 880022])
async def test_reject_slot_routes_max_rejection_for_pure_and_mixed_identity_candidates(
    telegram_id: int | None,
):
    seeded = await _seed_max_rejection_case(telegram_id=telegram_id)
    await _ensure_candidate_rejection_template()
    adapter = _RecordingMaxAdapter()
    broker = InMemoryNotificationBroker()
    await broker.start()

    import backend.core.messenger.registry as registry_module

    registry_module.get_registry().register(adapter)

    async with async_session() as session:
        slot = await session.get(Slot, int(seeded["slot_id"]))
        assert slot is not None
        snapshot = await capture_slot_snapshot(slot)

    service = NotificationService(
        broker=broker,
        poll_interval=0.05,
        rate_limit_per_sec=10,
    )
    result = await service.on_booking_status_changed(
        int(seeded["slot_id"]),
        BookingNotificationStatus.CANCELLED,
        snapshot=snapshot,
    )
    assert result.status == "queued"

    await service._poll_once()

    async with async_session() as session:
        outbox = await session.scalar(
            select(OutboxNotification)
            .where(OutboxNotification.booking_id == int(seeded["slot_id"]))
            .where(OutboxNotification.type == "candidate_rejection")
        )
        candidate = await session.scalar(
            select(User).where(User.candidate_id == str(seeded["candidate_id"]))
        )

    assert outbox is not None
    assert outbox.messenger_channel == "max"
    assert outbox.candidate_tg_id == telegram_id
    assert outbox.payload_json is not None
    assert outbox.payload_json["candidate_external_id"] == seeded["max_user_id"]
    assert outbox.payload_json["snapshot"]["candidate_external_id"] == seeded["max_user_id"]
    assert outbox.payload_json["snapshot"]["candidate_fio"] == "MAX Reject Candidate"
    if telegram_id is None:
        assert outbox.payload_json["snapshot"]["candidate_id"] is None
    else:
        assert outbox.payload_json["snapshot"]["candidate_id"] == telegram_id
    assert candidate is not None
    assert len(adapter.messages) == 1
    assert adapter.messages[0][0] == seeded["max_user_id"]

    async with async_session() as session:
        sent = await session.scalar(
            select(OutboxNotification)
            .where(OutboxNotification.booking_id == int(seeded["slot_id"]))
            .where(OutboxNotification.type == "candidate_rejection")
        )
    assert sent is not None
    assert sent.status == "sent"
    await broker.close()


@pytest.mark.asyncio
async def test_reject_slot_direct_fallback_uses_max_adapter_without_telegram_identity(
    monkeypatch: pytest.MonkeyPatch,
):
    seeded = await _seed_max_rejection_case(telegram_id=None)
    await _ensure_candidate_rejection_template()
    adapter = _RecordingMaxAdapter()

    async def _fake_ensure_max_adapter(*, settings=None):
        del settings
        return adapter

    monkeypatch.setattr(bot_base_module, "ensure_max_adapter", _fake_ensure_max_adapter)

    async with async_session() as session:
        slot = await session.get(Slot, int(seeded["slot_id"]))
        assert slot is not None
        snapshot = await capture_slot_snapshot(slot)

    service = NotificationService(
        broker=None,
        poll_interval=0.05,
        rate_limit_per_sec=10,
    )
    result = await service.on_booking_status_changed(
        int(seeded["slot_id"]),
        BookingNotificationStatus.CANCELLED,
        snapshot=snapshot,
    )

    assert result.status == "sent"
    assert len(adapter.messages) == 1
    assert adapter.messages[0][0] == seeded["max_user_id"]

    async with async_session() as session:
        outbox = await session.scalar(
            select(OutboxNotification)
            .where(OutboxNotification.booking_id == int(seeded["slot_id"]))
            .where(OutboxNotification.type == "candidate_rejection")
        )

    assert outbox is not None
    assert outbox.messenger_channel == "max"
    assert outbox.status == "sent"


@pytest.mark.asyncio
async def test_schedule_for_slot_queues_max_reminder_without_telegram_identity():
    seeded = await _seed_max_delivery_slot(purpose="interview")
    broker = InMemoryNotificationBroker()
    await broker.start()
    notification_service = NotificationService(
        broker=broker,
        poll_interval=0.05,
        rate_limit_per_sec=10,
    )
    import backend.apps.bot.services as services_module

    service = ReminderService(
        scheduler=AsyncIOScheduler(jobstores={"default": MemoryJobStore()}, timezone="UTC"),
    )
    services_module.get_notification_service = lambda: notification_service

    await service._execute_job(int(seeded["slot_id"]), ReminderKind.CONFIRM_2H)

    async with async_session() as session:
        outbox = await session.scalar(
            select(OutboxNotification)
            .where(OutboxNotification.booking_id == int(seeded["slot_id"]))
            .where(OutboxNotification.type.in_(["slot_reminder", "interview_reminder_2h"]))
            .order_by(OutboxNotification.id.desc())
        )

    assert outbox is not None
    assert outbox.messenger_channel == "max"
    assert outbox.candidate_tg_id is None
    assert outbox.payload_json is not None
    assert outbox.payload_json["candidate_external_id"] == seeded["max_user_id"]
    await broker.close()


@pytest.mark.asyncio
async def test_intro_day_invitation_uses_max_adapter_without_telegram_identity():
    seeded = await _seed_max_delivery_slot(purpose="intro_day")
    adapter = _RecordingMaxAdapter()

    import backend.core.messenger.registry as registry_module

    registry_module.get_registry().register(adapter)
    service = NotificationService(
        broker=None,
        poll_interval=0.05,
        rate_limit_per_sec=10,
    )
    entry = await add_outbox_notification(
        notification_type="intro_day_invitation",
        booking_id=int(seeded["slot_id"]),
        candidate_tg_id=None,
        payload={
            "candidate_external_id": seeded["max_user_id"],
            "custom_message": "Ознакомительный день назначен. Подтвердите участие.",
        },
        messenger_channel="max",
    )
    item = OutboxItem(
        id=entry.id,
        booking_id=entry.booking_id,
        type=entry.type,
        payload=entry.payload_json or {},
        candidate_tg_id=entry.candidate_tg_id,
        recruiter_tg_id=entry.recruiter_tg_id,
        attempts=entry.attempts,
        created_at=entry.created_at,
        messenger_channel=entry.messenger_channel,
    )

    await service._process_intro_day_invitation(item)

    assert len(adapter.messages) == 1
    assert adapter.messages[0][0] == seeded["max_user_id"]

    async with async_session() as session:
        outbox = await session.get(OutboxNotification, entry.id)

    assert outbox is not None
    assert outbox.status == "sent"
