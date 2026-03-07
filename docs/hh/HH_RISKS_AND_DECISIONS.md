# HH Risks And Decisions

## Recommended decisions
### 1. Source of truth
Recommendation: hybrid.
- CRM owns internal workflow and recruiter operations.
- HH owns imported resume/negotiation/vacancy external lifecycle.

### 2. Sync direction
- candidate profile core: CRM primary, HH-enriched inbound
- resume snapshot: inbound from HH
- negotiation status: bidirectional via action orchestration
- recruiter notes: CRM-only by default
- comments to HH: later, optional
- refusal/interview/invitation/view: outbound to HH where action exists

### 3. Webhook-first vs polling-first
Recommendation: webhook-first with mandatory polling fallback.

### 4. Raw payload storage
Recommendation: yes, store raw payloads with timestamps and minimal retention policy controls.

### 5. Mapping strategy
Recommendation: action-first orchestration + versioned mapping, not static status table.

### 6. Chat sync in MVP
Recommendation: no. Chat is not MVP core because legacy negotiation message endpoints are deprecated.

### 7. Synchronous vs background
- synchronous in UX: validation, command acceptance, pending state creation
- background: external HH call, retries, reconciliation, heavy imports

## Top risks
1. Hardcoding HH statuses as if they were stable CRM states.
2. Binding candidate only by URL string left by candidate.
3. Storing OAuth tokens unencrypted.
4. Treating webhooks as guaranteed delivery.
5. Ignoring `manager_account_id` and multi-account semantics.
6. Executing actions without loading current allowed HH actions.
7. Letting failed sync disappear without recruiter-visible state.
8. Reusing legacy deprecated message methods as core communication architecture.
9. No idempotency on invite/apply flows causing `already_applied` failures.
10. Mixing new direct integration with old `hh_sync` path without explicit migration boundary.

## Recommended compromise points
- keep old `users.hh_*` fields during transition;
- introduce new module in parallel;
- start with connection + identity + webhook foundation;
- move action sync after runtime discovery layer exists.
