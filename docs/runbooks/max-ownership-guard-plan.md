# MAX Ownership Guard Plan

## Purpose
Подготовить безопасный cleanup/preflight tranche перед DB uniqueness hardening для `users.max_user_id`.

## Owner
Backend Platform / Data Reliability

## Status
Canonical

## Last Reviewed
2026-04-06

## Source Paths
- `/Users/mikhail/Projects/recruitsmart_admin/backend/apps/max_bot/candidate_flow.py`
- `/Users/mikhail/Projects/recruitsmart_admin/backend/domain/candidates/max_owner_preflight.py`
- `/Users/mikhail/Projects/recruitsmart_admin/scripts/max_owner_preflight.py`
- `/Users/mikhail/Projects/recruitsmart_admin/backend/domain/candidates/models.py`
- `/Users/mikhail/Projects/recruitsmart_admin/docs/adr/adr-0003-telegram-max-channel-ownership-and-session-invalidation.md`

## Non-goals
- Не добавлять DB uniqueness в этом tranche.
- Не менять recruiter/admin UX.
- Не делать broad rewrite candidate/channel flows.
- Не пытаться auto-merge кандидатов без явного evidence-based решения.

## Current Runtime Guard
- MAX runtime резолвит existing owner по normalized `trim(max_user_id)`, а не по raw строке.
- Если один incoming `max_user_id` уже матчится к нескольким candidate rows, runtime возвращает `ownership_ambiguous`, пишет audit event `max_link_rejected`, и не делает side effects.
- Invite reuse с тем же normalized owner остается идемпотентным. Reuse с другим owner остается explicit conflict.

## Audit Entry Point

Read-only CLI:

```bash
.venv/bin/python scripts/max_owner_preflight.py --format text --limit 50
.venv/bin/python scripts/max_owner_preflight.py --format json --limit 200 --fail-on-blockers
```

Что делает:
- ищет duplicate groups по normalized `trim(max_user_id)`
- ищет blank/whitespace anomalies
- ищет invite ownership mismatch и `messenger_platform=max` без usable owner
- считает blast radius по chat/invite/journey footprint
- возвращает `ready_for_unique_index=yes|no`

`--fail-on-blockers` нужен для preflight gate: exit code `2` означает, что unique index rollout пока запрещен.

## Raw SQL Checks

PostgreSQL reference queries для ручной проверки:

### 1. Duplicate normalized MAX owners

```sql
SELECT
    BTRIM(max_user_id) AS normalized_max_user_id,
    COUNT(*) AS candidate_count,
    ARRAY_AGG(id ORDER BY id) AS candidate_ids
FROM users
WHERE NULLIF(BTRIM(max_user_id), '') IS NOT NULL
GROUP BY BTRIM(max_user_id)
HAVING COUNT(*) > 1
ORDER BY candidate_count DESC, normalized_max_user_id;
```

### 2. Blank / whitespace anomalies

```sql
SELECT
    id,
    candidate_id,
    messenger_platform,
    max_user_id
FROM users
WHERE max_user_id IS NOT NULL
  AND (
      BTRIM(max_user_id) = ''
      OR max_user_id <> BTRIM(max_user_id)
  )
ORDER BY id;
```

### 3. Invite ownership mismatch

```sql
WITH latest_used_max_invite AS (
    SELECT DISTINCT ON (candidate_id)
        candidate_id,
        NULLIF(BTRIM(used_by_external_id), '') AS used_by_external_id,
        used_at
    FROM candidate_invite_tokens
    WHERE channel = 'max'
      AND NULLIF(BTRIM(used_by_external_id), '') IS NOT NULL
    ORDER BY candidate_id, used_at DESC NULLS LAST, id DESC
)
SELECT
    u.id,
    u.candidate_id,
    NULLIF(BTRIM(u.max_user_id), '') AS current_owner,
    i.used_by_external_id AS invite_owner,
    u.messenger_platform
FROM users u
JOIN latest_used_max_invite i ON i.candidate_id = u.candidate_id
WHERE NULLIF(BTRIM(u.max_user_id), '') IS DISTINCT FROM i.used_by_external_id
   OR (u.messenger_platform = 'max' AND NULLIF(BTRIM(u.max_user_id), '') IS NULL)
ORDER BY u.id;
```

### 4. Blast radius by duplicate-owner candidate set

