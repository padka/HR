# MAX Ownership Guard And Data Audit Plan

## Purpose
Локализовать ownership risk вокруг `users.max_user_id`, описать текущие read/write surfaces, зафиксировать application-level guard до schema cutover и дать migration-safe plan для будущей DB uniqueness.

## Owner
Backend Platform / Integrations Reliability

## Status
Active hardening plan

## Last Reviewed
2026-04-06

## Source Paths
- `/Users/mikhail/Projects/recruitsmart_admin/backend/apps/max_bot/candidate_flow.py`
- `/Users/mikhail/Projects/recruitsmart_admin/backend/apps/max_bot/app.py`
- `/Users/mikhail/Projects/recruitsmart_admin/backend/apps/admin_ui/services/messenger_health.py`
- `/Users/mikhail/Projects/recruitsmart_admin/backend/apps/admin_ui/services/chat.py`
- `/Users/mikhail/Projects/recruitsmart_admin/backend/apps/admin_ui/services/candidate_shared_access.py`
- `/Users/mikhail/Projects/recruitsmart_admin/backend/core/messenger/registry.py`
- `/Users/mikhail/Projects/recruitsmart_admin/backend/domain/candidates/max_ownership.py`
- `/Users/mikhail/Projects/recruitsmart_admin/backend/domain/candidates/models.py`

## Ownership Audit

### Where `users.max_user_id` is read
- `backend/apps/max_bot/candidate_flow.py`: ownership resolution, invite/deep-link linking, public MAX re-entry.
- `backend/apps/admin_ui/services/messenger_health.py`: operator health/diagnostics for candidate channel state.
- `backend/apps/admin_ui/services/chat.py`: recruiter-to-candidate delivery routing.
- `backend/apps/admin_ui/services/candidate_shared_access.py`: OTP/shared access delivery through linked MAX channel.
- `backend/core/messenger/registry.py`: runtime routing capability checks and adapter selection.

### Where `users.max_user_id` is written
- `backend/apps/max_bot/candidate_flow.py`:
  - invite/deep-link claim for an existing CRM candidate;
  - idempotent re-entry for the already linked candidate;
  - placeholder candidate creation for feature-flagged public MAX onboarding.

### Existing application-level checks
- Same invite reused by the same `max_user_id` is allowed and stays idempotent.
- Same invite reused by another `max_user_id` is rejected.
- Candidate already bound to another `max_user_id` is rejected on relink attempt.
- New in this tranche:
  - Postgres transaction-scoped advisory lock serializes claim path per normalized `max_user_id`.
  - Same `max_user_id` against another candidate becomes explicit `ownership_conflict`.
  - Multiple persisted candidates with the same `max_user_id` become explicit `ownership_ambiguous`; flow stops instead of picking an arbitrary owner row.
  - Admin `channel-health` surfaces ownership ambiguity and blocks delivery readiness when ownership is not trustworthy.

## Collision And Race Map

| Scenario | Current outcome | Remaining risk |
| --- | --- | --- |
| Same MAX account reuses its own invite | Idempotent, no duplicate candidate rows | Low |
| Same MAX account tries another candidate invite/deep-link | Explicit `ownership_conflict`, original owner preserved | Low |
| Candidate invite reused by another MAX account | Explicit `invite_conflict` | Low |
| Two first-time claims race for the same `max_user_id` in Postgres | Serialized by advisory lock before owner lookup/assignment | Low in production, not guaranteed on SQLite dev/test |
| Historical duplicate owner rows already exist in DB | Explicit `ownership_ambiguous`, delivery/re-entry blocked until repaired | Medium until audit/cleanup is done |
| Admin/operator surfaces still read oversized orchestration modules | Diagnostics improved, but code ownership is still concentrated in `candidate_flow.py` | Medium maintainability risk |

## Data Audit Plan

