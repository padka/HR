# PROJECT AUDIT 01 — Overview
## Дата: 2026-03-14

## Методология и границы

- Аудит собран по текущему workspace-состоянию, включая незакоммиченные исходники.
- Из глубокого аудита исключены только генерируемые и внешние каталоги: `.venv*`, `.claude-code`, `node_modules`, `dist`, `build`, `.next`, `artifacts`, `.local`, кэши и `frontend/app/test-results`.
- Покрытие аудита: 915 файлов, 236619 строк.

## 0. Статистика проекта

| Метрика | Значение |
|---|---:|
| Всего файлов в аудите | 915 |
| Общее количество строк | 236619 |
| Python файлов | 571 |
| TS/TSX/JS файлов | 120 |
| CSS файлов | 19 |
| Markdown файлов | 175 |
| API-эндпоинтов FastAPI | 295 |
| TypeScript типов/интерфейсов | 323 |
| Файлов > 500 строк | 104 |
| Самый большой файл | `frontend/app/src/theme/global.css` (10104) |

### Крупнейшие файлы

| Файл | Строк | Категория |
|---|---:|---|
| `frontend/app/src/theme/global.css` | 10104 | styles |
| `frontend/app/package-lock.json` | 8553 | config |
| `backend/apps/bot/services.py` | 7627 | misc |
| `frontend/app/openapi.json` | 5915 | config |
| `frontend/app/src/api/schema.ts` | 4828 | frontend-api |
| `backend/apps/admin_ui/services/candidates.py` | 3984 | backend-services |
| `backend/apps/admin_ui/routers/api.py` | 3638 | backend-routers |
| `frontend/app/src/app/routes/app/candidate-detail.tsx` | 3458 | frontend-routes |
| `backend/apps/admin_ui/static/css/liquid-glass-integration.css` | 2552 | styles |
| `backend/core/ai/service.py` | 2478 | backend-core |
| `backend/apps/admin_ui/services/dashboard.py` | 2292 | backend-services |
| `backend/apps/admin_ui/services/slots.py` | 2041 | backend-services |
| `docs/archive/qa/QA_COMPREHENSIVE_REPORT.md` | 2006 | docs |
| `docs/archive/REDESIGN_STRATEGY.md` | 1764 | docs |
| `docs/archive/features/dashboard/DASHBOARD_CHANGELOG.md` | 1706 | docs |
| `frontend/app/src/app/routes/app/messenger.tsx` | 1612 | frontend-routes |
| `backend/domain/repositories.py` | 1583 | backend-domain |
| `frontend/app/src/app/routes/app/slots.tsx` | 1559 | frontend-routes |
| `backend/apps/admin_ui/routers/candidates.py` | 1422 | backend-routers |
| `tests/test_admin_candidate_schedule_slot.py` | 1416 | tests |

## 1. Конфигурация

### `frontend/app/package.json`

- `name`: `recruitsmart-admin-spa`
- Production dependencies: 21
- DevDependencies: 22
- Скрипты:
  - `dev` → `vite`
  - `build` → `vite build`
  - `bundle:check` → `node ./scripts/check-bundle-budgets.mjs`
  - `build:verify` → `npm run build && npm run bundle:check`
  - `preview` → `vite preview`
  - `lint` → `eslint --ext .ts,.tsx src`
  - `typecheck` → `tsc --noEmit`
  - `test` → `vitest run --passWithNoTests`
  - `test:e2e` → `npm run build && playwright test`
  - `test:e2e:smoke` → `npm run build && playwright test tests/e2e/smoke.spec.ts tests/e2e/mobile-smoke.spec.ts`
- Dependencies:
  - `@fullcalendar/core`: `^6.1.20`
  - `@fullcalendar/daygrid`: `^6.1.20`
  - `@fullcalendar/interaction`: `^6.1.20`
  - `@fullcalendar/react`: `^6.1.20`
  - `@fullcalendar/timegrid`: `^6.1.20`
  - `@hookform/resolvers`: `^5.2.2`
  - `@tanstack/react-query`: `^5.64.0`
  - `@tanstack/react-query-devtools`: `^5.64.0`
  - `@tanstack/react-router`: `^1.74.8`
  - `@tanstack/react-router-devtools`: `^1.74.8`
  - `@xyflow/react`: `^12.10.0`
  - `autoprefixer`: `^10.4.23`
  - `clsx`: `^2.1.1`
  - `framer-motion`: `^12.36.0`
  - `lucide-react`: `^0.469.0`
  - `openapi-typescript`: `^7.10.1`
  - `react`: `^18.3.1`
  - `react-dom`: `^18.3.1`
  - `react-hook-form`: `^7.71.1`
  - `zod`: `^4.3.6`
  - `zustand`: `^5.0.2`
- DevDependencies:
  - `@axe-core/playwright`: `^4.9.0`
  - `@playwright/test`: `^1.48.2`
  - `@testing-library/jest-dom`: `^6.6.3`
  - `@testing-library/react`: `^16.3.0`
  - `@testing-library/user-event`: `^14.6.1`
  - `@types/node`: `^22.9.1`
  - `@types/react`: `^18.3.11`
  - `@types/react-dom`: `^18.3.1`
  - `@typescript-eslint/eslint-plugin`: `^8.54.0`
  - `@typescript-eslint/parser`: `^8.54.0`
  - `@vitejs/plugin-react`: `^4.3.4`
  - `eslint`: `^9.39.2`
  - `eslint-config-standard-with-typescript`: `^20.0.0`
  - `eslint-plugin-import`: `^2.31.0`
  - `eslint-plugin-n`: `^16.6.2`
  - `eslint-plugin-promise`: `^6.6.0`
  - `eslint-plugin-react`: `^7.37.1`
  - `eslint-plugin-react-hooks`: `^5.0.0`
  - `jsdom`: `^24.1.3`
  - `typescript`: `^5.6.3`
  - `vite`: `^7.3.1`
  - `vitest`: `^4.0.18`

### `pyproject.toml`

- `name`: `hr-admin-ui`
- Python dependencies: 22
  - `aiofiles==23.2.1`
  - `aiohttp==3.13.3`
  - `aiogram==3.24.0`
  - `APScheduler==3.11.2`
  - `asyncpg==0.31.0`
  - `fastapi==0.134.0`
  - `starlette==0.52.1`
  - `uvicorn[standard]==0.30.6`
  - `itsdangerous==2.2.0`
  - `Jinja2==3.1.6`
  - `python-multipart==0.0.22`
  - `passlib[bcrypt]==1.7.4`
  - `PyJWT[crypto]==2.10.1`
  - `psycopg[binary]==3.2.3`
  - `redis==7.1.0`
  - `slowapi==0.1.9`
  - `sqladmin==0.22.0`
  - `SQLAlchemy[asyncio]==2.0.45`
  - `greenlet==3.2.4`
  - `starlette-wtf==0.4.5`
  - `pypdf==6.7.4`
  - `prometheus-client==0.21.0`
- optional `dev` (21): `aiosqlite==0.20.0`, `aiohttp==3.13.3`, `aiogram==3.24.0`, `redis==7.1.0`, `httpx==0.28.1`, `pytest==9.0.2`, `pytest-asyncio==1.3.0`, `playwright==1.57.0`, `ruff==0.14.11`, `black==25.12.0`, `isort==7.0.0`, `mypy==1.19.1`, `pre-commit==4.5.1`, `alembic==1.18.1`, `fakeredis==2.33.0`, `APScheduler==3.11.2`, `sqladmin==0.22.0`, `sentry-sdk[fastapi]==2.19.2`, `pypdf==6.7.4`, `python-multipart==0.0.22`, `Jinja2==3.1.6`

### `frontend/app/tsconfig.json`

- `jsx`: `react-jsx`
- `baseUrl`: `.`
- `paths`: `{"@/*": ["src/*"]}`
- `strict`: `True`
- `moduleResolution`: `Bundler`

### Tailwind

- Tailwind config в проекте не найден. Фронтенд использует обычные CSS-файлы и Framer Motion поверх Vite/React.

### Остальные конфиги

- `frontend/app/vite.config.ts` — Назначение требует ручного ревью.
- `frontend/app/vitest.config.ts` — Назначение требует ручного ревью.
- `frontend/app/playwright.config.ts` — Назначение требует ручного ревью.
- `frontend/app/eslint.config.js` — Назначение требует ручного ревью.
- `.pre-commit-config.yaml` — Конфигурационный файл `.pre-commit-config`.
  - Верхнеуровневые ключи: `repos`
- `docker-compose.yml` — Конфигурационный файл `docker-compose`.
  - Верхнеуровневые ключи: `x-app-env`, `services`, `volumes`, `networks`
- `.github/workflows/ci.yml` — Конфигурационный файл `ci`.
  - Верхнеуровневые ключи: `name`, `on`, `jobs`
- `.github/workflows/ci.yaml` — Конфигурационный файл `ci`.
  - Верхнеуровневые ключи: `name`, `on`, `jobs`
- `.github/workflows/dependency-audit.yml` — Конфигурационный файл `dependency-audit`.
  - Верхнеуровневые ключи: `name`, `on`, `jobs`
- `.github/workflows/migration-contract.yml` — Конфигурационный файл `migration-contract`.
  - Верхнеуровневые ключи: `name`, `on`, `jobs`
- `.github/workflows/ui-preview.yml` — Конфигурационный файл `ui-preview`.
  - Верхнеуровневые ключи: `name`, `on`, `jobs`
- `.github/dependabot.yml` — Конфигурационный файл `dependabot`.
  - Верхнеуровневые ключи: `version`, `updates`

## 2. File tree

