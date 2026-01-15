"""Domain package for candidate onboarding and test-related models/services."""

from typing import Any

from . import models  # noqa: F401  # ensure models are registered

_SERVICE_EXPORTS = {
    "create_or_update_user",
    "save_test_result",
    "get_user_by_telegram_id",
    "get_user_by_candidate_id",
    "get_all_active_users",
    "get_test_statistics",
    "create_auto_message",
    "get_active_auto_messages",
    "create_notification",
    "mark_notification_sent",
    "update_candidate_reports",
    "link_telegram_identity",
    "create_candidate_invite_token",
    "bind_telegram_to_candidate",
    "update_chat_message_status",
    "log_inbound_chat_message",
    "list_chat_messages",
    "set_conversation_mode",
    "is_chat_mode_active",
}

__all__ = sorted(_SERVICE_EXPORTS)


def __getattr__(name: str) -> Any:
    if name in _SERVICE_EXPORTS:
        from . import services
        return getattr(services, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(list(globals().keys()) + list(_SERVICE_EXPORTS))
