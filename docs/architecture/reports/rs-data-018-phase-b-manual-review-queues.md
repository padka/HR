# RS-DATA-018 Phase B Manual Review Queues

## Context

- Date: 2026-04-16
- Source signal: live run of `scripts/profile_phase_a_backfill_readiness.py`
- Snapshot type: local development PostgreSQL snapshot after Phase A schema
- Environment trust level: non-production, local-only, not a staging or production clone
- Intended use: early data-quality signal for Phase B planning

## Limitations

- This report is based on a local development database and must not be treated as staging truth.
- Counts are useful for migration planning and queue design, but not for final production cutover decisions.
- No candidate-level cleanup, merge, or backfill was executed.
- No PII, raw payloads, tokens, usernames, or connection details are included.

## Summary

### Live buckets

| Bucket | Count | Priority | Meaning |
| --- | ---: | --- | --- |
| `phone_normalized_duplicates` | 2 | `P0` | Identity ownership is ambiguous and blocks strict resolver hardening |
| `weak_demand_only_candidates` | 17 | `P1` | Demand signal exists but no deterministic vacancy or requisition anchor |
| `city_only_candidates` | 18 | `P1` | City exists without clean requisition anchor |
| `ai_provenance_gaps` | 141 | `P2` | Historical AI records cannot be mapped losslessly at candidate/application grain |
| `outbox_mapping_gaps` | 5 | `P2` | Historical delivery evidence is incomplete |
| `journey_access_gaps` | 9 | `P2` | Legacy journey rows do not have safe access-session anchoring |

### Manual review queue sizes

| Queue | Size | Priority |
| --- | ---: | --- |
| `identity_conflicts_review` | 2 | `P0` |
| `ambiguous_demand_review` | 35 | `P1` |
| `delivery_mapping_review` | 5 | `P2` |
| `ai_provenance_review` | 141 | `P2` |
| `journey_access_review` | 9 | `P2` |

## What Blocks Phase B Strict Resolver

Only unresolved identity ownership conflicts block strict resolver hardening in this snapshot.

Current blocker:

- `phone_normalized_duplicates = 2`

Why this is blocking:

- the resolver cannot safely infer whether the rows represent the same person, different people sharing a phone, or bad normalized phone data;
- any automatic ownership hardening here risks wrong candidate/application binding;
- any automatic merge or dedup dismissal would be unsafe without human review.

Resolver-adjacent buckets that do **not** block strict resolver directly:

- `weak_demand_only_candidates`
- `city_only_candidates`
- `outbox_mapping_gaps`
- `ai_provenance_gaps`
- `journey_access_gaps`

These should not force resolver guessing. They should be handled with `null-requisition`, `partial`, or `fill-forward` policy.

## What Does Not Block Phase A / Schema

The following do not block Phase A additive schema or Phase A runtime safety:

- ambiguous demand without deterministic requisition
- historical delivery artifacts with incomplete anchors
- historical AI provenance gaps
- historical journey/access gaps

These buckets affect Phase B backfill quality and operational review, but they do not invalidate the Phase A schema foundation.

## Manual Review Queues

### Queue A — Identity Conflicts

- Priority: `P0`
- Bucket: `phone_normalized_duplicates`
- Current size: `2`
- Blocks:
  - strict identity hardening
  - strict primary application resolver enablement
  - any automated merge or dedup workflow

Manual decision required per duplicate group:

- same person or not
- separate people sharing one phone or not
- bad normalization or not
- merge candidate or not
- mark duplicate dismissed or not

Accepted outcomes:

- conflict resolved and documented
- duplicate dismissed and documented
- normalization issue explicitly marked
- group moved to separate manual exception workflow

Not allowed:

- auto-merge
- guessed ownership reassignment
- silent dismissal without explicit decision

### Queue B — Ambiguous Demand

- Priority: `P1`
- Buckets:
  - `weak_demand_only_candidates = 17`
  - `city_only_candidates = 18`
- Combined queue size: `35`
- Does not block Phase A
- Does not block strict resolver if the null-requisition policy is accepted

Recommended handling:

- do not guess requisition
- create or keep `applications.requisition_id = null`
- fill forward demand only when an explicit recruiter, HH, slot, or direct requisition signal appears

Accepted outcomes:

- candidate intentionally kept on null-requisition application
- explicit requisition identified by trusted business signal
- candidate marked as unresolved demand until future signal appears

### Queue C — Delivery Mapping Review

- Priority: `P2`
- Buckets:
  - `outbox_mapping_gaps = 5`
  - `delivery_mapping_review = 5`
