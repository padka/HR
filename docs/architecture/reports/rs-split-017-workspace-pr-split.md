# RS-SPLIT-017 Workspace PR Split

## Current Workspace Status

The current workspace is mixed and must not be merged as one PR.

Inventory summary:

- Exact counts are intentionally omitted because parallel execution is still moving the mixed workspace.
- Use the stream manifests below as the source of truth for packaging.
- Active groups are `PR1` hardening/runtime/docs cleanup plus bounded MAX foundation, `PR2` pure Phase A schema foundation, `PR3` Phase B skeleton/adapters, `PR4` profiler/report/data-quality, and `PR5` persistent idempotency plus two bounded dual-write slices.

## Exact PR Groups

### PR 1: Hardening / Runtime / Docs Cleanup

- `.env.example`
- `.env.local.example`
- `CURRENT_PROGRAM_STATE.md`
- `PROJECT_CONTEXT_INDEX.md`
- `README.md`
- `REPOSITORY_WORKFLOW_GUIDE.md`
- `VERIFICATION_COMMANDS.md`
- `artifacts/verification/2026-03-25-tg-max-reliability/README.md`
- `artifacts/verification/2026-03-25-tg-max-reliability/regression-register.md`
- `artifacts/verification/2026-03-25-tg-max-reliability/release-blockers.md`
- `artifacts/verification/2026-03-25-tg-max-reliability/verification-snapshot.md`
- `backend/apps/admin_api/openapi.json`
- `backend/apps/admin_api/max_auth.py`
- `backend/apps/admin_api/max_launch.py`
- `backend/apps/admin_api/webapp/__init__.py`
- `backend/apps/admin_api/webapp/auth.py`
- `backend/apps/admin_ui/app.py`
- `backend/apps/admin_ui/routers/__init__.py`
- `backend/apps/admin_ui/routers/api_candidates.py`
- `backend/apps/admin_ui/routers/api_misc.py`
- `backend/apps/admin_ui/routers/candidate_portal.py`
- `backend/apps/admin_ui/routers/candidates.py`
- `backend/apps/admin_ui/routers/slots.py`
- `backend/apps/admin_ui/routers/system.py`
- `backend/apps/admin_ui/security.py`
- `backend/apps/admin_ui/services/candidate_chat_threads.py`
- `backend/apps/admin_ui/services/candidate_shared_access.py`
- `backend/apps/admin_ui/services/candidates/helpers.py`
- `backend/apps/admin_ui/services/candidates/lifecycle_use_cases.py`
- `backend/apps/admin_ui/services/candidates/write_intents.py`
- `backend/apps/admin_ui/services/chat.py`
- `backend/apps/admin_ui/services/max_sales_handoff.py`
- `backend/apps/admin_ui/services/messenger_health.py`
- `backend/apps/admin_ui/services/slots.py`
- `backend/apps/admin_ui/state.py`
- `backend/apps/bot/app.py`
- `backend/apps/bot/config.py`
- `backend/apps/bot/handlers/common.py`
- `backend/apps/bot/keyboards.py`
- `backend/apps/bot/services/base.py`
- `backend/apps/bot/services/broadcast.py`
- `backend/apps/bot/services/onboarding_flow.py`
- `backend/apps/max_bot/app.py`
- `backend/apps/max_bot/candidate_flow.py`
- `backend/core/messenger/bootstrap.py`
- `backend/core/messenger/channel_state.py`
- `backend/core/messenger/max_adapter.py`
- `backend/core/messenger/protocol.py`
- `backend/core/messenger/registry.py`
- `backend/core/messenger/reliability.py`
- `backend/core/settings.py`
- `backend/domain/candidates/actions.py`
- `backend/domain/candidates/max_owner_preflight.py`
- `backend/domain/candidates/max_ownership.py`
- `backend/domain/candidates/portal_service.py`
- `backend/domain/candidates/services.py`
- `docs/README.md`
- `docs/RELEASE_CHECKLIST.md`
- `docs/architecture/core-workflows.md`
- `docs/architecture/delivery-max-reliability-map.md`
- `docs/architecture/max-ownership-guard-plan.md`
- `docs/architecture/overview.md`
- `docs/architecture/runtime-topology.md`
- `docs/architecture/supported_channels.md`
- `docs/candidate_channels/MAX_BOT_READINESS_AUDIT_2026-04-09.md`
- `docs/candidate_channels/MAX_COMPLEX_SOLUTION_PLAN_2026-04-09.md`
- `docs/candidate_channels/MAX_CONDITIONAL_GO_REVIEW_2026-04-09.md`
- `docs/candidate_channels/MAX_EXECUTION_MASTER_PLAN_2026-04-09.md`
- `docs/candidate_channels/MAX_IMPLEMENTATION_SPEC_2026-04-09.md`
- `docs/candidate_channels/MAX_PILOT_LAUNCH_PLAYBOOK_2026-04-09.md`
- `docs/candidate_channels/MAX_RECRUITSMART_ARCHITECTURE_AND_ROADMAP_2026-04-09.md`
- `docs/candidate_channels/MAX_WAVE1_EXECUTION_BACKLOG_2026-04-09.md`
- `docs/candidate_channels/PRODUCT_REQUIREMENTS_CANDIDATE_PORTAL.md`
- `docs/frontend/README.md`
- `docs/frontend/route-map.md`
- `docs/frontend/screen-inventory.md`
- `docs/frontend/state-flows.md`
- `docs/qa/critical-flow-catalog.md`
- `docs/qa/master-test-plan.md`
- `docs/qa/release-gate-v2.md`
- `docs/qa/traceability-matrix.md`
- `docs/route-inventory.md`
- `docs/runbooks/max-live-local-bootstrap.md`
- `docs/runbooks/max-ownership-guard-plan.md`
- `docs/runbooks/portal-max-deeplink-failure.md`
- `docs/security/auth-and-token-model.md`
- `docs/security/trust-boundaries.md`
- `engine.md`
- `frontend/app/openapi.json`
- `frontend/app/src/api/candidate.test.ts`
- `frontend/app/src/api/candidate.ts`
- `frontend/app/src/api/schema.ts`
- `frontend/app/src/api/services/candidates.ts`
- `frontend/app/src/api/services/system.ts`
- `frontend/app/src/app/main.tsx`
- `frontend/app/src/app/routes/app/candidate-detail/CandidateActions.tsx`
- `frontend/app/src/app/routes/app/candidate-detail/CandidateDetailPage.tsx`
- `frontend/app/src/app/routes/app/candidate-detail/candidate-detail.api.ts`
- `frontend/app/src/app/routes/app/system.delivery-health.test.tsx`
- `frontend/app/src/app/routes/app/system.delivery-health.tsx`
- `frontend/app/src/app/routes/app/system.tsx`
- `frontend/app/src/app/routes/app/ui-cosmetics.test.tsx`
- `frontend/app/src/app/routes/candidate/journey.test.tsx`
- `frontend/app/src/app/routes/candidate/journey.tsx`
- `frontend/app/src/app/routes/candidate/start.test.tsx`
- `frontend/app/src/app/routes/candidate/start.tsx`
- `frontend/app/src/app/routes/candidate/webapp.ts`
- `frontend/app/src/shared/candidate-portal-session.ts`
- `max_bot.py`
- `scripts/check_openapi_drift.py`
- `scripts/dev_max_bot.sh`
- `scripts/dev_max_live.sh`
- `scripts/export_openapi.py`
- `tests/services/test_bot_keyboards.py`
- `tests/test_admin_candidate_chat_actions.py`
- `tests/test_admin_notifications_feed_api.py`
- `tests/test_admin_slots_api.py`
- `tests/test_admin_state_nullbot.py`
- `tests/test_admin_surface_hardening.py`
- `tests/test_bot_confirmation_flows.py`
- `tests/test_bot_integration_toggle.py`
- `tests/test_bot_test1_validation.py`
- `tests/test_broker_production_restrictions.py`
- `tests/test_candidate_actions.py`
- `tests/test_candidate_portal_api.py`
- `tests/test_chat_messages.py`
- `tests/test_docs_runtime_contract.py`
- `tests/test_hh_integration_actions.py`
- `tests/test_max_auth.py`
- `tests/test_max_bot.py`
- `tests/test_max_candidate_flow.py`
- `tests/test_max_launch_api.py`
- `tests/test_max_owner_preflight.py`
- `tests/test_max_sales_handoff.py`
- `tests/test_messenger.py`
- `tests/test_messenger_max_seam.py`
- `tests/test_notification_retry.py`
- `tests/test_openapi_tooling.py`
- `tests/test_outbox_notifications.py`
- `tests/test_prod_config_simple.py`
- `tests/test_runtime_surface_stabilization.py`
- `tests/test_session_cookie_config.py`
- `tests/test_sqlite_dev_schema.py`
- `tests/test_webapp_auth.py`

