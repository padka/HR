"""Bootstrap helpers for the notification service."""

from __future__ import annotations

from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from backend.apps.bot.broker import NotificationBrokerProtocol
from backend.apps.bot.services import (
    NotificationService,
    configure_notification_service as _register_service,
)
from backend.core.settings import get_settings

_bootstrap_instance: Optional[NotificationService] = None


def configure_notification_service(
    *,
    broker: Optional[NotificationBrokerProtocol],
    scheduler: Optional[AsyncIOScheduler] = None,
) -> NotificationService:
    """Configure and memoize the notification service singleton."""

    global _bootstrap_instance
    if _bootstrap_instance is not None:
        return _bootstrap_instance

    settings = get_settings()
    service = NotificationService(
        scheduler=scheduler,
        broker=broker,
        poll_interval=settings.notification_poll_interval,
        batch_size=settings.notification_batch_size,
        rate_limit_per_sec=settings.notification_rate_limit_per_sec,
        worker_concurrency=settings.notification_worker_concurrency,
        max_attempts=settings.notification_max_attempts,
        retry_base_delay=settings.notification_retry_base_seconds,
        retry_max_delay=settings.notification_retry_max_seconds,
    )
    _register_service(service)
    _bootstrap_instance = service
    return service
