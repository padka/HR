"""Compatibility service delegating to the new backend domain layer."""

from backend.domain.candidates import (
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


class DatabaseService:
    """Legacy facade kept for backwards compatibility."""

    create_or_update_user = staticmethod(create_or_update_user)
    save_test_result = staticmethod(save_test_result)
    get_user_by_telegram_id = staticmethod(get_user_by_telegram_id)
    get_all_active_users = staticmethod(get_all_active_users)
    get_test_statistics = staticmethod(get_test_statistics)
    create_auto_message = staticmethod(create_auto_message)
    get_active_auto_messages = staticmethod(get_active_auto_messages)
    create_notification = staticmethod(create_notification)
    mark_notification_sent = staticmethod(mark_notification_sent)


__all__ = [
    "DatabaseService",
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
