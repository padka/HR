from __future__ import annotations

import pytest

from backend.apps.bot.runtime_config import (
    DEFAULT_REMINDER_POLICY,
    get_reminder_policy_config,
    normalize_reminder_policy,
    save_reminder_policy_config,
)


def test_normalize_reminder_policy_sanitizes_payload() -> None:
    normalized = normalize_reminder_policy(
        {
            "interview": {
                "confirm_6h": {"enabled": "yes", "offset_hours": "5.5"},
                "confirm_3h": {"enabled": False, "offset_hours": -3},
            },
            "intro_day": {"intro_remind_3h": {"enabled": True, "offset_hours": 100}},
            "min_time_before_immediate_hours": "abc",
        }
    )

    assert normalized["interview"]["confirm_6h"]["enabled"] is True
    assert normalized["interview"]["confirm_6h"]["offset_hours"] == 5.5
    assert normalized["interview"]["confirm_3h"]["enabled"] is False
    assert normalized["interview"]["confirm_3h"]["offset_hours"] == 0.25
    assert normalized["intro_day"]["intro_remind_3h"]["offset_hours"] == 72.0
    assert normalized["min_time_before_immediate_hours"] == 2.0


@pytest.mark.asyncio
async def test_get_and_save_reminder_policy_roundtrip() -> None:
    policy, updated_at = await get_reminder_policy_config()
    assert policy == DEFAULT_REMINDER_POLICY
    assert updated_at is None

    saved, saved_at = await save_reminder_policy_config(
        {
            "interview": {
                "confirm_6h": {"enabled": False, "offset_hours": 4},
                "confirm_3h": {"enabled": True, "offset_hours": 2.5},
                "confirm_2h": {"enabled": True, "offset_hours": 1.5},
            },
            "intro_day": {
                "intro_remind_3h": {"enabled": True, "offset_hours": 2},
            },
            "min_time_before_immediate_hours": 1.25,
        }
    )
    assert saved["interview"]["confirm_6h"]["enabled"] is False
    assert saved["interview"]["confirm_3h"]["offset_hours"] == 2.5
    assert saved["interview"]["confirm_2h"]["offset_hours"] == 1.5
    assert saved["intro_day"]["intro_remind_3h"]["offset_hours"] == 2.0
    assert saved["min_time_before_immediate_hours"] == 1.25
    assert saved_at is not None

    reloaded, reloaded_at = await get_reminder_policy_config()
    assert reloaded == saved
    assert reloaded_at is not None
