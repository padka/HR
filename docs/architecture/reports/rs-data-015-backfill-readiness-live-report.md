# RS-DATA-015 Backfill Readiness Live Report

## Environment

- Date: 2026-04-16
- Target type: local non-production Postgres clone on `localhost:5432`
- Safe target DB: `rs_test`
- Source DB: `recruitsmart` read only
- Read-only mode: yes for profiling
- Production DB touched: no

## Migration Status

- Phase A additive schema migration `0102_phase_a_schema_foundation` applied on the safe clone only.
- Verified on safe target:
  - `16 / 16` Phase A tables present
  - `4 / 4` bridge columns present on `candidate_journey_sessions`
- No backfill was executed.
- No destructive action was used.

## Profiler Status

- Profiler: `scripts/profile_phase_a_backfill_readiness.py`
- Result: success
- Output mode: JSON aggregate counts only
- Generated at: `2026-04-16T16:41:27.071153+00:00`

## High-Signal Counts

| Bucket | Count | Notes |
| --- | ---: | --- |
| `users_total` | 24 | Clone population baseline |
| `phone_normalized_duplicate_groups` | 2 | Primary identity blocker |
| `phone_normalized_affected_candidates` | 7 | Candidates involved in duplicate phone ownership |
| `users_with_source_or_desired_position_no_vacancy` | 17 | Weak demand signals without deterministic vacancy anchor |
| `users_with_city_no_vacancy` | 18 | City present without vacancy anchor |
| `outbox_mapping_gaps` | 5 | Delivery history is not fully reconstructible |
| `journey_sessions_without_access_anchor` | 9 | Access/session fill-forward needed |
| `ai_outputs_unmappable` | 112 | AI provenance gaps at candidate/application grain |
| `ai_request_logs_unmappable` | 29 | AI audit trail gaps |
| `journey_sessions_total` | 11 | Legacy journey rows present |
| `candidate_invite_tokens_total` | 14 | Invite chain material present |

## Blockers

- `phone_normalized_duplicates = 2`
- Interpretation: normalized phone ownership is ambiguous and cannot be auto-resolved safely.
- Manual review required before strict resolver hardening or merge automation.

## Warnings

- `weak_demand_only_candidates = 17`
- `city_only_candidates = 18`
- `ai_provenance_gaps = 141` total across unmappable AI outputs and request logs
- `outbox_mapping_gaps = 5`
- `journey_access_gaps = 9`

## Ambiguous Buckets

- `outbox_mapping_gaps = 5`
- `journey_access_gaps = 9`

These should not be forced into strict backfill. They need manual review or fill-forward treatment.

## Manual Review Queues

| Queue | Trigger count | Reason |
| --- | ---: | --- |
| `identity_conflicts_review` | 2 | Resolve phone ownership conflicts first |
| `ambiguous_demand_review` | 35 | Demand hints exist without deterministic requisition binding |
| `delivery_mapping_review` | 5 | Messaging artifacts lack enough anchors for deterministic history |
| `ai_provenance_review` | 141 | AI artifacts need candidate/application provenance review |
| `journey_access_review` | 9 | Journey and access rows need cleanup before access/session hardening |

## Backfill Decision Table

| Entity | Readiness | Blockers | Manual review needed | Phase recommendation |
| --- | --- | --- | --- | --- |
| Identity / ownership | `unsafe` | `phone_normalized_duplicates` | yes | Phase B blocker |
| Demand / requisition inference | `partial` | weak demand / city-only anchors | yes | Phase B, null-requisition only |
| Scheduling / slot assignment | `deterministic` | none in this run | no | Phase B can proceed |
| Messaging / delivery | `partial` | `outbox_mapping_gaps` | yes | Phase B fill-forward |
| AI provenance | `partial` | `ai_provenance_gaps` | yes | Phase B partial only |
| Journey / access | `fill-forward` | `journey_access_gaps` | yes | Phase B/C fill-forward |
| Invite chains | `deterministic` | none in this run | no | Phase B can proceed |

## What Can Be Backfilled Deterministically

- Scheduling ownership and slot-assignment continuity
- Invite-chain rows without conflict
- Legacy rows that already have a single safe identity anchor

## What Is Partial Or Fill-Forward Only

- Weak demand / city-only candidate context
- Messaging delivery history with missing anchors
- AI output/request provenance
- Journey/access rows without clean access-session anchoring

## What Is Unsafe

- Phone identity collisions
- Any attempt to auto-merge ambiguous ownership
- Forcing deterministic delivery history for outbox rows with incomplete anchors

## Notes

- No PII, tokens, or raw payloads were emitted.
- The profiler emitted only aggregate counts and buckets.
- The only runtime warning observed was the existing in-memory rate-limiter warning; it did not block the audit.
