# Notification E2E Sandbox

This guide explains how to run the synthetic Telegram sandbox to verify that
candidate and recruiter notifications successfully traverse the pipeline and
produce `NotificationLog` entries with `delivery_status="sent"`.

## Prerequisites

- Local database with migrations applied (`python scripts/run_migrations.py`)
- Python environment for the repo (`.venv`)
- No need to expose the real Telegram Bot API – the script starts a local mock.

## Running the sandbox flow

```bash
PYTHONPATH=. .venv/bin/python scripts/e2e_notifications_sandbox.py \
  --candidate-chat-id 910001 \
  --recruiter-chat-id 910002
```

Arguments:

| Flag | Default | Description |
| --- | --- | --- |
| `--bot-token` | `sandbox:test` | Token injected into the mock Bot API URL. |
| `--candidate-chat-id` | `990001` | Telegram ID used for candidate notifications. |
| `--recruiter-chat-id` | `990002` | Telegram ID used for recruiter notifications. |
| `--sandbox-host` | `127.0.0.1` | Hostname for the mock API server. |
| `--sandbox-port` | `0` | Port for the mock server (`0` picks a random free port). |

The script performs the following steps:

1. Starts an HTTP server that mimics Telegram endpoints such as `sendMessage`.
2. Configures the bot + notification worker to talk to the sandbox via `BOT_API_BASE`.
3. Seeds the database with demo city/recruiter/slot/templates.
4. Enqueues two notifications (`candidate_rejection` and `recruiter_candidate_confirmed_notice`).
5. Forces a single poll iteration and verifies that `NotificationLog` records are written.

Successful run sample:

```json
{
  "slot_id": 1234,
  "log_count": 2,
  "sent_types": [
    "candidate_rejection",
    "recruiter_candidate_confirmed_notice"
  ],
  "sandbox_requests": [
    {"method": "sendMessage", "payload": {"chat_id": "990001", "text": "..." }},
    {"method": "sendMessage", "payload": {"chat_id": "990002", "text": "..." }}
  ]
}
```

The process exits with code `0` only when both candidate and recruiter messages are marked as sent; otherwise it returns `1`. Attach the generated JSON to release/audit notes inside `docs/reliability/`.