### PR 2: Pure Phase A Schema Foundation

- `backend/migrations/versions/0102_phase_a_schema_foundation.py`
- `backend/domain/models.py`
- `backend/domain/candidates/models.py`
- `backend/domain/messaging/__init__.py`
- `backend/domain/messaging/models.py`
- `backend/core/db.py`
- `tests/test_phase_a_schema_metadata.py`
- `tests/test_phase_a_schema_migration.py`
- `tests/integration/test_migrations_postgres.py`
- `docs/architecture/rfc/rs-rfc-007-phase-a-schema-and-api-contract-pack.md`
- `docs/architecture/implementation/rs-plan-006-unified-migration-blueprint.md`
- `docs/architecture/adr/rs-adr-002-application-requisition-lifecycle-event-log.md`
- `docs/architecture/adr/rs-adr-004-candidate-access-and-journey-surfaces.md`
- `docs/architecture/adr/rs-adr-005-messaging-delivery-model-and-channel-routing.md`
- `pyproject.toml`

### PR 3: Phase B Skeleton / Adapters

- `backend/domain/applications/__init__.py`
- `backend/domain/applications/contracts.py`
- `backend/domain/applications/events.py`
- `backend/domain/applications/idempotency.py`
- `backend/domain/applications/repositories.py`
- `backend/domain/applications/resolver.py`
- `backend/domain/applications/uow.py`
- `docs/architecture/specs/rs-spec-010-primary-application-resolver-event-publisher-backfill.md`
- `tests/test_application_event_publisher_contract.py`
- `tests/test_application_resolver_contract.py`
- `tests/test_application_sqlalchemy_repositories.py`
- `tests/test_application_event_store_sqlalchemy.py`

