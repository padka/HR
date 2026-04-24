-- Read-only staging schema compatibility checks for the hardening release.
-- Usage:
--   psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f scripts/staging_schema_compatibility.sql
--
-- Do not run migrations from this script. It opens a read-only transaction and
-- reports aggregate/schema facts only.

BEGIN TRANSACTION READ ONLY;

SELECT 'alembic_version' AS check_name, version_num
FROM alembic_version
ORDER BY version_num;

SELECT
  'uq_users_max_user_id_nonempty_exists' AS check_name,
  EXISTS (
    SELECT 1
    FROM pg_indexes
    WHERE schemaname = current_schema()
      AND tablename = 'users'
      AND indexname = 'uq_users_max_user_id_nonempty'
  ) AS ok;

SELECT
  'max_user_id_duplicate_groups' AS check_name,
  COUNT(*) AS duplicate_groups
FROM (
  SELECT max_user_id
  FROM users
  WHERE NULLIF(BTRIM(max_user_id), '') IS NOT NULL
  GROUP BY max_user_id
  HAVING COUNT(*) > 1
) duplicates;

SELECT
  'telegram_id_duplicate_groups' AS check_name,
  COUNT(*) AS duplicate_groups
FROM (
  SELECT telegram_id
  FROM users
  WHERE telegram_id IS NOT NULL
  GROUP BY telegram_id
  HAVING COUNT(*) > 1
) duplicates;

SELECT
  'telegram_user_id_duplicate_groups' AS check_name,
  COUNT(*) AS duplicate_groups
FROM (
  SELECT telegram_user_id
  FROM users
  WHERE telegram_user_id IS NOT NULL
  GROUP BY telegram_user_id
  HAVING COUNT(*) > 1
) duplicates;

SELECT
  'users_manual_availability_columns' AS check_name,
  ARRAY_AGG(column_name ORDER BY column_name) AS present_columns
FROM information_schema.columns
WHERE table_schema = current_schema()
  AND table_name = 'users'
  AND column_name IN (
    'manual_slot_from',
    'manual_slot_to',
    'manual_slot_comment',
    'manual_slot_timezone',
    'manual_slot_requested_at',
    'manual_slot_response_at'
  );

SELECT
  'slot_reservation_locks_indexes' AS check_name,
  ARRAY_AGG(indexname ORDER BY indexname) AS present_indexes
FROM pg_indexes
WHERE schemaname = current_schema()
  AND tablename = 'slot_reservation_locks'
  AND indexname IN (
    'uq_slot_reservation_locks_key',
    'ix_slot_reservation_locks_candidate_id'
  );

SELECT
  'hh_sync_jobs_columns' AS check_name,
  ARRAY_AGG(column_name ORDER BY column_name) AS present_columns
FROM information_schema.columns
WHERE table_schema = current_schema()
  AND table_name = 'hh_sync_jobs'
  AND column_name IN (
    'id',
    'connection_id',
    'job_type',
    'direction',
    'entity_type',
    'entity_external_id',
    'status',
    'idempotency_key',
    'attempts',
    'payload_json',
    'last_error',
    'next_retry_at',
    'started_at',
    'finished_at',
    'created_at',
    'candidate_id',
    'result_json',
    'failure_code'
  );

SELECT
  'hh_sync_jobs_indexes' AS check_name,
  ARRAY_AGG(indexname ORDER BY indexname) AS present_indexes
FROM pg_indexes
WHERE schemaname = current_schema()
  AND tablename = 'hh_sync_jobs'
  AND indexname IN (
    'ix_hh_sync_jobs_status',
    'ix_hh_sync_jobs_entity',
    'ix_hh_sync_jobs_candidate',
    'uq_hh_sync_jobs_idempotency'
  );

SELECT
  'hh_sync_jobs_counts_by_status' AS check_name,
  status,
  COUNT(*) AS jobs
FROM hh_sync_jobs
GROUP BY status
ORDER BY status;

SELECT
  'future_free_slots_count' AS check_name,
  COUNT(*) AS slots
FROM slots
WHERE start_utc > NOW()
  AND LOWER(status) = 'free';

ROLLBACK;