### Preflight query: duplicate owner rows
```sql
select
  max_user_id,
  count(*) as owner_count,
  array_agg(id order by id) as candidate_ids
from users
where max_user_id is not null
  and btrim(max_user_id) <> ''
group by max_user_id
having count(*) > 1
order by owner_count desc, max_user_id asc;
```

### Preflight query: ownership blast radius
```sql
select
  u.max_user_id,
  u.id as candidate_db_id,
  u.candidate_id,
  u.fio,
  u.phone_normalized,
  u.messenger_platform,
  u.candidate_status,
  u.workflow_status,
  u.source,
  u.last_activity,
  cit.created_at as latest_invite_created_at,
  cit.status as latest_invite_status,
  cit.used_at as latest_invite_used_at,
  cit.used_by_external_id as latest_invite_used_by_external_id
from users u
left join lateral (
  select *
  from candidate_invite_tokens cit
  where cit.candidate_id = u.candidate_id
    and cit.channel = 'max'
  order by cit.created_at desc, cit.id desc
  limit 1
) cit on true
where u.max_user_id in (
  select max_user_id
  from users
  where max_user_id is not null
    and btrim(max_user_id) <> ''
  group by max_user_id
  having count(*) > 1
)
order by u.max_user_id asc, u.id asc;
```

### What to classify during audit
- Whether duplicates are active business candidates, archived/history rows, or placeholder/public MAX rows.
- Whether duplicate rows share the same phone/recruiter/source and are safe merge candidates.
- Whether latest invite metadata points to one clear canonical owner.
- Whether recruiter chat/shared-access delivery still targets those duplicate rows.
- Whether rows are still receiving new MAX activity after the duplicate state was introduced.

## Preconditions Before DB Uniqueness
- Duplicate `max_user_id` rows are either merged, unlinked, or explicitly archived with a chosen canonical owner.
- Empty-string / whitespace anomalies are normalized so the future index can safely ignore only `NULL` or blank values by design.
- App-layer guard is already deployed and observed stable, so new duplicates stop appearing before migration.
- Operator runbook exists for `ownership_ambiguous` candidates discovered after deploy.
- Migration is scheduled separately from any invite/restart semantics change.

## Migration Recommendation

### Safe target
Introduce a partial unique index after data cleanup:

```sql
create unique index concurrently if not exists uq_users_max_user_id_not_blank
on users (max_user_id)
where max_user_id is not null
  and btrim(max_user_id) <> '';
```

### Recommended rollout
1. Run duplicate-owner audit and classify every collision.
2. Repair/merge/unlink collisions in controlled batches with audit logging.
3. Re-run preflight until duplicate query is empty.
4. Deploy code with app-level guard already enabled.
5. Create the partial unique index concurrently.
6. Monitor for write failures on MAX claim paths and admin `channel-health` ambiguity signals.

### Migration risks
- Existing duplicates will cause unique-index creation to fail immediately.
- Repair scripts that clear `max_user_id` from the wrong candidate can strand recruiter chat/shared-access delivery.
- Concurrent operator cleanup without ownership lock discipline can recreate the same conflict during rollout.
- SQLite dev/test cannot model Postgres advisory locking or `CONCURRENTLY`; rollout confidence must come from Postgres-backed validation.

### Rollback considerations
- Keep the application-level guard even if the DB uniqueness rollout is postponed or reverted.
- If the unique index must be rolled back, drop only the new index; do not remove the conflict/ambiguity guard.
- Do not combine index rollout with broader MAX product semantics changes; rollback must stay isolated to ownership enforcement.

## Operational Notes
- `channel-health` is now the first operator-facing place to confirm `ownership_status`, `ownership_candidate_ids`, and whether delivery was blocked by ambiguity.
- `ownership_ambiguous` should be treated as data-quality debt, not as a recoverable candidate self-service state.
- `ownership_conflict` is candidate-facing by design: it protects the existing owner instead of silently re-routing the MAX session.