### PR 4: Profiler / Report / Data Quality

- `scripts/profile_phase_a_backfill_readiness.py`
- `tests/test_profile_phase_a_backfill_readiness.py`
- `docs/architecture/reports/rs-data-012-backfill-readiness-report.md`
- `docs/architecture/reports/rs-data-015-backfill-readiness-live-report.md`
- `docs/architecture/reports/rs-data-018-phase-b-manual-review-queues.md`
- `artifacts/audit/2026-04-16-api-inventory.csv`
- `artifacts/audit/2026-04-16-db-model-inventory.csv`
- `artifacts/audit/2026-04-16-risk-register.csv`
- `artifacts/audit/2026-04-16-techlead-audit.md`

### PR 5: Persistent Idempotency / Bounded Dual-Write Slices

- `backend/migrations/versions/0103_persistent_application_idempotency_keys.py`
- `backend/domain/applications/persistent_idempotency.py`
- `backend/apps/admin_ui/services/candidates/application_dual_write.py`
- `backend/apps/admin_ui/services/candidates/helpers.py` (PR5 hunks only; shared file with PR1)
- `backend/apps/admin_ui/services/candidates/lifecycle_use_cases.py` (PR5 hunks only; shared file with PR1)
- `backend/apps/admin_ui/routers/candidates.py` (PR5 hunks only; shared file with PR1)
- `backend/apps/admin_ui/routers/api_misc.py` (PR5 hunks only; shared file with PR1)
- `backend/core/settings.py` (PR5 hunks only; shared file with PR1)
- `tests/test_application_idempotency_migration.py`
- `tests/test_application_persistent_idempotency_repository.py`
- `tests/test_candidate_create_dual_write.py`
- `tests/test_candidate_status_dual_write.py`
- `docs/architecture/specs/rs-idemp-019-persistent-idempotency-and-concurrency.md`
- `Makefile`

### Ambiguous / Needs Human Decision

- `AGENTS.md`
- `docs/architecture/reports/rs-pr-014-phase-a-merge-readiness.md`
- `docs/architecture/reports/rs-autonomous-backend-execution-log.md`
- `docs/architecture/reports/rs-clean-pr-assembly-summary.md`
- `docs/architecture/reports/rs-split-017-workspace-pr-split.md`

## Dependency Order