```sql
WITH dup AS (
    SELECT BTRIM(max_user_id) AS normalized_max_user_id
    FROM users
    WHERE NULLIF(BTRIM(max_user_id), '') IS NOT NULL
    GROUP BY BTRIM(max_user_id)
    HAVING COUNT(*) > 1
),
dup_users AS (
    SELECT u.id, u.candidate_id
    FROM users u
    JOIN dup d ON d.normalized_max_user_id = BTRIM(u.max_user_id)
)
SELECT
    COUNT(DISTINCT du.id) AS duplicate_candidate_rows,
    COUNT(cm.id) FILTER (WHERE cm.channel = 'max') AS duplicate_max_chat_messages,
    COUNT(cit.id) FILTER (WHERE cit.channel = 'max' AND cit.status = 'used') AS duplicate_used_max_invites,
    COUNT(cjs.id) FILTER (WHERE cjs.status = 'active' AND cjs.entry_channel = 'max') AS duplicate_active_max_journeys
FROM dup_users du
LEFT JOIN chat_messages cm ON cm.candidate_id = du.id
LEFT JOIN candidate_invite_tokens cit ON cit.candidate_id = du.candidate_id
LEFT JOIN candidate_journey_sessions cjs ON cjs.candidate_id = du.id;
```

## Classification

| Case | Cleanup bucket | Blocks unique index | Expected action |
| --- | --- | --- | --- |
| `max_user_id` is only whitespace and candidate has no MAX evidence | `safe_auto_cleanup` | yes, until cleared | set `max_user_id = NULL` |
| `max_user_id` only has surrounding whitespace and trimmed value is not already owned | `safe_auto_cleanup` | yes, until trimmed | trim in place |
| Duplicate normalized owner, and exactly one row has authoritative MAX evidence | `safe_auto_cleanup` | yes, until secondaries cleared | keep authoritative row, clear secondary `max_user_id` values after snapshot verification |
| Duplicate normalized owner, and more than one row has MAX evidence | `manual_review_only` | yes | manual merge/relink decision |
| Latest used MAX invite points to a different external id than current candidate owner | `manual_review_only` | yes | reconcile invite ownership before cleanup |
| `messenger_platform = 'max'` but normalized owner is empty | `manual_review_only` | yes | restore/correct owner or downgrade preferred channel intentionally |

## Safe Execution Order

1. Freeze scope for the cleanup window.
2. Run the CLI in JSON mode and keep the output as the canonical snapshot for the batch.
3. Export the affected `users`, `candidate_invite_tokens`, `chat_messages`, and `candidate_journey_sessions` rows for the candidate ids in that snapshot.
4. Clear blank/whitespace-only `max_user_id` rows that have no MAX evidence.
5. Trim non-conflicting whitespace-only formatting issues.
6. Resolve safe duplicate groups where exactly one authoritative row exists and all secondary rows are operationally cold.
7. Stop and route the remaining blockers to manual review.
8. Re-run the CLI with `--fail-on-blockers`.
9. Only after `ready_for_unique_index=yes` move to schema hardening.

## Verification After Cleanup
- `scripts/max_owner_preflight.py --fail-on-blockers` exits `0`.
- No rows remain where `max_user_id <> BTRIM(max_user_id)` or `BTRIM(max_user_id) = ''`.
- No duplicate groups remain for normalized `trim(max_user_id)`.
- No invite mismatch cases remain.
- Sample repaired candidates can still open MAX flow without hitting `ownership_ambiguous`.

## Rollback Posture
- Cleanup runs in small explicit batches keyed by candidate ids, not as a repo-wide blind update.
- Every batch must keep a row-level snapshot of the original `users.max_user_id` and `candidate_invite_tokens.used_by_external_id`.
- Rollback restores those fields only for the touched candidate ids.
- Do not replay or rewrite chat history as part of rollback.
- If a batch creates uncertainty, stop the rollout, restore the snapshot, and re-run preflight before the next attempt.

## What Must Be True Before Unique Index
- `ready_for_unique_index=yes` in the CLI output.
- `blocking_checks=[]`.
- Every non-null `users.max_user_id` is already canonical: trimmed and non-empty.
- No duplicate normalized owner groups remain.
- No candidate still carries conflicting MAX invite ownership.
- `ownership_ambiguous` audit events are no longer firing for fresh runtime traffic.

## Migration Recommendation

Recommended order:

1. Keep the runtime ambiguity guard enabled.
2. Run the cleanup workflow until the CLI reports readiness.
3. Add the DB migration only after the data is canonical.
4. In the uniqueness migration, assert the same preconditions and fail closed if blockers still exist.

Index recommendation after cleanup:

```sql
CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS uq_users_max_user_id
ON users (max_user_id)
WHERE max_user_id IS NOT NULL;
```

This recommendation assumes preflight already enforced the canonical contract: no blanks and no surrounding whitespace. If that contract is not yet true, stop and finish cleanup first.
