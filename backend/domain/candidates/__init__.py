"""Domain package for candidate onboarding and test-related models/services."""

from . import models  # noqa: F401  # ensure models are registered
from .services import (  # noqa: F401
    create_or_update_user,
    save_test_result,
    get_user_by_telegram_id,
    get_all_active_users,
    get_test_statistics,
    create_auto_message,
    get_active_auto_messages,
    create_notification,
    mark_notification_sent,
)

__all__ = [
    "create_or_update_user",
    "save_test_result",
    "get_user_by_telegram_id",
    "get_all_active_users",
    "get_test_statistics",
    "create_auto_message",
    "get_active_auto_messages",
    "create_notification",
    "mark_notification_sent",
]