- Does not block Phase A
- Does not block strict resolver

Recommended handling:

- do not force lossless reconstruction
- treat historical gaps as advisory history only
- start clean `message_deliveries` truth from future routing v2 writes

Accepted outcomes:

- historical row marked advisory / partial
- row excluded from deterministic backfill
- future delivery lineage captured fill-forward only

### Queue D — AI Provenance Review

- Priority: `P2`
- Buckets:
  - `ai_provenance_gaps = 141`
  - `ai_provenance_review = 141`
- Does not block Phase A
- Does not block strict resolver

Recommended handling:

- do not backfill `ai_decision_records` unless a clean request/output/action chain exists
- do not block `applications` / `application_events` foundation on historical AI gaps
- fill forward future AI acceptance, edit, reject, and ignore logging

Accepted outcomes:

- historical AI artifact marked unmappable
- clean AI chain promoted to deterministic backfill candidate
- future-only audit coverage accepted

### Queue E — Journey / Access Review

- Priority: `P2`
- Buckets:
  - `journey_access_gaps = 9`
  - `journey_access_review = 9`
- Does not block Phase A
- Does not block strict resolver

Recommended handling:

- do not reconstruct fake access sessions
- preserve legacy journey history as-is
- start clean `candidate_access_sessions` only for future launches

Accepted outcomes:

- historical journey row retained without synthetic access session
- row marked fill-forward only
- row explicitly excluded from deterministic access backfill

## Cleanup Acceptance Criteria Before Phase B Strict Resolver

The following must be true before strict resolver hardening:

- all `phone_normalized` duplicate groups are reviewed
- no unresolved `P0` identity conflict remains
- duplicate groups are resolved, dismissed, or moved to a tracked exception queue
- ambiguous demand strategy is formally approved
- there is no attempt to force requisition onto weak-demand-only or city-only candidates
- AI, delivery, and journey historical gaps are classified as `partial` or `fill-forward` unless a clean mapping exists

## Backfill Decision Policy

| Entity / area | Readiness | Why | Recommended Phase B behavior |
| --- | --- | --- | --- |
| Identity ownership | `unsafe` until reviewed | duplicate phone ownership can produce wrong application anchor | manual review first |
| Requisition inference from weak demand | `partial` | weak or city-only signals are not deterministic | keep `null-requisition` |
| Scheduling and invite continuity | `deterministic` in this snapshot | no active conflict bucket surfaced here | deterministic backfill allowed |
| Historical delivery lineage | `partial` | outbox gaps prevent lossless reconstruction | advisory history + fill-forward |
| Historical AI provenance | `partial` | request/output/action chain often incomplete | clean-chain-only backfill |
| Historical journey/access continuity | `fill-forward` | safe access-session reconstruction is absent | preserve legacy history, start clean future sessions |

## Manual Review Process

### Queue owners

- Queue A: data ops lead or backend owner with recruiter ops sign-off
- Queue B: recruiter ops / business ops
- Queue C: messaging ops / backend owner
- Queue D: AI owner or backend owner
- Queue E: candidate journey owner / backend owner

### Recommended handling order

1. Queue A — unblock strict resolver
2. Queue B — approve null-requisition policy and exception handling
3. Queue C — mark historical delivery rows advisory
4. Queue D — mark historical AI rows clean-chain-only or fill-forward
5. Queue E — accept future-only access session truth

### Exit criteria for this report

- every queue has a named owner
- every queue has a decision policy
- Queue A has explicit SLA before strict resolver work starts
- Queue B has explicit approval for `null-requisition` as the default safe outcome
- Queues C, D, and E are explicitly accepted as `partial` or `fill-forward`

## Why No Export Script Was Added In This Step

An additional row-level or opaque-id exporter was intentionally not added in this step.

Reason:

- the current signal comes from a local development snapshot, not a staging-quality truth source;
- a queue exporter that emits row-level identifiers from this snapshot adds reidentification risk while giving limited operational value;
- the current Phase B need is decision policy and queue ownership, not automated cleanup or row-level export.

If a later operational pass needs an exporter, it should target a trusted non-production staging clone and remain aggregate-first, with row identifiers gated to tightly scoped internal use only.

## Operator Checklist Before Strict Resolver

- review both duplicate phone groups in Queue A
- record explicit decision for each group
- approve `null-requisition` handling for Queue B
- accept that Queues C, D, and E are not strict blockers
- avoid candidate merge unless there is a separate explicit merge workflow and approval
