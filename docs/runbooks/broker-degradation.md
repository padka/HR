# Broker Degradation

## Purpose
Описать действия при деградации Redis-backed notification broker или content update pub/sub, чтобы сохранить доступность системы и не потерять бизнес-события.

## Owner
Platform / Bot Runtime / On-call

## Status
Canonical

## Last Reviewed
2026-03-25

## Source Paths
- `/Users/mikhail/Projects/recruitsmart_admin/backend/apps/admin_ui/state.py`
- `/Users/mikhail/Projects/recruitsmart_admin/backend/apps/bot/broker.py`
- `/Users/mikhail/Projects/recruitsmart_admin/backend/core/content_updates.py`
- `/Users/mikhail/Projects/recruitsmart_admin/backend/apps/admin_ui/app.py`
- `/Users/mikhail/Projects/recruitsmart_admin/backend/core/redis_factory.py`

## Related Diagrams
- `docs/security/trust-boundaries.md`
- `docs/security/auth-and-token-model.md`

## Change Policy
- Runbook covers observable degradation and safe fallback, not code changes.
- Broker fallback must remain idempotent and best-effort.

## Incident Entry Points
- `/health/notifications`
- `app.state.notification_broker_status`
- `app.state.notification_broker_available`
- Redis ping/publish logs
- `CONTENT_UPDATES_CHANNEL`

## Symptoms
- Notifications stop draining.
- Bot or admin runtime reports `degraded` broker status.
- Content updates do not reach the bot.
- Redis is unreachable or Redis client library is missing.
- Only Telegram or only MAX stops draining while the second channel still sends.
- Outbox rows move to `dead_letter` with `misconfiguration` and channel-specific degraded reason.

## Immediate Response

1. Confirm whether the app has switched to in-memory fallback.
2. Check whether `REDIS_URL` is missing, malformed, or unreachable.
3. Inspect broker logs for reconnect attempts and publish failures.
4. Check `/api/system/messenger-health` or operator UI to see whether degradation is broker-wide or only `telegram` / `max`.
5. Separate delivery degradation from data corruption.

## Triage Flow

```mermaid
flowchart TD
  A["Broker degradation"] --> B{"Redis reachable?"}
  B -->|No| C["Use memory fallback, keep service alive"]
  B -->|Yes| D{"Broker attach/start succeeded?"}
  D -->|No| E["Inspect Redis client / permissions / topology"]
  D -->|Yes| F{"Notifications still stuck?"}
  F -->|Yes| G["Inspect queue consumer, stale claims, per-channel degraded state, DLQ"]
  F -->|No| H["Monitor until stable"]
```

## Recovery Steps

1. Restore Redis reachability or credentials.
2. Restart affected runtime only if reconnect loop does not recover.
3. Verify notification broker transitions from `degraded` to `ok`.
4. Verify content updates can be published again.
5. If only one messenger channel is degraded, fix adapter/config cause first, then call `POST /api/system/messenger-health/{channel}/recover` to clear degraded state explicitly.
6. Only after channel recovery, use explicit requeue for affected `dead_letter` items. Retry does not auto-clear degraded state.
7. Check whether any messages were moved to DLQ / `dead_letter` and triage them separately.

## Verification

- `/health/notifications` shows healthy delivery state.
- `app.state.notification_broker_status` is `ok` or `memory` where that is the explicit dev fallback.
- Bot/admin critical message flow works end-to-end.
- `/api/system/messenger-health` shows expected per-channel queue depth, dead-letter count and `degraded=false` after recovery.

## Escalation Criteria

- Redis outage affects all critical delivery paths.
- DLQ growth is unexpected.
- Reconnect loops cause request latency or process churn.