```text
.claude/agents/admin-panel-frontend-dev.md
.claude/agents/qa-frontend-tester.md
.claude/agents/ui-ux-designer.md
.claude/launch.json
.claude/settings.local.json
.codex/system.md
.env.development.example
.env.example
.env.local
.env.local.example
.github/dependabot.yml
.github/workflows/ci.yaml
.github/workflows/ci.yml
.github/workflows/dependency-audit.yml
.github/workflows/migration-contract.yml
.github/workflows/ui-preview.yml
.pre-commit-config.yaml
.vscode/extensions.json
.vscode/settings.json
AGENTS.md
CURRENT_PROGRAM_STATE.md
PROJECT_CONTEXT_INDEX.md
README.md
REPOSITORY_WORKFLOW_GUIDE.md
VERIFICATION_COMMANDS.md
audit/ACTION_PLAN.md
audit/CSS_SIZE.md
audit/DIAGNOSIS.md
audit/ESTIMATES.md
audit/INVENTORY.json
audit/INVENTORY.md
audit/METRICS.md
audit/QUALITY.md
audit/REPORT.md
audit/SECURITY.md
audit/collect_metrics.py
audit/generate_inventory.py
audit/metrics.json
audit/run_smoke_checks.py
backend/__init__.py
backend/apps/__init__.py
backend/apps/admin_api/__init__.py
backend/apps/admin_api/admin.py
backend/apps/admin_api/hh_integration.py
backend/apps/admin_api/hh_sync.py
backend/apps/admin_api/main.py
backend/apps/admin_api/slot_assignments.py
backend/apps/admin_api/webapp/__init__.py
backend/apps/admin_api/webapp/auth.py
backend/apps/admin_api/webapp/recruiter_routers.py
backend/apps/admin_api/webapp/routers.py
backend/apps/admin_ui/__init__.py
backend/apps/admin_ui/app.py
backend/apps/admin_ui/background_tasks.py
backend/apps/admin_ui/calendar_hub.py
backend/apps/admin_ui/config.py
backend/apps/admin_ui/middleware.py
backend/apps/admin_ui/perf/__init__.py
backend/apps/admin_ui/perf/cache/__init__.py
backend/apps/admin_ui/perf/cache/keys.py
backend/apps/admin_ui/perf/cache/microcache.py
backend/apps/admin_ui/perf/cache/policy.py
backend/apps/admin_ui/perf/cache/readthrough.py
backend/apps/admin_ui/perf/degraded/__init__.py
backend/apps/admin_ui/perf/degraded/allowlist.py
backend/apps/admin_ui/perf/degraded/middleware.py
backend/apps/admin_ui/perf/degraded/state.py
backend/apps/admin_ui/perf/limits/__init__.py
backend/apps/admin_ui/perf/limits/refresh_limiter.py
backend/apps/admin_ui/perf/metrics/__init__.py
backend/apps/admin_ui/perf/metrics/cache.py
backend/apps/admin_ui/perf/metrics/context.py
backend/apps/admin_ui/perf/metrics/db.py
backend/apps/admin_ui/perf/metrics/db_metrics.py
backend/apps/admin_ui/perf/metrics/http.py
backend/apps/admin_ui/perf/metrics/http_metrics.py
backend/apps/admin_ui/perf/metrics/prometheus.py
backend/apps/admin_ui/presence.py
backend/apps/admin_ui/routers/__init__.py
backend/apps/admin_ui/routers/ai.py
backend/apps/admin_ui/routers/api.py
backend/apps/admin_ui/routers/assignments.py
backend/apps/admin_ui/routers/auth.py
backend/apps/admin_ui/routers/candidates.py
backend/apps/admin_ui/routers/cities.py
backend/apps/admin_ui/routers/content_api.py
backend/apps/admin_ui/routers/dashboard.py
backend/apps/admin_ui/routers/detailization.py
backend/apps/admin_ui/routers/directory.py
backend/apps/admin_ui/routers/hh_integration.py
backend/apps/admin_ui/routers/knowledge_base.py
backend/apps/admin_ui/routers/message_templates.py
backend/apps/admin_ui/routers/metrics.py
backend/apps/admin_ui/routers/profile.py
backend/apps/admin_ui/routers/profile_api.py
backend/apps/admin_ui/routers/questions.py
backend/apps/admin_ui/routers/recruiters.py
backend/apps/admin_ui/routers/recruiters_api_example.py
backend/apps/admin_ui/routers/regions.py
backend/apps/admin_ui/routers/reschedule_requests.py
backend/apps/admin_ui/routers/simulator.py
backend/apps/admin_ui/routers/slot_assignments.py
backend/apps/admin_ui/routers/slot_assignments_api.py
backend/apps/admin_ui/routers/slots.py
backend/apps/admin_ui/routers/system.py
backend/apps/admin_ui/routers/workflow.py
backend/apps/admin_ui/schemas.py
backend/apps/admin_ui/security.py
backend/apps/admin_ui/services/__init__.py
backend/apps/admin_ui/services/bot_service.py
backend/apps/admin_ui/services/builder_graph.py
backend/apps/admin_ui/services/calendar_events.py
backend/apps/admin_ui/services/calendar_tasks.py
backend/apps/admin_ui/services/candidate_chat_threads.py
backend/apps/admin_ui/services/candidates.py
backend/apps/admin_ui/services/chat.py
backend/apps/admin_ui/services/chat_meta.py
backend/apps/admin_ui/services/cities.py
backend/apps/admin_ui/services/cities_hh.py
backend/apps/admin_ui/services/city_reminder_policy.py
backend/apps/admin_ui/services/dashboard.py
backend/apps/admin_ui/services/dashboard_calendar.py
backend/apps/admin_ui/services/detailization.py
backend/apps/admin_ui/services/kpis.py
backend/apps/admin_ui/services/max_sales_handoff.py
backend/apps/admin_ui/services/message_templates.py
backend/apps/admin_ui/services/message_templates_presets.py
backend/apps/admin_ui/services/notifications.py
backend/apps/admin_ui/services/notifications_ops.py
backend/apps/admin_ui/services/questions.py
backend/apps/admin_ui/services/recruiter_access.py
backend/apps/admin_ui/services/recruiter_plan.py
backend/apps/admin_ui/services/recruiters.py
backend/apps/admin_ui/services/reminders_ops.py
backend/apps/admin_ui/services/reschedule_intents.py
backend/apps/admin_ui/services/slots.py
backend/apps/admin_ui/services/slots/__init__.py
backend/apps/admin_ui/services/slots/bot.py
backend/apps/admin_ui/services/slots/bulk.py
backend/apps/admin_ui/services/slots/core.py
backend/apps/admin_ui/services/slots/crud.py
backend/apps/admin_ui/services/staff_chat.py
backend/apps/admin_ui/services/test_builder_preview.py
backend/apps/admin_ui/services/vacancies.py
backend/apps/admin_ui/state.py
backend/apps/admin_ui/static/css/design-system.css
backend/apps/admin_ui/static/css/forms.css
backend/apps/admin_ui/static/css/glass-surfaces.css
backend/apps/admin_ui/static/css/liquid-glass-integration.css
backend/apps/admin_ui/static/css/liquid-glass.css
backend/apps/admin_ui/static/css/theme-tokens.css
backend/apps/admin_ui/static/js/modules/slots-notion.js
backend/apps/admin_ui/timezones.py
backend/apps/admin_ui/utils.py
backend/apps/admin_ui/views/__init__.py
backend/apps/admin_ui/views/tests.py
backend/apps/bot/MessageStyleGuide.md
backend/apps/bot/__init__.py
backend/apps/bot/api_client.py
backend/apps/bot/app.py
backend/apps/bot/backend_client.py
backend/apps/bot/broker.py
backend/apps/bot/city_registry.py
backend/apps/bot/config.py
backend/apps/bot/defaults.py
backend/apps/bot/events.py
backend/apps/bot/handlers/__init__.py
backend/apps/bot/handlers/attendance.py
backend/apps/bot/handlers/common.py
backend/apps/bot/handlers/interview.py
backend/apps/bot/handlers/recruiter.py
backend/apps/bot/handlers/recruiter_actions.py
backend/apps/bot/handlers/slot_assignments.py
backend/apps/bot/handlers/slots.py
backend/apps/bot/handlers/test1.py
backend/apps/bot/handlers/test2.py
backend/apps/bot/jinja_renderer.py
backend/apps/bot/keyboards.py
backend/apps/bot/main.py
backend/apps/bot/metrics.py
backend/apps/bot/middleware.py
backend/apps/bot/notifications/__init__.py
backend/apps/bot/notifications/bootstrap.py
backend/apps/bot/recruiter_service.py
backend/apps/bot/reminders.py
backend/apps/bot/runtime_config.py
backend/apps/bot/security.py
backend/apps/bot/services.py
backend/apps/bot/slot_assignment_flow.py
backend/apps/bot/state_store.py
backend/apps/bot/template_provider.py
backend/apps/bot/test1_validation.py
backend/apps/bot/utils/text.py
backend/apps/hh_integration_webhooks.py
backend/apps/max_bot/__init__.py
backend/apps/max_bot/app.py
backend/core/__init__.py
backend/core/ai/__init__.py
backend/core/ai/candidate_scorecard.py
backend/core/ai/context.py
backend/core/ai/interview_script_builder.py
backend/core/ai/knowledge_base.py
backend/core/ai/llm_script_generator.py
backend/core/ai/prompts.py
backend/core/ai/providers/__init__.py
backend/core/ai/providers/base.py
backend/core/ai/providers/fake.py
backend/core/ai/providers/openai.py
backend/core/ai/redaction.py
backend/core/ai/schemas.py
backend/core/ai/service.py
backend/core/audit.py
backend/core/auth.py
backend/core/bootstrap.py
backend/core/cache.py
backend/core/cache_decorators.py
backend/core/content_updates.py
backend/core/db.py
backend/core/dependencies.py
backend/core/env.py
backend/core/error_handler.py
backend/core/guards.py
backend/core/logging.py
backend/core/messenger/__init__.py
backend/core/messenger/bootstrap.py
backend/core/messenger/max_adapter.py
backend/core/messenger/protocol.py
backend/core/messenger/registry.py
backend/core/messenger/telegram_adapter.py
backend/core/metrics.py
backend/core/microcache.py
backend/core/passwords.py
backend/core/query_optimization.py
backend/core/redis_factory.py
backend/core/repository/__init__.py
backend/core/repository/base.py
backend/core/repository/protocols.py
backend/core/result.py
backend/core/sanitizers.py
backend/core/scoping.py
backend/core/settings.py
backend/core/sqlite_dev_schema.py
backend/core/time_utils.py
backend/core/timezone.py
backend/core/timezone_service.py
backend/core/timezone_utils.py
backend/core/uow.py
backend/domain/ai/__init__.py
backend/domain/ai/models.py
backend/domain/analytics.py
backend/domain/analytics_models.py
backend/domain/auth_account.py
backend/domain/base.py
backend/domain/candidate_status_service.py
backend/domain/candidates/__init__.py
backend/domain/candidates/actions.py
backend/domain/candidates/journey.py
backend/domain/candidates/models.py
backend/domain/candidates/services.py
backend/domain/candidates/status.py
backend/domain/candidates/status_service.py
backend/domain/candidates/workflow.py
backend/domain/cities/models.py
backend/domain/default_data.py
backend/domain/detailization/__init__.py
backend/domain/detailization/models.py
backend/domain/errors.py
backend/domain/hh_integration/__init__.py
backend/domain/hh_integration/client.py
backend/domain/hh_integration/contracts.py
backend/domain/hh_integration/crypto.py
backend/domain/hh_integration/importer.py
backend/domain/hh_integration/jobs.py
backend/domain/hh_integration/models.py
backend/domain/hh_integration/oauth.py
backend/domain/hh_integration/service.py
backend/domain/hh_integration/summary.py
backend/domain/hh_sync/__init__.py
backend/domain/hh_sync/dispatcher.py
backend/domain/hh_sync/mapping.py
backend/domain/hh_sync/models.py
backend/domain/hh_sync/resolver.py
backend/domain/hh_sync/worker.py
backend/domain/models.py
backend/domain/repositories.py
backend/domain/simulator/__init__.py
backend/domain/simulator/models.py
backend/domain/slot_assignment_service.py
backend/domain/slot_service.py
backend/domain/template_contexts.py
backend/domain/template_stages.py
backend/domain/test_questions/__init__.py
backend/domain/test_questions/services.py
backend/domain/tests/bootstrap.py
backend/domain/tests/models.py
backend/migrations/__init__.py
backend/migrations/runner.py
backend/migrations/utils.py
backend/migrations/versions/0001_initial_schema.py
backend/migrations/versions/0002_seed_defaults.py
backend/migrations/versions/0003_add_slot_interview_outcome.py
backend/migrations/versions/0004_add_slot_bot_markers.py
backend/migrations/versions/0005_add_city_profile_fields.py
backend/migrations/versions/0006_add_slots_recruiter_start_index.py
backend/migrations/versions/0007_prevent_duplicate_slot_reservations.py
backend/migrations/versions/0008_add_slot_reminder_jobs.py
backend/migrations/versions/0009_add_missing_indexes.py
backend/migrations/versions/0010_add_notification_logs.py
backend/migrations/versions/0011_add_candidate_binding_to_notification_logs.py
backend/migrations/versions/0012_update_slots_candidate_recruiter_index.py
backend/migrations/versions/0013_enhance_notification_logs.py
backend/migrations/versions/0014_notification_outbox_and_templates.py
backend/migrations/versions/0015_add_kpi_weekly_table.py
backend/migrations/versions/0015_recruiter_city_links.py
backend/migrations/versions/0016_add_slot_interview_feedback.py
backend/migrations/versions/0016_add_slot_timezone.py
backend/migrations/versions/0017_bot_message_logs.py
backend/migrations/versions/0017_recruiter_capacity_and_pipeline.py
backend/migrations/versions/0018_candidate_report_urls.py
backend/migrations/versions/0018_slots_candidate_fields.py
backend/migrations/versions/0019_fix_notification_log_unique_index.py
backend/migrations/versions/0020_add_user_username.py
backend/migrations/versions/0021_update_slot_unique_index_include_purpose.py
backend/migrations/versions/0022_add_candidate_status.py
backend/migrations/versions/0023_add_interview_notes.py
backend/migrations/versions/0024_remove_legacy_24h_reminders.py
backend/migrations/versions/0025_add_intro_day_details.py
backend/migrations/versions/0026_add_recruiter_candidate_confirmed_template.py
backend/migrations/versions/0027_add_manual_slot_audit_log.py
backend/migrations/versions/0028_add_candidate_profile_fields.py
backend/migrations/versions/0029_add_manual_slot_availability.py
backend/migrations/versions/0030_add_telegram_identity_fields.py
backend/migrations/versions/0031_add_chat_messages.py
backend/migrations/versions/0032_add_conversation_mode.py
backend/migrations/versions/0033_add_intro_decline_reason.py
backend/migrations/versions/0034_message_templates_city_support.py
backend/migrations/versions/0035_add_analytics_events_and_jinja_flag.py
backend/migrations/versions/0036_ensure_candidate_status_enum_values.py
backend/migrations/versions/0037_recruiter_portal_auth.py
backend/migrations/versions/0038_recruiter_user_profile_link.py
backend/migrations/versions/0039_allow_multiple_recruiters_per_city.py
backend/migrations/versions/0040_add_audit_log_table.py
backend/migrations/versions/0041_add_slot_overlap_exclusion_constraint.py
backend/migrations/versions/0042_add_comprehensive_slot_indexes.py
backend/migrations/versions/0043_add_candidate_uuid_and_lead_source.py
backend/migrations/versions/0044_add_lead_statuses_to_candidate_enum.py
backend/migrations/versions/0045_add_candidate_responsible_recruiter.py
backend/migrations/versions/0046_add_test2_invites_and_test_result_source.py
backend/migrations/versions/0047_fix_invite_tokens_identity.py
backend/migrations/versions/0048_fix_test2_invites_timezone_columns.py
backend/migrations/versions/0049_allow_null_city_timezone.py
backend/migrations/versions/0050_align_slot_overlap_bounds_and_duration_default.py
backend/migrations/versions/0051_enforce_slot_overlap_on_10min_windows.py
backend/migrations/versions/0052_add_workflow_status_fields.py
backend/migrations/versions/0053_add_outbox_notification_indexes.py
backend/migrations/versions/0054_restore_city_responsible_recruiter.py
backend/migrations/versions/0055_add_performance_indexes.py
backend/migrations/versions/0056_sync_workflow_status_from_legacy.py
backend/migrations/versions/0057_auth_accounts.py
backend/migrations/versions/0058_add_recruiter_last_seen_at.py
backend/migrations/versions/0059_add_recruiter_plan_entries.py
backend/migrations/versions/0060_add_staff_messenger.py
backend/migrations/versions/0061_staff_message_tasks.py
backend/migrations/versions/0062_slot_assignments.py
backend/migrations/versions/0063_add_candidate_rejection_reason.py
backend/migrations/versions/0064_add_test_questions_tables.py
backend/migrations/versions/0065_add_intro_day_template_to_city.py
backend/migrations/versions/0066_add_city_experts_executives.py
backend/migrations/versions/0067_add_fk_indexes.py
backend/migrations/versions/0068_add_template_description.py
backend/migrations/versions/0069_drop_legacy_templates.py
backend/migrations/versions/0070_add_city_intro_fields.py
backend/migrations/versions/0071_add_slot_pending_candidate_status.py
backend/migrations/versions/0072_add_bot_runtime_configs.py
backend/migrations/versions/0073_unify_test_question_sources.py
backend/migrations/versions/0074_add_ai_outputs_and_logs.py
backend/migrations/versions/0075_add_kb_and_ai_chat.py
backend/migrations/versions/0076_add_simulator_runs.py
backend/migrations/versions/0077_add_detailization_entries.py
backend/migrations/versions/0078_add_vacancies.py
backend/migrations/versions/0079_add_city_reminder_policies.py
backend/migrations/versions/0080_slot_overlap_per_purpose.py
backend/migrations/versions/0081_add_detailization_soft_delete.py
backend/migrations/versions/0082_add_calendar_tasks.py
backend/migrations/versions/0083_sync_test1_question_bank.py
backend/migrations/versions/0084_allow_intro_day_parallel_slots.py
backend/migrations/versions/0085_add_interview_script_feedback_and_hh_resume.py
backend/migrations/versions/0086_update_interview_notification_templates.py
backend/migrations/versions/0087_update_t1_done_template.py
backend/migrations/versions/0088_upgrade_candidate_template_texts.py
backend/migrations/versions/0089_add_hh_sync_fields_and_log.py
backend/migrations/versions/0090_add_messenger_fields.py
backend/migrations/versions/0091_add_hh_integration_foundation.py
backend/migrations/versions/0092_allow_unbound_hh_vacancy_bindings.py
backend/migrations/versions/0093_reschedule_windows_and_candidate_chat_reads.py
backend/migrations/versions/0094_add_candidate_chat_archive_state.py
backend/migrations/versions/0095_add_candidate_portal_journey.py
backend/migrations/versions/0096_add_candidate_chat_workspaces.py
backend/migrations/versions/0097_add_candidate_journey_archive_foundation.py
backend/migrations/versions/__init__.py
backend/repositories/__init__.py
backend/repositories/city.py
backend/repositories/recruiter.py
backend/repositories/slot.py
backend/repositories/template.py
backend/repositories/user.py
backend/utils/__init__.py
backend/utils/jinja_renderer.py
bot.py
codex/CODEOWNERS.md
codex/agents/devops_ci.md
codex/agents/frontend_refactor.md
codex/agents/qa_playwright.md
codex/agents/scheduler_arch.md
codex/bootstrap.md
codex/codex.yaml
codex/context/audit.md
codex/context/decisions.log.md
codex/context/dev_department.md
codex/context/glossary.md
codex/context/guide_full.md
codex/context/project_map.md
codex/context/risks.md
codex/guidelines.md
codex/reports/ci_fix.md
codex/reports/ci_fix_py312.md
codex/reports/ci_fix_uvloop.md
codex/reports/ci_setup.md
codex/reports/fix_slots_serialization.md
codex/reports/qa_visual_smoke.md
codex/reports/repo_scan.md
codex/reports/run_log.md
codex/reports/serialization_issue_template.md
codex/reports/serialization_validation.md
codex/tasks/audit_fixlist.yaml
codex/tasks/e2e_basics.yaml
codex/tasks/sprint1_refactor.yaml
codex/tools/scripts.md
conftest.py
docker-compose.yml
docs/AI_COACH_RUNBOOK.md
docs/AI_INTERVIEW_SCRIPT_RUNBOOK.md
docs/DATABASE_SESSION_BEST_PRACTICES.md
docs/DEPENDENCY_INJECTION.md
docs/DEVEX.md
docs/LOCAL_DEV.md
docs/MIGRATIONS.md
docs/QA_AUDIT_REPORT_2026-02-26.md
docs/QUALITY_SCORECARD.md
docs/RELEASE_CHECKLIST.md
docs/SIMULATOR_RUNBOOK.md
docs/TECHNICAL_OVERVIEW.md
docs/TECH_STRATEGY.md
docs/TEST1_CONTRACTS.md
docs/TEST1_STATE_MACHINE.md
docs/access-control.md
docs/archive/Audit.md
docs/archive/BATCH_NOTIFICATION_ARCHITECTURE.md
docs/archive/BUGFIX_DUPLICATE_NOTIFICATIONS.md
docs/archive/BUGFIX_FORM_DUPLICATION.md
docs/archive/BUGFIX_INTEGRITYERROR_IDEMPOTENCY.md
docs/archive/BUGFIX_TELEGRAM_CHAT_LINK.md
docs/archive/DATETIME_FIXES_SUMMARY.md
docs/archive/DESIGN_SYSTEM_CANDIDATES_PAGE.md
docs/archive/DesignSystem.md
docs/archive/FINAL_SUMMARY.md
docs/archive/IMPLEMENTATION_PLAN.md
docs/archive/LIQUID_GLASS_GUIDE.md
docs/archive/LIQUID_GLASS_QUICKSTART.md
docs/archive/ND21.md
docs/archive/ND21_TZ.md
docs/archive/NOTIFICATIONS_E2E.md
docs/archive/NOTIFICATIONS_LOADTEST.md
docs/archive/PROJECT_AUDIT_REPORT.md
docs/archive/QA_REPORT.md
docs/archive/README_REDESIGN.md
docs/archive/REDESIGN_STRATEGY.md
docs/archive/SERVER_STABILITY.md
docs/archive/SLOTS_V2_PHASE1_PROGRESS.md
docs/archive/SLOTS_V2_SOURCE_OF_TRUTH.md
docs/archive/SMOKE_UI_CHECKLIST.md
docs/archive/TELEGRAM_USERNAME_AUTO_PARSING.md
docs/archive/TEST1_FIX_PLAN.md
docs/archive/TEST1_GAPS_CHECKLIST.md
docs/archive/TEST1_TRACES.md
docs/archive/admin/slots.md
docs/archive/candidate_profile.md
docs/archive/codex_system_prompt.md
docs/archive/features/dashboard/ANIMATED_COUNTER_IMPLEMENTATION.md
docs/archive/features/dashboard/CARD_TILT_IMPLEMENTATION.md
docs/archive/features/dashboard/DASHBOARD_BACKEND_INTEGRATION.md
docs/archive/features/dashboard/DASHBOARD_CHANGELOG.md
docs/archive/features/dashboard/DASHBOARD_EFFECTS_GUIDE.md
docs/archive/features/dashboard/DASHBOARD_REDESIGN_SUMMARY.md
docs/archive/features/dashboard/DESIGN_IMPROVEMENTS_SUMMARY.md
docs/archive/features/dashboard/INTERFACE_IMPROVEMENTS_PHASE_2.md
docs/archive/features/dashboard/LIQUID_GLASS_IMPLEMENTATION.md
docs/archive/features/dashboard/LIQUID_GLASS_README.md
docs/archive/features/dashboard/NEURAL_NETWORK_IMPLEMENTATION.md
docs/archive/features/dashboard/REAL_DATA_INTEGRATION_COMPLETE.md
docs/archive/features/notifications/INTRO_DAY_NOTIFICATIONS_FIX.md
docs/archive/guides/CACHE_CLEAR_INSTRUCTIONS.md
docs/archive/guides/VISUAL_EFFECTS_QUICKSTART.md
docs/archive/guides/VISUAL_EFFECTS_README.md
docs/archive/issues/001-css-duplication.md
docs/archive/issues/002-template-not-found.md
docs/archive/issues/003-inline-scripts.md
docs/archive/issues/004-static-paths.md
docs/archive/optimization/OPTIMIZATION_SUMMARY.md
docs/archive/optimization/PHASE2_PERFORMANCE.md
docs/archive/optimization/README_OPTIMIZATION.md
docs/archive/priority3-dashboard-prompt.md
docs/archive/qa/CRITICAL_ISSUES.md
docs/archive/qa/MANUAL_TEST_REPORT.md
docs/archive/qa/QA_COMPREHENSIVE_REPORT.md
docs/archive/qa/QA_ITERATION_2_REPORT.md
docs/archive/qa/REAL_BUG_REPORT.md
docs/archive/qa/TEST_REPORT.md
docs/archive/reliability/README.md
docs/archive/reliability_findings.md
docs/archive/ux/metrics-kpi.md
docs/archive/ux/research/notes-template.md
docs/archive/ux/research/research-plan.md
docs/candidate_channels/CANDIDATE_CHANNELS_AUDIT.md
docs/candidate_channels/CANDIDATE_EXPERIENCE_TARGET_ARCHITECTURE.md
docs/candidate_channels/CHANNEL_OPTIONS_COMPARISON.md
docs/candidate_channels/IMPLEMENTATION_ROADMAP.md
docs/candidate_channels/PRODUCT_REQUIREMENTS_CANDIDATE_PORTAL.md
docs/candidate_channels/RISK_REGISTER_CANDIDATE_CHANNELS.md
docs/candidate_channels/TECHNICAL_BACKLOG_CANDIDATE_CHANNELS.md
docs/frontend-migration-log.md
docs/gates/SPRINT1_2_FORMAL_GATE.md
docs/gates/SPRINT1_2_LAST_RUN.md
docs/gates/SPRINT1_2_ROUTE_INVENTORY_LAST_RUN.md
docs/gates/SPRINT_STABILITY_GATE_2026-02-27.md
docs/gates/baseline_metrics.md
docs/hh/EXECUTIVE_SUMMARY.md
docs/hh/HH_DOMAIN_MAPPING.md
docs/hh/HH_IMPLEMENTATION_ROADMAP.md
docs/hh/HH_INTEGRATION_ARCHITECTURE.md
docs/hh/HH_INTEGRATION_PRD.md
docs/hh/HH_INTEGRATION_RESEARCH.md
docs/hh/HH_PROTOCOLS_AND_CONTRACTS.md
docs/hh/HH_RISKS_AND_DECISIONS.md
docs/hh/HH_SYNC_LIFECYCLE.md
docs/hh/HH_UI_UX_INTEGRATION_PLAN.md
docs/migration-map.md
docs/performance/caching.md
docs/performance/explain_20260217.md
docs/performance/loadtesting.md
docs/performance/metrics.md
docs/performance/overview.md
docs/performance/results_20260216.md
docs/performance/results_20260217.md
docs/performance/results_20260301_go_gate.md
docs/project/AUDIT.md
docs/project/CLAUDE.md
docs/project/CODEX.md
docs/project/CONTRIBUTING.md
docs/project/DEPLOYMENT_GUIDE.md
docs/project/PROD_CHECKLIST.md
docs/rfc/ADR/ADR-0001-frontend-build-vite.md
docs/rfc/ADR/ADR-0002-ui-core-and-a11y.md
docs/rfc/ADR/ADR-0003-hh-integration-module.md
docs/route-inventory.md
docs/slots_generation.md
docs/status_flow.md
docs/telegram_delivery_pipeline.md
engine.md
frontend/app/eslint.config.js
frontend/app/openapi.json
frontend/app/package-lock.json
frontend/app/package.json
frontend/app/playwright.config.ts
frontend/app/public/manifest.json
frontend/app/src/api/client.ts
frontend/app/src/api/schema.ts
frontend/app/src/api/services/candidates.ts
frontend/app/src/api/services/dashboard.ts
frontend/app/src/api/services/messenger.ts
frontend/app/src/api/services/profile.ts
frontend/app/src/api/services/slots.ts
frontend/app/src/api/services/system.ts
frontend/app/src/app/components/ApiErrorBanner.tsx
frontend/app/src/app/components/Calendar/ScheduleCalendar.tsx
frontend/app/src/app/components/Calendar/calendar.css
frontend/app/src/app/components/CandidatePipeline/CandidatePipeline.tsx
frontend/app/src/app/components/CandidatePipeline/PipelineConnector.tsx
frontend/app/src/app/components/CandidatePipeline/PipelineStage.tsx
frontend/app/src/app/components/CandidatePipeline/StageBadge.tsx
frontend/app/src/app/components/CandidatePipeline/StageDetailPanel.tsx
frontend/app/src/app/components/CandidatePipeline/StageIndicator.tsx
frontend/app/src/app/components/CandidatePipeline/candidate-pipeline.css
frontend/app/src/app/components/CandidatePipeline/pipeline.types.ts
frontend/app/src/app/components/CandidatePipeline/pipeline.utils.ts
frontend/app/src/app/components/CandidatePipeline/pipeline.variants.ts
frontend/app/src/app/components/CandidateTimeline/CandidateTimeline.tsx
frontend/app/src/app/components/CandidateTimeline/TimelineEvent.tsx
frontend/app/src/app/components/CandidateTimeline/candidate-timeline.css
frontend/app/src/app/components/CandidateTimeline/timeline.types.ts
frontend/app/src/app/components/CohortComparison/CohortBar.tsx
frontend/app/src/app/components/CohortComparison/CohortComparison.tsx
frontend/app/src/app/components/CohortComparison/cohort-comparison.css
frontend/app/src/app/components/ErrorBoundary.test.tsx
frontend/app/src/app/components/ErrorBoundary.tsx
frontend/app/src/app/components/InterviewScript/InterviewScript.tsx
frontend/app/src/app/components/InterviewScript/RatingScale.tsx
frontend/app/src/app/components/InterviewScript/ScriptBriefing.tsx
frontend/app/src/app/components/InterviewScript/ScriptNotes.tsx
frontend/app/src/app/components/InterviewScript/ScriptQuestion.tsx
frontend/app/src/app/components/InterviewScript/ScriptScorecard.tsx
frontend/app/src/app/components/InterviewScript/ScriptStepper.tsx
frontend/app/src/app/components/InterviewScript/ScriptTimer.tsx
frontend/app/src/app/components/InterviewScript/interview-script.css
frontend/app/src/app/components/InterviewScript/script.prompts.ts
frontend/app/src/app/components/InterviewScript/script.types.ts
frontend/app/src/app/components/InterviewScript/script.variants.ts
frontend/app/src/app/components/InterviewScript/useInterviewScript.ts
frontend/app/src/app/components/QuestionPayloadEditor.tsx
frontend/app/src/app/components/QuickNotes/QuickNotes.tsx
frontend/app/src/app/components/RoleGuard.test.tsx
frontend/app/src/app/components/RoleGuard.tsx
frontend/app/src/app/hooks/useCalendarWebSocket.ts
frontend/app/src/app/hooks/useIsMobile.ts
frontend/app/src/app/hooks/useProfile.ts
frontend/app/src/app/lib/timezonePreview.ts
frontend/app/src/app/main.tsx
frontend/app/src/app/routes/__root.tsx
frontend/app/src/app/routes/__root.ui-mode.test.tsx
frontend/app/src/app/routes/app/calendar.tsx
frontend/app/src/app/routes/app/candidate-detail.tsx
frontend/app/src/app/routes/app/candidate-new.test.tsx
frontend/app/src/app/routes/app/candidate-new.tsx
frontend/app/src/app/routes/app/candidates.test.tsx
frontend/app/src/app/routes/app/candidates.tsx
frontend/app/src/app/routes/app/cities.tsx
frontend/app/src/app/routes/app/city-edit.tsx
frontend/app/src/app/routes/app/city-new.tsx
frontend/app/src/app/routes/app/copilot.tsx
frontend/app/src/app/routes/app/dashboard.tsx
frontend/app/src/app/routes/app/detailization.tsx
frontend/app/src/app/routes/app/incoming-demo.test.ts
frontend/app/src/app/routes/app/incoming-demo.ts
frontend/app/src/app/routes/app/incoming.filters.test.ts
frontend/app/src/app/routes/app/incoming.filters.ts
frontend/app/src/app/routes/app/incoming.tsx
frontend/app/src/app/routes/app/index.tsx
frontend/app/src/app/routes/app/login.tsx
frontend/app/src/app/routes/app/message-templates.tsx
frontend/app/src/app/routes/app/messenger.tsx
frontend/app/src/app/routes/app/messenger/useMessageDraft.ts
frontend/app/src/app/routes/app/profile.tsx
frontend/app/src/app/routes/app/question-edit.tsx
frontend/app/src/app/routes/app/question-new.tsx
frontend/app/src/app/routes/app/questions.tsx
frontend/app/src/app/routes/app/recruiter-edit.tsx
frontend/app/src/app/routes/app/recruiter-form.ts
frontend/app/src/app/routes/app/recruiter-new.tsx
frontend/app/src/app/routes/app/recruiters.tsx
frontend/app/src/app/routes/app/reminder-ops.tsx
frontend/app/src/app/routes/app/simulator.tsx
frontend/app/src/app/routes/app/slots-create.tsx
frontend/app/src/app/routes/app/slots.filters.test.ts
frontend/app/src/app/routes/app/slots.filters.ts
frontend/app/src/app/routes/app/slots.tsx
frontend/app/src/app/routes/app/slots.utils.test.ts
frontend/app/src/app/routes/app/slots.utils.ts
frontend/app/src/app/routes/app/system.tsx
frontend/app/src/app/routes/app/template-edit.tsx
frontend/app/src/app/routes/app/template-list.tsx
frontend/app/src/app/routes/app/template-new.tsx
frontend/app/src/app/routes/app/template_meta.ts
frontend/app/src/app/routes/app/test-builder-graph.tsx
frontend/app/src/app/routes/app/test-builder.tsx
frontend/app/src/app/routes/app/ui-cosmetics.test.tsx
frontend/app/src/app/routes/app/vacancies.tsx
frontend/app/src/app/routes/tg-app/candidate.tsx
frontend/app/src/app/routes/tg-app/incoming.tsx
frontend/app/src/app/routes/tg-app/index.tsx
frontend/app/src/app/routes/tg-app/layout.tsx
frontend/app/src/test/setup.ts
frontend/app/src/theme/components.css
frontend/app/src/theme/global.css
frontend/app/src/theme/material.css
frontend/app/src/theme/mobile.css
frontend/app/src/theme/motion.css
frontend/app/src/theme/pages.css
frontend/app/src/theme/tokens.css
frontend/app/src/theme/tokens.ts
frontend/app/tests/e2e/a11y.spec.ts
frontend/app/tests/e2e/ai-copilot.spec.ts
frontend/app/tests/e2e/candidates.spec.ts
frontend/app/tests/e2e/focus.cities.spec.ts
frontend/app/tests/e2e/focus.slots.spec.ts
frontend/app/tests/e2e/health.spec.ts
frontend/app/tests/e2e/mobile-smoke.spec.ts
frontend/app/tests/e2e/recruiters.spec.ts
frontend/app/tests/e2e/regression-flow.spec.ts
frontend/app/tests/e2e/slots.spec.ts
frontend/app/tests/e2e/smoke.spec.ts
frontend/app/tests/e2e/ui-cosmetics.spec.ts
frontend/app/tests/e2e/utils/keyboard.ts
frontend/app/tsconfig.json
frontend/app/vite.config.ts
frontend/app/vitest.config.ts
frontend/docs/slots-ui.md
frontend/package-lock.json
max_bot.py
pyproject.toml
run_migrations.py
scripts/check_candidate.py
scripts/check_failed_notifications.py
scripts/check_slot_2_notification.py
scripts/collect_ux.py
scripts/dev_doctor.py
scripts/dev_server.py
scripts/diagnose_notifications.py
scripts/diagnose_server.py
scripts/e2e_notifications_sandbox.py
scripts/export_interview_script_dataset.py
scripts/fix_slot_2_notification.py
scripts/formal_gate_sprint12.py
scripts/generate_waiting_candidates.py
scripts/loadtest_notifications.py
scripts/loadtest_profiles/analyze_step.py
scripts/loadtest_profiles/bodies/chat_send.json
scripts/loadtest_profiles/summarize_profile.py
scripts/migrate_city_templates.py
scripts/migrate_legacy_templates.py
scripts/run_interview_script_finetune.py
scripts/run_migrations.py
scripts/seed_auth_accounts.py
scripts/seed_city_templates.py
scripts/seed_default_templates.py
scripts/seed_incoming_candidates.py
scripts/seed_legacy_templates.py
scripts/seed_message_templates.py
scripts/seed_test_candidates.py
scripts/seed_test_users.py
scripts/seed_tests.py
scripts/summarize_autocannon.py
scripts/test_bot_init.py
scripts/test_create_intro_day.py
scripts/update_notification_templates.py
scripts/verify_jwt.py
splash.css
tests/conftest.py
tests/handlers/test_common_free_text.py
tests/integration/__init__.py
tests/integration/test_migrations_postgres.py
tests/integration/test_notification_broker_redis.py
tests/reproduce_issue_1.py
tests/services/test_bot_keyboards.py
tests/services/test_dashboard_and_slots.py
tests/services/test_dashboard_calendar.py
tests/services/test_dashboard_funnel.py
tests/services/test_slot_outcome.py
tests/services/test_slots_bulk.py
tests/services/test_slots_delete.py
tests/services/test_weekly_kpis.py
tests/test_action_endpoint.py
tests/test_admin_auth_form_admin_env.py
tests/test_admin_auth_no_basic_challenge.py
tests/test_admin_candidate_chat_actions.py
tests/test_admin_candidate_schedule_slot.py
tests/test_admin_candidate_status_update.py
tests/test_admin_candidates_service.py
tests/test_admin_message_templates.py
tests/test_admin_message_templates_sms.py
tests/test_admin_message_templates_update.py
tests/test_admin_notifications_feed_api.py
tests/test_admin_notifications_service.py
tests/test_admin_slots_api.py
tests/test_admin_state_nullbot.py
tests/test_admin_surface_hardening.py
tests/test_admin_template_keys.py
tests/test_admin_templates_legacy_create_revive.py
tests/test_admin_ui_auth_startup.py
tests/test_ai_copilot.py
tests/test_api_presets.py
tests/test_bot_app.py
tests/test_bot_app_smoke.py
tests/test_bot_confirmation_flows.py
tests/test_bot_html_escape.py
tests/test_bot_integration_toggle.py
tests/test_bot_manual_contact.py
tests/test_bot_questions_refresh.py
tests/test_bot_reminder_jobs_api.py
tests/test_bot_reminder_policy_api.py
tests/test_bot_reschedule_reject.py
tests/test_bot_runtime_config.py
tests/test_bot_template_copy_quality.py
tests/test_bot_test1_notifications.py
tests/test_bot_test1_validation.py
tests/test_broker_production_restrictions.py
tests/test_bulk_slots_timezone_moscow_novosibirsk.py
tests/test_cache_integration.py
tests/test_calendar_hub_scope.py
tests/test_candidate_actions.py
tests/test_candidate_chat_threads_api.py
tests/test_candidate_lead_and_invite.py
tests/test_candidate_rejection_reason.py
tests/test_candidate_reports.py
tests/test_candidate_services.py
tests/test_candidate_status_logic.py
tests/test_chat_messages.py
tests/test_chat_rate_limit.py
tests/test_cities_settings_api.py
tests/test_city_experts_sync.py
tests/test_city_hh_vacancies_api.py
tests/test_city_lookup_variants.py
tests/test_city_reminder_policy.py
tests/test_city_template_resolution.py
tests/test_content_updates.py
tests/test_delete_past_free_slots.py
tests/test_dependency_injection.py
tests/test_detailization_report.py
tests/test_domain_repositories.py
tests/test_double_booking.py
tests/test_e2e_notification_flow.py
tests/test_hh_integration_actions.py
tests/test_hh_integration_client.py
tests/test_hh_integration_foundation.py
tests/test_hh_integration_import.py
tests/test_hh_integration_jobs.py
tests/test_hh_integration_migrations.py
tests/test_hh_sync.py
tests/test_interview_script_ai.py
tests/test_interview_script_feedback.py
tests/test_intro_day_e2e.py
tests/test_intro_day_flow.py
tests/test_intro_day_notifications.py
tests/test_intro_day_recruiter_scope.py
tests/test_intro_day_slot_isolation.py
tests/test_intro_day_status.py
tests/test_jinja_renderer.py
tests/test_kb_active_documents_list.py
tests/test_kb_and_ai_agent_chat.py
tests/test_manual_slot_assignment.py
tests/test_manual_slot_booking_api.py
tests/test_max_bot.py
tests/test_max_sales_handoff.py
tests/test_message_templates_rbac.py
tests/test_messenger.py
tests/test_migration_runner_privileges.py
tests/test_notification_bootstrap.py
tests/test_notification_log_idempotency.py
tests/test_notification_logs.py
tests/test_notification_retry.py
tests/test_openai_provider_params.py
tests/test_openai_provider_responses_api.py
tests/test_outbox_deduplication.py
tests/test_outbox_notifications.py
tests/test_perf_cache_keys.py
tests/test_perf_cache_stale_revalidate.py
tests/test_perf_metrics_endpoint.py
tests/test_prod_config_simple.py
tests/test_prod_requires_redis.py
tests/test_profile_avatar_api.py
tests/test_profile_settings_api.py
tests/test_questions_reorder_api.py
tests/test_rate_limiting.py
tests/test_recruiter_service.py
tests/test_recruiter_timezone_conversion.py
tests/test_reminder_service.py
tests/test_reminders_schedule.py
tests/test_reschedule_requests_scoping.py
tests/test_run_migrations_contract.py
tests/test_scoping_guards.py
tests/test_security_auth_hardening.py
tests/test_session_cookie_config.py
tests/test_simulator_api.py
tests/test_slot_approval_notifications.py
tests/test_slot_assignment_reschedule_replace.py
tests/test_slot_assignment_slot_sync.py
tests/test_slot_cleanup_strict.py
tests/test_slot_creation_timezone_validation.py
tests/test_slot_duration_validation.py
tests/test_slot_overlap_constraint.py
tests/test_slot_overlap_handling.py
tests/test_slot_overlap_window.py
tests/test_slot_past_validation.py
tests/test_slot_repository.py
tests/test_slot_reservations.py
tests/test_slot_status_transitions.py
tests/test_slot_timezone_moscow_novosibirsk.py
tests/test_slot_timezone_validation.py
tests/test_slot_timezones.py
tests/test_slots_api_tz.py
tests/test_slots_generation.py
tests/test_slots_timezone_handling.py
tests/test_sqlite_dev_schema.py
tests/test_staff_chat_file_upload.py
tests/test_staff_chat_updates.py
tests/test_state_store.py
tests/test_status_service_transitions.py
tests/test_telegram_identity.py
tests/test_template_lookup_and_invalidation.py
tests/test_template_provider.py
tests/test_test_builder_graph_api.py
tests/test_test_builder_graph_preview_api.py
tests/test_timezone_service.py
tests/test_timezone_utils.py
tests/test_timezones.py
tests/test_vacancy_api.py
tests/test_vacancy_service.py
tests/test_webapp_auth.py
tests/test_webapp_booking_api.py
tests/test_webapp_recruiter.py
tests/test_webapp_smoke.py
tests/test_workflow_api.py
tests/test_workflow_contract.py
tests/test_workflow_hired.py
tools/recompute_weekly_kpis.py
tools/render_previews.py
```