1. PR 2: pure Phase A schema foundation
2. PR 3: Phase B skeleton/adapters on top of PR 2
3. PR 5: persistent idempotency plus the bounded candidate-create and candidate-status dual-write slices on top of PR 3
4. PR 4: profiler/report/data-quality pack, preferably after PR 2
5. PR 1: hardening/runtime/docs cleanup as a separate stream

## Risks

- The current workspace still mixes additive schema, resolver skeleton, runtime hardening, frontend/OpenAPI cleanup, report artifacts, and PR5 dual-write work.
- `backend/domain/models.py` and `backend/domain/candidates/models.py` remain legacy ORM monoliths; PR 2 currently relies on a tactical `ruff` waiver in `pyproject.toml`.
- `docs/architecture/specs/rs-spec-010-primary-application-resolver-event-publisher-backfill.md` belongs to PR 3 and should move with the resolver/event-publisher skeleton, not with Phase A schema foundation.
- `AGENTS.md` remains repo-wide workflow guidance and should not be packed automatically.
- `backend/apps/admin_ui/services/candidates/helpers.py`, `backend/apps/admin_ui/services/candidates/lifecycle_use_cases.py`, `backend/apps/admin_ui/routers/candidates.py`, `backend/apps/admin_ui/routers/api_misc.py`, and `backend/core/settings.py` now require explicit hunk-splitting between PR1 and PR5; do not cherry-pick those files wholesale.
- `Makefile` now carries the live PostgreSQL proof target for PR 5 and should move with that slice only if you want the one-command harness update in the same PR.

## Recommended Commands For Clean Branches

```bash
BASE_REF=$(git merge-base HEAD origin/main)

# PR 2

git worktree add ../recruitsmart-pr2 "$BASE_REF"
cd ../recruitsmart-pr2
git checkout -b codex/rs-pr2-phase-a-schema

# PR 3

git worktree add ../recruitsmart-pr3 "$BASE_REF"
cd ../recruitsmart-pr3
git checkout -b codex/rs-pr3-phase-b-prep

# PR 5

git worktree add ../recruitsmart-pr5 "$BASE_REF"
cd ../recruitsmart-pr5
git checkout -b codex/rs-pr5-persistent-idempotency

# PR 4

git worktree add ../recruitsmart-pr4 "$BASE_REF"
cd ../recruitsmart-pr4
git checkout -b codex/rs-pr4-data-report

# PR 1

git worktree add ../recruitsmart-pr1 "$BASE_REF"
cd ../recruitsmart-pr1
git checkout -b codex/rs-pr1-hardening
```

Apply patch bundles only for PR 2/3/4/5. Recreate PR 1 from this manifest in a fresh worktree.

## Gate Commands Per PR

### PR 1 hardening/runtime/docs cleanup

```bash
./.venv/bin/python scripts/check_openapi_drift.py
ENVIRONMENT=test REDIS_URL='' REDIS_NOTIFICATIONS_URL='' NOTIFICATION_BROKER=memory BOT_ENABLED=0 BOT_INTEGRATION_ENABLED=0 ADMIN_USER=admin ADMIN_PASSWORD=admin SESSION_SECRET='test-session-secret-0123456789abcdef0123456789abcd' BOT_CALLBACK_SECRET='test-bot-callback-secret-0123456789abcdef012' ./.venv/bin/pytest tests/test_admin_surface_hardening.py tests/test_runtime_surface_stabilization.py tests/test_openapi_tooling.py tests/test_docs_runtime_contract.py -q
npm --prefix frontend/app run typecheck
```

### PR 2 pure Phase A schema foundation

