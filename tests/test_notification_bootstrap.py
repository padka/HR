import pytest

from backend.apps.bot.notifications import bootstrap
from backend.apps.bot.reminders import create_scheduler


@pytest.mark.asyncio
async def test_notification_service_reinitializes_after_reset():
    bootstrap.reset_notification_service()
    scheduler = create_scheduler(redis_url=None)
    service = bootstrap.configure_notification_service(broker=None, scheduler=scheduler)
    first_identity = id(service)

    await service.shutdown()
    bootstrap.reset_notification_service()

    scheduler2 = create_scheduler(redis_url=None)
    service2 = bootstrap.configure_notification_service(broker=None, scheduler=scheduler2)

    try:
        assert id(service2) != first_identity
    finally:
        await service2.shutdown()
        bootstrap.reset_notification_service()


@pytest.mark.asyncio
async def test_notification_service_disable_runtime_removes_scheduler_job():
    bootstrap.reset_notification_service()
    scheduler = create_scheduler(redis_url=None)
    service = bootstrap.configure_notification_service(broker=None, scheduler=scheduler)

    try:
        service.start()
        assert scheduler.get_job("notification:outbox_worker") is not None

        await service.disable_runtime()

        assert scheduler.get_job("notification:outbox_worker") is None
        snapshot = await service.health_snapshot()
        assert snapshot["started"] is False
        assert snapshot["scheduler_job"] is False
    finally:
        await service.shutdown()
        bootstrap.reset_notification_service()
