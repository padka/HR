# RS-PR-014: Phase A Schema Merge Readiness

## Overall Verdict

`BLOCKED` for the **current mixed workspace**.

`MERGE READY AFTER SPLIT` for the **pure Phase A schema subset**.

Reason:

- the Phase A schema pack is now RFC-conformant and has live local PostgreSQL migration proof;
- the current worktree still mixes large out-of-scope runtime/API/frontend/docs hardening changes with the schema pack, so it must not be merged as one PR.

## In-Scope Files

Pure Phase A schema branch should contain only:

### Schema and ORM registration

- `backend/migrations/versions/0102_phase_a_schema_foundation.py`
- `backend/domain/models.py`
- `backend/domain/candidates/models.py`
- `backend/domain/messaging/__init__.py`
- `backend/domain/messaging/models.py`
- `backend/core/db.py`

### Schema-support contracts for future dual-write work

- `backend/domain/applications/__init__.py`
- `backend/domain/applications/contracts.py`
- `backend/domain/applications/events.py`
- `backend/domain/applications/idempotency.py`
- `backend/domain/applications/resolver.py`

### Phase A proof and profiling

- `scripts/profile_phase_a_backfill_readiness.py`
- `tests/test_phase_a_schema_metadata.py`
- `tests/test_phase_a_schema_migration.py`
- `tests/test_profile_phase_a_backfill_readiness.py`
- `tests/test_application_event_publisher_contract.py`
- `tests/test_application_resolver_contract.py`
- `tests/integration/test_migrations_postgres.py`

### Canonical design docs for this schema pack

- `docs/architecture/rfc/rs-rfc-007-phase-a-schema-and-api-contract-pack.md`
- `docs/architecture/implementation/rs-plan-006-unified-migration-blueprint.md`
- `docs/architecture/specs/rs-spec-010-primary-application-resolver-event-publisher-backfill.md`
- `docs/architecture/adr/rs-adr-002-application-requisition-lifecycle-event-log.md`
- `docs/architecture/adr/rs-adr-004-candidate-access-and-journey-surfaces.md`
- `docs/architecture/adr/rs-adr-005-messaging-delivery-model-and-channel-routing.md`

### Tactical lint gate support

- `pyproject.toml`

## Out-Of-Scope Files

These changes must stay out of the pure Phase A schema PR:

### Runtime hardening / live surface cleanup

- `backend/apps/admin_ui/app.py`
- `backend/apps/admin_api/webapp/__init__.py`
- `backend/apps/admin_api/webapp/auth.py`
- `backend/apps/admin_ui/routers/*`
- `backend/apps/admin_ui/services/*`
- `backend/apps/admin_ui/security.py`
- `backend/apps/admin_ui/state.py`
- `backend/apps/bot/*`
- `backend/apps/max_bot/*`
- `backend/core/messenger/*`
- `backend/core/settings.py`
- `backend/domain/candidates/actions.py`
- `backend/domain/candidates/services.py`
- `backend/domain/candidates/portal_service.py`
- `backend/domain/candidates/max_owner_preflight.py`
- `backend/domain/candidates/max_ownership.py`

### OpenAPI / frontend / runtime docs cleanup

- `scripts/check_openapi_drift.py`
- `scripts/export_openapi.py`
- `frontend/app/*`
- `docs/README.md`
- `docs/RELEASE_CHECKLIST.md`
- `docs/architecture/core-workflows.md`
- `docs/architecture/overview.md`
- `docs/architecture/runtime-topology.md`
- `docs/frontend/*`
- `docs/qa/*`
- `docs/security/*`
- `docs/runbooks/*`
- `docs/candidate_channels/*`
- `docs/architecture/supported_channels.md`

### Generated / unrelated artifacts

- `backend/apps/admin_api/openapi.json`
- `artifacts/audit/*`

## PostgreSQL Proof Status

`PASS`

Safe local/ephemeral proof used an already running local PostgreSQL database on `localhost:5432/rs_test`.

Verified:

- migration chain applies cleanly to head;
- `0102_phase_a_schema_foundation` is the final revision after upgrade in this workspace;
- all Phase A tables exist after migration;
- additive-only downgrade policy remains no-op by design.

One PostgreSQL-specific fix was required before proof passed:

