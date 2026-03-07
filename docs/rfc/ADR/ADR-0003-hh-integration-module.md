# ADR-0003: Introduce HH Integration Module

## Status
Accepted

## Context
RecruitSmart already contains a legacy HH synchronization path implemented through:
- `backend/domain/hh_sync`
- `backend/apps/admin_api/hh_sync.py`
- candidate-level `hh_*` columns on `users`

That path is sufficient only for narrow status sync/resolution through `n8n`. It does not model HH as first-class external domain and cannot safely support stable identity, vacancy import, runtime action discovery, webhook processing or reliable two-way sync.

## Decision
Introduce a new additive module `backend/domain/hh_integration` with its own:
- connection model
- OAuth helpers
- HH client wrapper
- identity tables
- webhook delivery log
- future sync jobs / negotiation snapshots

Keep the existing `backend/domain/hh_sync` module as legacy compatibility path until migrated feature-by-feature.

## Rationale
- HH workflow is action-driven and employer-specific.
- Existing static mapping and `n8n` callback model are too narrow for the target product capability.
- Direct integration needs explicit domain boundaries, retry/idempotency semantics and secure token handling.

## Consequences
### Positive
- Future HH work has a clear home.
- OAuth and webhook flow become first-class code, not side-channel automation only.
- Candidate identity model becomes stable and auditable.

### Negative
- Two HH paths coexist during transition.
- Additional tables and service modules increase short-term complexity.

## Rejected alternatives
### 1. Extend `users.hh_*` fields only
Rejected because it keeps identity, connection and negotiation lifecycle collapsed into a single candidate record.

### 2. Make `n8n` the primary long-term HH integration engine
Rejected because core orchestration, idempotency and supportability should remain in application code and database, not only in external low-code flows.

### 3. Use static `CRM status -> HH status` mapping as primary design
Rejected because HH docs explicitly recommend action-driven handling and state availability varies by vacancy/employer.