## 3. Инвентарь документации и конфигов

### Корневые документы и конфиги

| Файл | Тип | Строк | Назначение |
|---|---:|---:|---|
| `.env.development.example` | Конфиг/данные | 21 | Файл переменных окружения/пример локальной конфигурации. |
| `.env.example` | Конфиг/данные | 87 | Файл переменных окружения/пример локальной конфигурации. |
| `.env.local` | Конфиг/данные | 54 | Файл переменных окружения/пример локальной конфигурации. |
| `.env.local.example` | Конфиг/данные | 68 | Файл переменных окружения/пример локальной конфигурации. |
| `.pre-commit-config.yaml` | Конфиг/данные | 34 | Конфигурационный файл `.pre-commit-config`. |
| `AGENTS.md` | Документ | 157 | AGENTS.md |
| `CURRENT_PROGRAM_STATE.md` | Документ | 54 | Current Program State |
| `PROJECT_CONTEXT_INDEX.md` | Документ | 50 | Project Context Index |
| `README.md` | Документ | 131 | RecruitSmart Admin |
| `REPOSITORY_WORKFLOW_GUIDE.md` | Документ | 45 | Repository Workflow Guide |
| `VERIFICATION_COMMANDS.md` | Документ | 226 | Verification Commands |
| `docker-compose.yml` | Конфиг/данные | 225 | Конфигурационный файл `docker-compose`. |
| `engine.md` | Документ | 80 | engine.md |
| `pyproject.toml` | Конфиг/данные | 97 | Конфигурация Python-проекта и инструментов разработки. |