- shortened the index identifier `ix_candidate_channel_identities_candidate_delivery_health_updated`
  to `ix_candidate_channel_identities_delivery_health_updated`
  in:
  - `backend/domain/models.py`
  - `backend/migrations/versions/0102_phase_a_schema_foundation.py`

## RFC Conformance Summary

Current implementation is conformant with `RS-RFC-007` and companion docs.

Confirmed absent:

- global unique `(channel, external_user_id)`
- active unique `(candidate_id, requisition_id)`
- `NOT NULL applications.requisition_id`
- `NOT NULL message_threads.application_id`
- `NOT NULL messages.application_id`
- mandatory policy row per candidate
- aggressive hard constraints on dirty legacy data

Confirmed present:

- `application_events.event_id` uniqueness
- `candidate_access_tokens.token_id` uniqueness
- `candidate_access_tokens.token_hash` uniqueness
- partial `candidate_access_tokens.start_param` uniqueness
- `candidate_access_sessions.session_id` uniqueness
- `messages.idempotency_key` uniqueness
- `message_deliveries.idempotency_key` uniqueness
- dedup pair ordering check and normalized pair uniqueness
- partial `candidate_contact_policies` uniqueness only where RFC allows it
- `channel_health_registry(channel, provider, runtime_surface)` uniqueness

## Gate Results

### Passed

- `./.venv/bin/python -m py_compile backend/domain/models.py backend/domain/candidates/models.py backend/domain/messaging/models.py backend/core/db.py backend/migrations/versions/0102_phase_a_schema_foundation.py backend/domain/applications/__init__.py backend/domain/applications/contracts.py backend/domain/applications/events.py backend/domain/applications/idempotency.py backend/domain/applications/resolver.py tests/test_phase_a_schema_metadata.py tests/test_phase_a_schema_migration.py tests/test_profile_phase_a_backfill_readiness.py tests/test_application_event_publisher_contract.py tests/test_application_resolver_contract.py tests/integration/test_migrations_postgres.py`
- `./.venv/bin/ruff check backend/domain/models.py backend/domain/candidates/models.py backend/domain/messaging/models.py backend/core/db.py backend/migrations/versions/0102_phase_a_schema_foundation.py tests/test_phase_a_schema_metadata.py tests/test_phase_a_schema_migration.py tests/test_profile_phase_a_backfill_readiness.py tests/integration/test_migrations_postgres.py pyproject.toml`
- `ENVIRONMENT=test ./.venv/bin/pytest tests/test_phase_a_schema_metadata.py tests/test_phase_a_schema_migration.py tests/test_profile_phase_a_backfill_readiness.py -q`
- `TEST_USE_POSTGRES=1 TEST_DATABASE_URL='postgresql+asyncpg://recruitsmart:recruitsmart@localhost:5432/rs_test' DATABASE_URL='postgresql+asyncpg://recruitsmart:recruitsmart@localhost:5432/rs_test' ENVIRONMENT=test REDIS_URL='' REDIS_NOTIFICATIONS_URL='' NOTIFICATION_BROKER=memory BOT_ENABLED=0 BOT_INTEGRATION_ENABLED=0 ADMIN_USER=admin ADMIN_PASSWORD=admin SESSION_SECRET='test-session-secret-0123456789abcdef0123456789abcd' ./.venv/bin/pytest tests/integration/test_migrations_postgres.py -q -rs`
- `./.venv/bin/python scripts/check_openapi_drift.py`

### Non-blocking warnings

- `pydantic` warning in test runs: `model_custom_emoji_id` protected namespace conflict

## Blockers

Current blocker is no longer PostgreSQL proof.

Current blocker is **branch hygiene only**:

- the workspace is still a mixed diff containing schema changes and unrelated runtime/API/frontend/docs cleanup;
- the pure Phase A subset must be split into its own commit/PR.

## Recommended Merge Order

1. Create a pure Phase A schema PR containing only the in-scope files listed above.
2. Keep runtime/API hardening and frontend/OpenAPI/docs cleanup in a separate PR.
3. Follow up later with ORM debt reduction:
   - extract new Phase A blocks out of legacy monoliths
   - narrow or remove the tactical `ruff` waiver in `pyproject.toml`

## Runtime Risk

Low for the schema pack itself:

- no runtime cutover
- no API behavior change
- no backfill
- no candidate portal/MAX runtime restoration

Main risk is organizational:

- if this mixed workspace is merged as-is, unrelated runtime hardening changes will ride along with the Phase A schema pack.