```bash
./.venv/bin/python -m py_compile backend/domain/models.py backend/domain/candidates/models.py backend/domain/messaging/models.py backend/core/db.py backend/migrations/versions/0102_phase_a_schema_foundation.py tests/test_phase_a_schema_metadata.py tests/test_phase_a_schema_migration.py tests/integration/test_migrations_postgres.py
./.venv/bin/ruff check backend/domain/models.py backend/domain/candidates/models.py backend/domain/messaging/models.py backend/core/db.py backend/migrations/versions/0102_phase_a_schema_foundation.py tests/test_phase_a_schema_metadata.py tests/test_phase_a_schema_migration.py tests/integration/test_migrations_postgres.py pyproject.toml
ENVIRONMENT=test ./.venv/bin/pytest tests/test_phase_a_schema_metadata.py tests/test_phase_a_schema_migration.py -q
TEST_USE_POSTGRES=1 TEST_DATABASE_URL='postgresql+asyncpg://recruitsmart:recruitsmart@localhost:5432/rs_test' DATABASE_URL='postgresql+asyncpg://recruitsmart:recruitsmart@localhost:5432/rs_test' ENVIRONMENT=test REDIS_URL='' REDIS_NOTIFICATIONS_URL='' NOTIFICATION_BROKER=memory BOT_ENABLED=0 BOT_INTEGRATION_ENABLED=0 ADMIN_USER=admin ADMIN_PASSWORD=admin SESSION_SECRET='test-session-secret-0123456789abcdef0123456789abcd' ./.venv/bin/pytest tests/integration/test_migrations_postgres.py -q -rs
./.venv/bin/python scripts/check_openapi_drift.py
```

### PR 3 Phase B skeleton/adapters

```bash
./.venv/bin/python -m py_compile backend/domain/applications/__init__.py backend/domain/applications/contracts.py backend/domain/applications/events.py backend/domain/applications/idempotency.py backend/domain/applications/repositories.py backend/domain/applications/resolver.py backend/domain/applications/uow.py tests/test_application_event_publisher_contract.py tests/test_application_resolver_contract.py tests/test_application_sqlalchemy_repositories.py tests/test_application_event_store_sqlalchemy.py
./.venv/bin/ruff check backend/domain/applications/__init__.py backend/domain/applications/contracts.py backend/domain/applications/events.py backend/domain/applications/idempotency.py backend/domain/applications/repositories.py backend/domain/applications/resolver.py backend/domain/applications/uow.py tests/test_application_event_publisher_contract.py tests/test_application_resolver_contract.py tests/test_application_sqlalchemy_repositories.py tests/test_application_event_store_sqlalchemy.py
ENVIRONMENT=test ./.venv/bin/pytest tests/test_application_event_publisher_contract.py tests/test_application_resolver_contract.py tests/test_application_sqlalchemy_repositories.py tests/test_application_event_store_sqlalchemy.py -q
./.venv/bin/python scripts/check_openapi_drift.py
rg -n "application_events|resolver|idempotency" backend/apps backend/domain -S
```

### PR 4 profiler/report/data-quality

```bash
./.venv/bin/python -m py_compile scripts/profile_phase_a_backfill_readiness.py tests/test_profile_phase_a_backfill_readiness.py
./.venv/bin/ruff check scripts/profile_phase_a_backfill_readiness.py tests/test_profile_phase_a_backfill_readiness.py
ENVIRONMENT=test ./.venv/bin/pytest tests/test_profile_phase_a_backfill_readiness.py -q
rg -n "Private Candidate|max-private|\\+7999" scripts/profile_phase_a_backfill_readiness.py tests/test_profile_phase_a_backfill_readiness.py docs/architecture/reports -S
```

### PR 5 persistent idempotency / first dual-write slice

```bash
./.venv/bin/python -m py_compile backend/migrations/versions/0103_persistent_application_idempotency_keys.py backend/domain/applications/persistent_idempotency.py backend/apps/admin_ui/services/candidates/application_dual_write.py backend/apps/admin_ui/services/candidates/helpers.py backend/apps/admin_ui/routers/api_misc.py backend/core/settings.py tests/test_application_idempotency_migration.py tests/test_application_persistent_idempotency_repository.py tests/test_candidate_create_dual_write.py
./.venv/bin/ruff check backend/migrations/versions/0103_persistent_application_idempotency_keys.py backend/domain/applications/persistent_idempotency.py backend/apps/admin_ui/services/candidates/application_dual_write.py tests/test_application_idempotency_migration.py tests/test_application_persistent_idempotency_repository.py tests/test_candidate_create_dual_write.py
ENVIRONMENT=test ./.venv/bin/pytest tests/test_application_idempotency_migration.py tests/test_application_persistent_idempotency_repository.py tests/test_candidate_create_dual_write.py -q
./.venv/bin/python scripts/check_openapi_drift.py
make test-postgres-proof
rg -n "CANDIDATE_CREATE_DUAL_WRITE_ENABLED|application_events|application_idempotency_keys" backend tests docs -S
```
