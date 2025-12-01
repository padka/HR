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
    update_candidate_reports,
    link_telegram_identity,
    update_chat_message_status,
    log_inbound_chat_message,
    list_chat_messages,
    set_conversation_mode,
    is_chat_mode_active,
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
    "update_candidate_reports",
    "link_telegram_identity",
    "update_chat_message_status",
    "log_inbound_chat_message",
    "list_chat_messages",
    "set_conversation_mode",
    "is_chat_mode_active",
]
