# HH Sync Lifecycle

## Inbound: HH -> CRM
1. HH sends webhook to connection-specific receiver URL.
2. Receiver validates connection by unguessable URL key.
3. Delivery is stored in `hh_webhook_deliveries` with unique `(connection_id, delivery_id)`.
4. Duplicate delivery returns `409` and is not re-enqueued.
5. New delivery returns `202` and becomes source input for processor/reconciliation.
6. Processor resolves affected entity (`vacancy`, `resume`, `negotiation`, `candidate identity`).
7. Processor updates normalized snapshot tables and appends sync log entry.
8. If entity resolution fails, create conflict / error state and leave delivery traceable.

## Outbound: CRM -> HH
1. Recruiter action in CRM expresses business intent.
2. Integration service loads current negotiation snapshot and available HH actions.
3. Mapping layer selects candidate HH action.
4. Command is persisted with idempotency key before network call.
5. Worker executes HH request.
6. Response updates local sync state and audit log.
7. Webhook or follow-up polling reconciles final HH state.

## Sync states
Recommended normalized states:
- `pending_sync`
- `synced`
- `failed_sync`
- `conflicted`
- `stale`
- `skipped`

## Retry policy
Retryable:
- transport errors
- HH `5xx`
- timeout
- temporary `chat_is_not_ready`-style transient states

Non-retryable without human action:
- `wrong_state`
- `already_applied`
- `not_enough_purchased_services`
- revoked auth / invalid refresh token

## Idempotency
Use stable keys for:
- outbound commands: `provider + connection + command_type + negotiation_id + crm_event_id`
- webhook deliveries: `(connection_id, delivery_id)`
- initial imports: `connection_id + entity_type + external_id + source_updated_at`

## Conflict handling
Conflict examples:
- CRM stage expects action not currently allowed in HH
- webhook reports state unknown to current mapping version
- local candidate linked to resume that now belongs to different negotiation chain

Recommended resolution flow:
- mark entity `conflicted`
- expose banner in UI
- allow manual re-sync / re-resolve
- preserve raw payload for support analysis
