from backend.domain.idempotency import (
    has_max_provider_boundary,
    max_admin_chat_key,
    max_chat_prompt_key,
    max_provider_message_id,
    max_rollout_invite_send_key,
    max_webhook_inbound_message_key,
    max_webhook_outbound_key,
)


def test_max_idempotency_keys_are_stable_and_fit_chat_message_limit() -> None:
    keys = {
        max_webhook_outbound_key("manual-prompt", "callback-123"),
        max_webhook_inbound_message_key(
            provider_message_id="provider-mid-1",
            message_text="ignored when provider id exists",
            max_user_id="max-user-1",
        ),
        max_chat_prompt_key("base-request", state="booking_slot", booking_id=42),
        max_admin_chat_key(123, "browser-command-1"),
        max_rollout_invite_send_key(456),
        max_webhook_outbound_key("very-long-scope", "x" * 200),
    }

    assert len(keys) == 6
    assert all(key.startswith("max:") for key in keys)
    assert all(len(key) <= 64 for key in keys)
    assert max_rollout_invite_send_key(456) == max_rollout_invite_send_key(456)


def test_max_provider_boundary_detects_provider_result() -> None:
    assert has_max_provider_boundary(status="failed", payload_json={"provider_message_id": "mid-1"})
    assert has_max_provider_boundary(status="sent", payload_json={})
    assert not has_max_provider_boundary(status="failed", payload_json={})
    assert max_provider_message_id({"provider_message_id": " mid-1 "}) == "mid-1"