### Docs

| Файл | Тип | Строк | Назначение |
|---|---:|---:|---|
| `docs/AI_COACH_RUNBOOK.md` | Документ | 40 | AI Coach Runbook |
| `docs/AI_INTERVIEW_SCRIPT_RUNBOOK.md` | Документ | 81 | AI Interview Script Runbook |
| `docs/DATABASE_SESSION_BEST_PRACTICES.md` | Документ | 197 | Database Session Best Practices |
| `docs/DEPENDENCY_INJECTION.md` | Документ | 434 | FastAPI Dependency Injection Guide |
| `docs/DEVEX.md` | Документ | 75 | Developer Experience Guide |
| `docs/LOCAL_DEV.md` | Документ | 61 | Local Admin UI Development |
| `docs/MIGRATIONS.md` | Документ | 312 | Database Migrations Guide |
| `docs/QA_AUDIT_REPORT_2026-02-26.md` | Документ | 289 | QA Audit Report — RecruitSmart CRM |
| `docs/QUALITY_SCORECARD.md` | Документ | 60 | Quality Scorecard (Local) |
| `docs/RELEASE_CHECKLIST.md` | Документ | 47 | Release Checklist |
| `docs/SIMULATOR_RUNBOOK.md` | Документ | 46 | Scenario Simulator Runbook (Local Only) |
| `docs/TECHNICAL_OVERVIEW.md` | Документ | 82 | Technical Overview |
| `docs/TECH_STRATEGY.md` | Документ | 32 | Liquid Glass v2 Frontend Strategy |
| `docs/TEST1_CONTRACTS.md` | Документ | 61 | TEST 1 — Contract Matrix |
| `docs/TEST1_STATE_MACHINE.md` | Документ | 54 | Тест 1 — состояние слота и кандидата |
| `docs/access-control.md` | Документ | 50 | Access Control – RecruitSmart (web) |
| `docs/archive/Audit.md` | Документ | 12 | UI Аудит админ-панели |
| `docs/archive/BATCH_NOTIFICATION_ARCHITECTURE.md` | Документ | 129 | Batch Notification Processing Architecture |
| `docs/archive/BUGFIX_DUPLICATE_NOTIFICATIONS.md` | Документ | 298 | Bugfix: Duplicate Confirmation Messages (CONFIRM_2H) |
| `docs/archive/BUGFIX_FORM_DUPLICATION.md` | Документ | 332 | Bugfix: Дублирование анкеты и улучшения UX |
| `docs/archive/BUGFIX_INTEGRITYERROR_IDEMPOTENCY.md` | Документ | 501 | Bugfix: IntegrityError при повторном вызове reject_booking |
| `docs/archive/BUGFIX_TELEGRAM_CHAT_LINK.md` | Документ | 562 | Bugfix: Ссылка на чат с кандидатом открывает бота вместо личных сообщений |
| `docs/archive/DATETIME_FIXES_SUMMARY.md` | Документ | 381 | DateTime Fixes Summary |
| `docs/archive/DESIGN_SYSTEM_CANDIDATES_PAGE.md` | Документ | 873 | 🎨 Design System: Страница "Кандидаты" \| Liquid Glass Улучшения |
| `docs/archive/DesignSystem.md` | Документ | 69 | Liquid Glass Design System |
| `docs/archive/FINAL_SUMMARY.md` | Документ | 626 | FINAL SUMMARY: RecruitSmart Admin UI Redesign |
| `docs/archive/IMPLEMENTATION_PLAN.md` | Документ | 29 | Implementation Plan |
| `docs/archive/LIQUID_GLASS_GUIDE.md` | Документ | 656 | Liquid Glass Design System Guide |
| `docs/archive/LIQUID_GLASS_QUICKSTART.md` | Документ | 408 | Liquid Glass Design System - Quick Start |
| `docs/archive/ND21.md` | Документ | 142 | Audit ND21 — Recruitsmart Admin Readiness (повторный) |
| `docs/archive/ND21_TZ.md` | Документ | 57 | ТЗ: Улучшение подсистем уведомлений и эксплуатационной готовности |
| `docs/archive/NOTIFICATIONS_E2E.md` | Документ | 57 | Notification E2E Sandbox |
| `docs/archive/NOTIFICATIONS_LOADTEST.md` | Документ | 94 | Notification Load Testing |
| `docs/archive/PROJECT_AUDIT_REPORT.md` | Документ | 442 | 🔍 Аудит Кодовой Базы RecruitSmart Admin |
| `docs/archive/QA_REPORT.md` | Документ | 406 | QA Test Report - Sprint 0 Implementation |
| `docs/archive/README_REDESIGN.md` | Документ | 249 | RecruitSmart Admin UI Redesign — Quick Start |
| `docs/archive/REDESIGN_STRATEGY.md` | Документ | 1764 | REDESIGN STRATEGY: RecruitSmart Admin UI |
| `docs/archive/SERVER_STABILITY.md` | Документ | 463 | Server Stability & Monitoring Guide |
| `docs/archive/SLOTS_V2_PHASE1_PROGRESS.md` | Документ | 233 | Slots v2 - Phase 1 Progress |
| `docs/archive/SLOTS_V2_SOURCE_OF_TRUTH.md` | Документ | 448 | Slots v2: Source of Truth |
| `docs/archive/SMOKE_UI_CHECKLIST.md` | Документ | 12 | UI Smoke Checklist (Light/Dark) |
| `docs/archive/TELEGRAM_USERNAME_AUTO_PARSING.md` | Документ | 394 | Автоматический парсинг username из Telegram |
| `docs/archive/TEST1_FIX_PLAN.md` | Документ | 38 | TEST 1 — Fix & Migration Plan |
| `docs/archive/TEST1_GAPS_CHECKLIST.md` | Документ | 15 | TEST 1 — Gap Checklist |
| `docs/archive/TEST1_TRACES.md` | Документ | 84 | TEST 1 — Sequence Traces |
| `docs/archive/admin/slots.md` | Документ | 40 | Страница «Слоты» |
| `docs/archive/candidate_profile.md` | Документ | 25 | Профиль кандидата: быстрые действия и коммуникация |
| `docs/archive/codex_system_prompt.md` | Документ | 146 | Codex System Prompt для проекта RecruitSmart / SMART SERVICE |
| `docs/archive/features/dashboard/ANIMATED_COUNTER_IMPLEMENTATION.md` | Документ | 544 | Animated Counter with Sparkles - Implementation Guide |
| `docs/archive/features/dashboard/CARD_TILT_IMPLEMENTATION.md` | Документ | 383 | 3D Card Tilt + Holographic Shine - Implementation Guide |
| `docs/archive/features/dashboard/DASHBOARD_BACKEND_INTEGRATION.md` | Документ | 517 | 🔌 Dashboard Backend Integration — Summary |
| `docs/archive/features/dashboard/DASHBOARD_CHANGELOG.md` | Документ | 1706 | Dashboard Redesign Changelog |
| `docs/archive/features/dashboard/DASHBOARD_EFFECTS_GUIDE.md` | Документ | 401 | RecruitSmart Dashboard - Visual Effects Guide |
| `docs/archive/features/dashboard/DASHBOARD_REDESIGN_SUMMARY.md` | Документ | 318 | 🎨 RecruitSmart Dashboard — Premium Redesign |
| `docs/archive/features/dashboard/DESIGN_IMPROVEMENTS_SUMMARY.md` | Документ | 399 | Design Improvements Summary - RecruitSmart Admin |
| `docs/archive/features/dashboard/INTERFACE_IMPROVEMENTS_PHASE_2.md` | Документ | 616 | 🚀 Interface Improvements — Phase 2 |
| `docs/archive/features/dashboard/LIQUID_GLASS_IMPLEMENTATION.md` | Документ | 530 | Liquid Glass Design System - Implementation Summary |
| `docs/archive/features/dashboard/LIQUID_GLASS_README.md` | Документ | 326 | 🌊 Liquid Glass Design System |
| `docs/archive/features/dashboard/NEURAL_NETWORK_IMPLEMENTATION.md` | Документ | 205 | Neural Network Background Effect - Implementation Guide |
| `docs/archive/features/dashboard/REAL_DATA_INTEGRATION_COMPLETE.md` | Документ | 329 | ✅ Real Data Integration — Complete |
| `docs/archive/features/notifications/INTRO_DAY_NOTIFICATIONS_FIX.md` | Документ | 262 | Исправление уведомлений ознакомительного дня |
| `docs/archive/guides/CACHE_CLEAR_INSTRUCTIONS.md` | Документ | 177 | 🔄 Инструкция: Обновление дашборда после изменений |
| `docs/archive/guides/VISUAL_EFFECTS_QUICKSTART.md` | Документ | 340 | 🚀 Visual Effects - Quick Start Guide |
| `docs/archive/guides/VISUAL_EFFECTS_README.md` | Документ | 390 | 🎨 RecruitSmart Dashboard - Visual Effects |
| `docs/archive/issues/001-css-duplication.md` | Документ | 22 | Issue 001 — Дублирование CSS и конфликт тем |
| `docs/archive/issues/002-template-not-found.md` | Документ | 25 | Issue 002 — TemplateNotFound на /questions/{id}/edit |
| `docs/archive/issues/003-inline-scripts.md` | Документ | 20 | Issue 003 — Inline-скрипты в шаблонах |
| `docs/archive/issues/004-static-paths.md` | Документ | 22 | Issue 004 — Жёсткие пути /static в шаблонах |
| `docs/archive/optimization/OPTIMIZATION_SUMMARY.md` | Документ | 346 | Backend Optimization Summary |
| `docs/archive/optimization/PHASE2_PERFORMANCE.md` | Документ | 601 | Phase 2: Performance Optimization - Complete! 🚀 |
| `docs/archive/optimization/README_OPTIMIZATION.md` | Документ | 292 | 🚀 Backend Optimization - Complete! |
| `docs/archive/priority3-dashboard-prompt.md` | Документ | 100 | Контекст |
| `docs/archive/qa/CRITICAL_ISSUES.md` | Документ | 261 | ⚠️ Критичные проблемы - Требуют немедленного внимания |
| `docs/archive/qa/MANUAL_TEST_REPORT.md` | Документ | 334 | Manual Test Report |
| `docs/archive/qa/QA_COMPREHENSIVE_REPORT.md` | Документ | 2006 | QA Testing Report - RecruitSmart Admin Platform |
| `docs/archive/qa/QA_ITERATION_2_REPORT.md` | Документ | 349 | QA Testing Report: Iteration 2 - Required Field Indicators |
| `docs/archive/qa/REAL_BUG_REPORT.md` | Документ | 504 | Real Bug Report - RecruitSmart Admin (FastAPI + Jinja2) |
| `docs/archive/qa/TEST_REPORT.md` | Документ | 511 | Отчет о тестировании системы Recruitsmart Admin |
| `docs/archive/reliability/README.md` | Документ | 16 | Reliability Artifacts |
| `docs/archive/reliability_findings.md` | Документ | 21 | Надёжность и устойчивость (наблюдения) |
| `docs/archive/ux/metrics-kpi.md` | Документ | 55 | KPI и метрики UX админ-панели |
| `docs/archive/ux/research/notes-template.md` | Документ | 49 | Шаблон заметок по интервью |
| `docs/archive/ux/research/research-plan.md` | Документ | 80 | План UX-исследований админ-панели |
| `docs/candidate_channels/CANDIDATE_CHANNELS_AUDIT.md` | Документ | 488 | Candidate Channels Audit |
| `docs/candidate_channels/CANDIDATE_EXPERIENCE_TARGET_ARCHITECTURE.md` | Документ | 603 | Candidate Experience Target Architecture |
| `docs/candidate_channels/CHANNEL_OPTIONS_COMPARISON.md` | Документ | 314 | Channel Options Comparison |
| `docs/candidate_channels/IMPLEMENTATION_ROADMAP.md` | Документ | 433 | Implementation Roadmap |
| `docs/candidate_channels/PRODUCT_REQUIREMENTS_CANDIDATE_PORTAL.md` | Документ | 485 | Product Requirements: Candidate Portal |
| `docs/candidate_channels/RISK_REGISTER_CANDIDATE_CHANNELS.md` | Документ | 130 | Risk Register: Candidate Channels |
| `docs/candidate_channels/TECHNICAL_BACKLOG_CANDIDATE_CHANNELS.md` | Документ | 277 | Technical Backlog: Candidate Channels |
| `docs/frontend-migration-log.md` | Документ | 162 | Frontend Migration Log (React + TS, Vite) |
| `docs/gates/SPRINT1_2_FORMAL_GATE.md` | Документ | 51 | Formal Gate: Sprint 1/2 |
| `docs/gates/SPRINT1_2_LAST_RUN.md` | Документ | 49 | Formal Gate Sprint 1/2 |
| `docs/gates/SPRINT1_2_ROUTE_INVENTORY_LAST_RUN.md` | Документ | 223 | Sprint 1/2 Route Inventory |
| `docs/gates/SPRINT_STABILITY_GATE_2026-02-27.md` | Документ | 79 | Sprint Stability Gate — 2026-02-27 |
| `docs/gates/baseline_metrics.md` | Документ | 121 | vNext Baseline Metrics |
| `docs/hh/EXECUTIVE_SUMMARY.md` | Документ | 37 | HH Executive Summary |
| `docs/hh/HH_DOMAIN_MAPPING.md` | Документ | 107 | HH Domain Mapping |
| `docs/hh/HH_IMPLEMENTATION_ROADMAP.md` | Документ | 50 | HH Implementation Roadmap |
| `docs/hh/HH_INTEGRATION_ARCHITECTURE.md` | Документ | 79 | HH Integration Architecture |
| `docs/hh/HH_INTEGRATION_PRD.md` | Документ | 107 | HH Integration PRD |
| `docs/hh/HH_INTEGRATION_RESEARCH.md` | Документ | 196 | HH Integration Research |
| `docs/hh/HH_PROTOCOLS_AND_CONTRACTS.md` | Документ | 64 | HH Protocols And Contracts |
| `docs/hh/HH_RISKS_AND_DECISIONS.md` | Документ | 50 | HH Risks And Decisions |
| `docs/hh/HH_SYNC_LIFECYCLE.md` | Документ | 61 | HH Sync Lifecycle |
| `docs/hh/HH_UI_UX_INTEGRATION_PLAN.md` | Документ | 38 | HH UI UX Integration Plan |
| `docs/migration-map.md` | Документ | 139 | Migration Map: Jinja → React/TSX (Admin UI) |
| `docs/performance/caching.md` | Документ | 63 | Caching (admin_ui perf) |
| `docs/performance/explain_20260217.md` | Документ | 77 | EXPLAIN Artifacts (local) — 2026-02-17 |
| `docs/performance/loadtesting.md` | Документ | 147 | Load Testing (HTTP) for admin_ui |
| `docs/performance/metrics.md` | Документ | 72 | Metrics (admin_ui perf) |
| `docs/performance/overview.md` | Документ | 92 | Performance Overview (admin_ui) |
| `docs/performance/results_20260216.md` | Документ | 40 | Performance Results (local) — 2026-02-16 |
| `docs/performance/results_20260217.md` | Документ | 160 | Performance Results (local) — 2026-02-17 |
| `docs/performance/results_20260301_go_gate.md` | Документ | 66 | GO Perf Gate — 2026-03-01 |
| `docs/project/AUDIT.md` | Документ | 24 | Project Audit (Draft) |
| `docs/project/CLAUDE.md` | Документ | 138 | CLAUDE.md |
| `docs/project/CODEX.md` | Документ | 56 | Codex: Smart Service HR Admin |
| `docs/project/CONTRIBUTING.md` | Документ | 14 | Contributing Guidelines |
| `docs/project/DEPLOYMENT_GUIDE.md` | Документ | 59 | Deployment Guide |
| `docs/project/PROD_CHECKLIST.md` | Документ | 27 | Production Checklist (Draft) |
| `docs/rfc/ADR/ADR-0001-frontend-build-vite.md` | Документ | 28 | ADR-0001 — Переход на Vite и manifest-helper |
| `docs/rfc/ADR/ADR-0002-ui-core-and-a11y.md` | Документ | 31 | ADR-0002 — UI-core и доступность |
| `docs/rfc/ADR/ADR-0003-hh-integration-module.md` | Документ | 49 | ADR-0003: Introduce HH Integration Module |
| `docs/route-inventory.md` | Документ | 33 | Route Inventory (admin_ui) — Auth & Scoping (100% covered) |
| `docs/slots_generation.md` | Документ | 22 | Генерация слотов (админка /slots) |
| `docs/status_flow.md` | Документ | 68 | Карта статусов кандидата (as-is) |
| `docs/telegram_delivery_pipeline.md` | Документ | 80 | Надёжная доставка исходящих сообщений в Telegram |

