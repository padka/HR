# HH CRM-master Sync MVP

## Status
Accepted for MVP implementation.

## Goal
- CRM is the source of truth for candidate statuses.
- HH is a source channel and external action surface.
- Recruiters work only in CRM.
- HH synchronization is executed only through supported HH actions discovered at runtime.

## Scope
- Inbound HH response ingestion into CRM.
- Persistence of HH candidate identity and sync metadata.
- Outbound CRM status synchronization for a minimal mapped subset of statuses.
- Structured sync errors, retry support, and operator-visible job state.

## Non-goals
- Replacing the current CRM status taxonomy.
- Free-text state mirroring into HH.
- Bidirectional status reconciliation where HH can overwrite CRM workflow state.
- Per-recruiter or per-vacancy HH connection routing in MVP.

## Architecture
- Reuse `backend/domain/hh_integration` as the primary integration domain.
- Keep legacy `backend/domain/hh_sync` readable for compatibility only.
- Reuse `hh_sync_jobs` as the only queue/retry surface.
- Reuse `hh_webhook_deliveries` for delivery dedupe and webhook audit.

## Source Of Truth Rules
- CRM `candidate_status` is canonical for recruiter actions.
- HH negotiation state is only consulted to decide whether a mapped HH action is available.
- HH webhook payloads are not treated as authoritative CRM status changes.
- Imported HH payload snapshots are support/debug data, not workflow ownership.

## Outbound Mapping
- `interview_scheduled`, `interview_confirmed` -> `invite_to_interview`
- `interview_declined`, `test2_failed`, `intro_day_declined_invitation`, `intro_day_declined_day_of`, `not_hired` -> `reject_candidate`
- `hired` -> `mark_hired`
- all other CRM statuses -> `no_op`

## Outbound Execution Rules
- Never push a raw HH status string from CRM.
- Before executing an HH action, refresh the latest negotiation snapshot.
- Only enabled HH actions may be executed.
- If no enabled action matches the mapped intent, record `wrong_state` or `action_unavailable`.
- CRM state must not be rolled back on HH sync failure.

## Idempotency
- Each outbound CRM status sync is represented as a deterministic `hh_sync_jobs` row keyed by:
  - candidate id
  - target CRM status
  - candidate `status_changed_at`
- Repeated enqueue attempts for the same CRM transition must dedupe to the same pending/running job.
- Retry reuses the same stored job row instead of creating a new logical intent.

## Failure Model
- Stable failure codes:
  - `transport_error`
  - `provider_http_error`
  - `token_refresh_required`
  - `action_unavailable`
  - `wrong_state`
  - `identity_not_linked`
- Retryable:
  - `transport_error`
  - `provider_http_error`
  - `token_refresh_required`
- Terminal by default:
  - `action_unavailable`
  - `wrong_state`
  - `identity_not_linked`

## Inbound Flow
1. HH sends webhook to `/api/hh-integration/webhooks/{webhook_key}`.
2. Delivery is deduped by `(connection_id, delivery_id)`.
3. Receiver enqueues a scoped `import_negotiations` job when a vacancy can be resolved.
4. Importer upserts candidate, first-class HH identity rows, negotiation snapshot, and legacy `users.hh_*` compatibility fields.

## Secrets And Security
- HH OAuth tokens remain encrypted at rest.
- OAuth state remains signed and TTL-bound.
- Webhook receiver remains authenticated by per-connection secret path key.
- Logs must not expose tokens, webhook keys, or raw secrets.

## Operations
### Required env vars
- `HH_INTEGRATION_ENABLED`
- `HH_CLIENT_ID`
- `HH_CLIENT_SECRET`
- `HH_REDIRECT_URI`
- `HH_USER_AGENT`
- `HH_WEBHOOK_BASE_URL`

### Webhooks
- Register HH webhooks through the existing admin HH integration endpoints.
- The callback target is derived from `HH_WEBHOOK_BASE_URL` and the connection webhook key.

### Retry
- Failed outbound syncs remain visible in `hh_sync_jobs`.
- Operators can retry through the existing retry endpoint.
- Terminal failures stay visible for manual review and explicit retry after data/state correction.

## Notes
- MVP remains on the existing `candidate_status` model.
- Office-day-specific CRM states stay internal unless HH exposes a safe mapped action.
