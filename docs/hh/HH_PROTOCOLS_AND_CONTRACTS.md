# HH Protocols And Contracts

## Connection contract
### hh_connections
Purpose: store one HH connection per local principal.

Required fields:
- `principal_type`
- `principal_id`
- encrypted access/refresh tokens
- `employer_id`
- `manager_id`
- `manager_account_id`
- `webhook_url_key`
- `status`

## Webhook delivery contract
Receiver path:
- `POST /api/hh-integration/webhooks/{webhook_key}`

Expected inbound payload:
- `id`
- `subscription_id`
- `action_type`
- `payload`

Response contract:
- `202 Accepted` for new delivery
- `409 Conflict` for duplicate delivery
- `404` for unknown key
- `400` for malformed payload

Storage contract:
- unique key: `(connection_id, delivery_id)`
- preserve raw headers and raw payload

## OAuth contract
Admin endpoint:
- `GET /api/integrations/hh/oauth/authorize`
- returns authorize URL and state metadata

Callback endpoint:
- `GET /api/integrations/hh/oauth/callback?code=...&state=...`
- validates signed state
- exchanges code
- fetches `/me` and `/manager_accounts/mine`
- upserts connection

## Idempotency contract
- OAuth callback: safe upsert by `(principal_type, principal_id)`
- Webhook delivery: safe dedupe by `(connection_id, delivery_id)`
- Future outbound commands: unique idempotency key per CRM intent

## Security contract
- tokens encrypted at rest
- signed OAuth state
- no raw tokens in logs
- webhook endpoint uses unguessable per-connection key because HH webhook subscriptions do not include first-class secret field

## Compatibility contract
- legacy `backend/domain/hh_sync` stays intact
- new `backend/domain/hh_integration` is additive
- old `users.hh_*` fields remain readable during migration