### Codex / audit материалы

| Файл | Тип | Строк | Назначение |
|---|---:|---:|---|
| `.claude/agents/admin-panel-frontend-dev.md` | Документ | 208 | Core Responsibilities |
| `.claude/agents/qa-frontend-tester.md` | Документ | 181 | Testing Methodology |
| `.claude/agents/ui-ux-designer.md` | Документ | 100 | name: ui-ux-designer description: Use this agent when the user needs interface design expertise, including: analyzing existing UI/UX implementations, creating or improving admin dashboards, designing forms and data entry workflows, optimizi… |
| `.claude/launch.json` | Конфиг/данные | 18 | Конфигурационный файл `launch`. |
| `.claude/settings.local.json` | Конфиг/данные | 119 | Конфигурационный файл `settings.local`. |
| `audit/ACTION_PLAN.md` | Документ | 13 | План работ |
| `audit/CSS_SIZE.md` | Документ | 10 | CSS Size Audit |
| `audit/DIAGNOSIS.md` | Документ | 38 | Диагностика |
| `audit/ESTIMATES.md` | Документ | 14 | Оценка трудозатрат |
| `audit/INVENTORY.json` | Конфиг/данные | 461 | Конфигурационный файл `INVENTORY`. |
| `audit/INVENTORY.md` | Документ | 407 | Project Inventory |
| `audit/METRICS.md` | Документ | 22 | Runtime and Bundle Metrics |
| `audit/QUALITY.md` | Документ | 21 | Качество, DX и UX |
| `audit/REPORT.md` | Документ | 36 | Итоговый отчёт (Liquid Glass audit) |
| `audit/SECURITY.md` | Документ | 8 | Безопасность |
| `audit/collect_metrics.py` | Файл | 152 | !/usr/bin/env python3 |
| `audit/generate_inventory.py` | Файл | 459 | !/usr/bin/env python3 |
| `audit/metrics.json` | Конфиг/данные | 48 | Конфигурационный файл `metrics`. |
| `audit/run_smoke_checks.py` | Файл | 88 | !/usr/bin/env python3 |
| `codex/CODEOWNERS.md` | Документ | 17 | CODEOWNERS для Codex |
| `codex/agents/devops_ci.md` | Документ | 34 | Агент DevOps & CI |
| `codex/agents/frontend_refactor.md` | Документ | 39 | Агент Frontend Refactorer |
| `codex/agents/qa_playwright.md` | Документ | 28 | Агент QA E2E (Playwright) |
| `codex/agents/scheduler_arch.md` | Документ | 35 | Агент Scheduler Architect |
| `codex/bootstrap.md` | Документ | 39 | Bootstrap Codex |
| `codex/codex.yaml` | Конфиг/данные | 50 | Конфигурационный файл `codex`. |
| `codex/context/audit.md` | Документ | 62 | Аудит Smart Service HR Admin (экспресс) |
| `codex/context/decisions.log.md` | Документ | 7 | Журнал решений |
| `codex/context/dev_department.md` | Документ | 52 | Виртуальный отдел разработки |
| `codex/context/glossary.md` | Документ | 12 | Глоссарий |
| `codex/context/guide_full.md` | Документ | 78 | Полный гайд по Smart Service HR Admin |
| `codex/context/project_map.md` | Документ | 35 | Карта проекта |
| `codex/context/risks.md` | Документ | 13 | Риски и долги |
| `codex/guidelines.md` | Документ | 48 | Руководство по разработке |
| `codex/reports/ci_fix.md` | Документ | 34 | CI Fix Log |
| `codex/reports/ci_fix_py312.md` | Документ | 12 | CI stabilization for Python 3.12 and Playwright smoke tests |
| `codex/reports/ci_fix_uvloop.md` | Документ | 6 | CI fix: uvloop optionality on Python 3.12 |
| `codex/reports/ci_setup.md` | Документ | 22 | CI dry-run notes — 2025-10-18 |
| `codex/reports/fix_slots_serialization.md` | Документ | 11 | Fix slots serialization issue |
| `codex/reports/qa_visual_smoke.md` | Документ | 12 | QA Visual Smoke |
| `codex/reports/repo_scan.md` | Документ | 57 | Repo scan — HR Admin/Bot |
| `codex/reports/run_log.md` | Документ | 59 | Dry-run log — 2025-10-18 |
| `codex/reports/serialization_issue_template.md` | Документ | 19 | Контекст |
| `codex/reports/serialization_validation.md` | Документ | 15 | Serialization validation follow-up |
| `codex/tasks/audit_fixlist.yaml` | Конфиг/данные | 62 | Конфигурационный файл `audit_fixlist`. |
| `codex/tasks/e2e_basics.yaml` | Конфиг/данные | 57 | Конфигурационный файл `e2e_basics`. |
| `codex/tasks/sprint1_refactor.yaml` | Конфиг/данные | 43 | Конфигурационный файл `sprint1_refactor`. |
| `codex/tools/scripts.md` | Документ | 31 | Скрипты и утилиты |

