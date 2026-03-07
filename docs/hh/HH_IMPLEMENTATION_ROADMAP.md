# HH Implementation Roadmap

## Phase 1. Technical foundation
- introduce `backend/domain/hh_integration`
- add settings/env for direct HH integration
- add encrypted connection storage
- add candidate/vacancy identity tables
- add webhook receiver with idempotent persistence
- add admin endpoints for OAuth connect/status
- keep legacy `hh_sync` untouched

## Phase 2. Operational sync MVP
- initial vacancy import
- negotiation import for linked employer account
- candidate detail HH metadata block
- deep links to HH
- manual re-sync actions
- connection health panel

## Phase 3. Action-first lifecycle sync
- fetch current negotiation actions
- action mapping engine
- outbound command persistence and execution
- sync log and recruiter-visible errors
- basic refusal/interview/invitation/view actions

## Phase 4. Event-driven reliability
- subscription management against HH webhook API
- event processor
- polling reconciliation for missed webhooks
- retry/backoff
- dead-letter handling
- drift detection jobs

## Phase 5. UX and scale
- HH timeline in candidate detail
- list filters by HH source/sync status
- conflict dashboard
- rate limit protection and bulk-safe tooling
- support playbooks and observability dashboards

## First 7 engineering steps
1. Add direct HH integration settings and user-agent contract.
2. Create new foundation models and migration.
3. Implement token encryption and OAuth helpers.
4. Implement admin OAuth connect endpoints.
5. Implement external webhook receiver with idempotency.
6. Add targeted tests for OAuth/webhook foundation.
7. Only then start vacancy/negotiation import jobs.