### Прочие конфиги/данные

| Файл | Тип | Строк | Назначение |
|---|---:|---:|---|
| `.claude/launch.json` | Конфиг/данные | 18 | Конфигурационный файл `launch`. |
| `.claude/settings.local.json` | Конфиг/данные | 119 | Конфигурационный файл `settings.local`. |
| `.env.development.example` | Конфиг/данные | 21 | Файл переменных окружения/пример локальной конфигурации. |
| `.env.example` | Конфиг/данные | 87 | Файл переменных окружения/пример локальной конфигурации. |
| `.env.local` | Конфиг/данные | 54 | Файл переменных окружения/пример локальной конфигурации. |
| `.env.local.example` | Конфиг/данные | 68 | Файл переменных окружения/пример локальной конфигурации. |
| `.github/dependabot.yml` | Конфиг/данные | 36 | Конфигурационный файл `dependabot`. |
| `.github/workflows/ci.yaml` | Конфиг/данные | 114 | Конфигурационный файл `ci`. |
| `.github/workflows/ci.yml` | Конфиг/данные | 110 | Конфигурационный файл `ci`. |
| `.github/workflows/dependency-audit.yml` | Конфиг/данные | 51 | Конфигурационный файл `dependency-audit`. |
| `.github/workflows/migration-contract.yml` | Конфиг/данные | 114 | Конфигурационный файл `migration-contract`. |
| `.github/workflows/ui-preview.yml` | Конфиг/данные | 41 | Конфигурационный файл `ui-preview`. |
| `.pre-commit-config.yaml` | Конфиг/данные | 34 | Конфигурационный файл `.pre-commit-config`. |
| `.vscode/extensions.json` | Конфиг/данные | 5 | Конфигурационный файл `extensions`. |
| `.vscode/settings.json` | Конфиг/данные | 5 | Конфигурационный файл `settings`. |
| `audit/INVENTORY.json` | Конфиг/данные | 461 | Конфигурационный файл `INVENTORY`. |
| `audit/metrics.json` | Конфиг/данные | 48 | Конфигурационный файл `metrics`. |
| `codex/codex.yaml` | Конфиг/данные | 50 | Конфигурационный файл `codex`. |
| `codex/tasks/audit_fixlist.yaml` | Конфиг/данные | 62 | Конфигурационный файл `audit_fixlist`. |
| `codex/tasks/e2e_basics.yaml` | Конфиг/данные | 57 | Конфигурационный файл `e2e_basics`. |
| `codex/tasks/sprint1_refactor.yaml` | Конфиг/данные | 43 | Конфигурационный файл `sprint1_refactor`. |
| `docker-compose.yml` | Конфиг/данные | 225 | Конфигурационный файл `docker-compose`. |
| `frontend/app/openapi.json` | Конфиг/данные | 5915 | Конфигурационный файл `openapi`. |
| `frontend/app/package-lock.json` | Конфиг/данные | 8553 | Конфигурационный файл `package-lock`. |
| `frontend/app/package.json` | Конфиг/данные | 73 | Конфигурация frontend-пакета, скриптов и npm-зависимостей. |
| `frontend/app/public/manifest.json` | Конфиг/данные | 23 | Конфигурационный файл `manifest`. |
| `frontend/app/tsconfig.json` | Конфиг/данные | 23 | Конфигурационный файл `tsconfig`. |
| `frontend/package-lock.json` | Конфиг/данные | 7 | Конфигурационный файл `package-lock`. |
| `pyproject.toml` | Конфиг/данные | 97 | Конфигурация Python-проекта и инструментов разработки. |
