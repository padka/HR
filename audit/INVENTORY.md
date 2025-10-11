# Project Inventory

## Repository Tree (trimmed)
```
├── .github/
│   └── workflows/
│       ├── ci.yml
│       └── ui-preview.yml
├── .vscode/
│   └── settings.json
├── admin_server/
│   ├── __init__.py
│   └── app.py
├── audit/
│   ├── ACTION_PLAN.md
│   ├── CSS_SIZE.md
│   ├── DIAGNOSIS.md
│   ├── ESTIMATES.md
│   ├── INVENTORY.json
│   ├── INVENTORY.md
│   ├── LOGS.txt
│   ├── METRICS.md
│   ├── QUALITY.md
│   ├── REPORT.md
│   ├── SECURITY.md
│   ├── collect_metrics.py
│   ├── generate_inventory.py
│   ├── metrics.json
│   └── run_smoke_checks.py
├── backend/
│   ├── apps/
│   │   ├── admin_api/
│   │   │   ├── __init__.py
│   │   │   ├── admin.py
│   │   │   └── main.py
│   │   ├── admin_ui/
│   │   │   ├── routers/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── api.py
│   │   │   │   ├── candidates.py
│   │   │   │   ├── cities.py
│   │   │   │   ├── dashboard.py
│   │   │   │   ├── questions.py
│   │   │   │   ├── recruiters.py
│   │   │   │   ├── regions.py
│   │   │   │   ├── slots.py
│   │   │   │   ├── system.py
│   │   │   │   └── templates.py
│   │   │   ├── services/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── bot_service.py
│   │   │   │   ├── candidates.py
│   │   │   │   ├── cities.py
│   │   │   │   ├── dashboard.py
│   │   │   │   ├── dashboard_calendar.py
│   │   │   │   ├── kpis.py
│   │   │   │   ├── questions.py
│   │   │   │   ├── recruiters.py
│   │   │   │   ├── slots.py
│   │   │   │   └── templates.py
│   │   │   ├── static/
│   │   │   │   ├── css/
│   │   │   │   │   ├── cards.css
│   │   │   │   │   ├── forms.css
│   │   │   │   │   ├── liquid-dashboard 2.css
│   │   │   │   │   ├── liquid-dashboard.css
│   │   │   │   │   ├── lists.css
│   │   │   │   │   ├── main.css
│   │   │   │   │   ├── tahoe.css
│   │   │   │   │   └── tokens.css
│   │   │   │   ├── js/
│   │   │   │   │   ├── modules/
│   │   │   │   │   │   ├── city-selector 2.js
│   │   │   │   │   │   ├── city-selector.js
│   │   │   │   │   │   ├── dashboard-calendar 2.js
│   │   │   │   │   │   ├── dashboard-calendar.js
│   │   │   │   │   │   ├── form-dirty-guard 2.js
│   │   │   │   │   │   ├── form-dirty-guard.js
│   │   │   │   │   │   ├── form-hotkeys.js
│   │   │   │   │   │   ├── template-editor.js
│   │   │   │   │   │   └── template-presets.js
│   │   │   │   │   ├── theme-toggle.js
│   │   │   │   │   └── ux-telemetry.js
│   │   │   │   └── favicon.ico
│   │   │   ├── templates/
│   │   │   │   ├── partials/
│   │   │   │   │   ├── components.html
│   │   │   │   │   ├── form_shell.html
│   │   │   │   │   ├── layout.html
│   │   │   │   │   ├── list_toolbar.html
│   │   │   │   │   └── theme_toggle.html
│   │   │   │   ├── base.html
│   │   │   │   ├── candidates_detail.html
│   │   │   │   ├── candidates_list.html
│   │   │   │   ├── candidates_new.html
│   │   │   │   ├── cities_list.html
│   │   │   │   ├── cities_new.html
│   │   │   │   ├── index.html
│   │   │   │   ├── questions_edit.html
│   │   │   │   ├── questions_list.html
│   │   │   │   ├── recruiters_edit.html
│   │   │   │   ├── recruiters_list.html
│   │   │   │   ├── recruiters_new.html
│   │   │   │   ├── slots_list.html
│   │   │   │   ├── slots_new.html
│   │   │   │   ├── templates_edit.html
│   │   │   │   ├── templates_list.html
│   │   │   │   └── templates_new.html
│   │   │   ├── __init__.py
│   │   │   ├── app.py
│   │   │   ├── config.py
│   │   │   ├── security.py
│   │   │   ├── state.py
│   │   │   ├── timezones.py
│   │   │   └── utils.py
│   │   ├── bot/
│   │   │   ├── handlers/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── attendance.py
│   │   │   │   ├── common.py
│   │   │   │   ├── recruiter.py
│   │   │   │   ├── slots.py
│   │   │   │   ├── test1.py
│   │   │   │   └── test2.py
│   │   │   ├── __init__.py
│   │   │   ├── api_client.py
│   │   │   ├── app.py
│   │   │   ├── city_registry.py
│   │   │   ├── config.py
│   │   │   ├── keyboards.py
│   │   │   ├── main.py
│   │   │   ├── metrics.py
│   │   │   ├── reminders.py
│   │   │   ├── services.py
│   │   │   ├── state_store.py
│   │   │   ├── template_provider.py
│   │   │   ├── templates.py
│   │   │   └── test1_validation.py
│   │   └── __init__.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── bootstrap.py
│   │   ├── db.py
│   │   ├── env.py
│   │   └── settings.py
│   ├── domain/
│   │   ├── candidates/
│   │   │   ├── __init__.py
│   │   │   ├── models.py
│   │   │   └── services.py
│   │   ├── test_questions/
│   │   │   ├── __init__.py
│   │   │   └── services.py
│   │   ├── base.py
│   │   ├── default_data.py
│   │   ├── default_questions.py
│   │   ├── models.py
│   │   ├── repositories.py
│   │   └── template_stages.py
│   ├── migrations/
│   │   ├── versions/
│   │   │   ├── 0001_initial_schema.py
│   │   │   ├── 0002_seed_defaults.py
│   │   │   ├── 0003_add_slot_interview_outcome.py
│   │   │   ├── 0004_add_slot_bot_markers.py
│   │   │   ├── 0005_add_city_profile_fields.py
│   │   │   ├── 0006_add_slots_recruiter_start_index.py
│   │   │   ├── 0007_prevent_duplicate_slot_reservations.py
│   │   │   ├── 0008_add_slot_reminder_jobs.py
│   │   │   ├── 0009_add_missing_indexes.py
│   │   │   ├── 0010_add_notification_logs.py
│   │   │   ├── 0011_add_candidate_binding_to_notification_logs.py
│   │   │   ├── 0012_update_slots_candidate_recruiter_index.py
│   │   │   ├── 0013_enhance_notification_logs.py
│   │   │   ├── 0014_notification_outbox_and_templates.py
│   │   │   ├── 0015_add_kpi_weekly_table.py
│   │   │   └── __init__.py
│   │   ├── __init__.py
│   │   └── runner.py
│   └── __init__.py
├── docs/
│   ├── ux/
│   │   ├── research/
│   │   │   ├── notes-template.csv
│   │   │   ├── notes-template.md
│   │   │   └── research-plan.md
│   │   └── metrics-kpi.md
│   ├── Audit.md
│   ├── DEVEX.md
│   ├── DesignSystem.md
│   ├── IMPLEMENTATION_PLAN.md
│   ├── LOCAL_DEV.md
│   ├── TECH_STRATEGY.md
│   ├── TEST1_CONTRACTS.md
│   ├── TEST1_FIX_PLAN.md
│   ├── TEST1_GAPS_CHECKLIST.md
│   ├── TEST1_STATE_MACHINE.md
│   └── TEST1_TRACES.md
├── previews/
│   ├── ux_logs/
│   │   └── .gitignore
│   ├── .gitkeep
│   ├── candidate-detail.html
│   ├── candidate-new.html
│   ├── candidates.html
│   ├── cities.html
│   ├── index.html
│   ├── questions.html
│   ├── recruiter-new.html
│   ├── recruiters.html
│   ├── slot-new.html
│   ├── slots.html
│   └── templates.html
├── scripts/
│   ├── collect_ux.py
│   └── dev_doctor.py
├── tests/
│   ├── audit_failing_tests/
│   │   ├── test_double_booking.py
│   │   └── test_notification_logs.py
│   ├── handlers/
│   │   └── test_common_free_text.py
│   ├── services/
│   │   ├── test_bot_keyboards.py
│   │   ├── test_dashboard_and_slots.py
│   │   ├── test_dashboard_calendar.py
│   │   ├── test_slot_outcome.py
│   │   ├── test_slots_bulk.py
│   │   ├── test_slots_delete.py
│   │   ├── test_templates_and_cities.py
│   │   └── test_weekly_kpis.py
│   ├── conftest.py
│   ├── test_admin_candidates_service.py
│   ├── test_admin_recruiters_ui.py
│   ├── test_admin_slots_api.py
│   ├── test_admin_state_nullbot.py
│   ├── test_bot_app.py
│   ├── test_bot_app_smoke.py
│   ├── test_bot_confirmation_flows.py
│   ├── test_bot_integration_toggle.py
│   ├── test_bot_manual_contact.py
│   ├── test_bot_reschedule_reject.py
│   ├── test_bot_templates.py
│   ├── test_bot_test1_notifications.py
│   ├── test_bot_test1_validation.py
│   ├── test_candidate_services.py
│   ├── test_domain_repositories.py
│   ├── test_notification_retry.py
│   ├── test_reminder_service.py
│   ├── test_slot_reservations.py
│   ├── test_slots_api_tz.py
│   ├── test_state_store.py
│   ├── test_template_lookup_and_invalidation.py
│   ├── test_timezones.py
│   └── test_ui_screenshots.py
├── tools/
│   ├── recompute_weekly_kpis.py
│   └── render_previews.py
├── ui_screenshots/
│   └── .gitkeep
├── .DS_Store
├── .env.example
├── .gitattributes
├── .gitattributes 2
├── .gitignore
├── .pre-commit-config.yaml
├── AUDIT_TEST1.md
├── Audit.md
├── DesignSystem.md
├── Makefile
├── PR_DESCRIPTION.md
├── README.md
├── app_demo.py
├── bot.py
├── config.py
├── mypy.ini
├── package-lock.json
├── package.json
├── postcss.config.cjs
├── pyproject.toml
├── pytest.ini
├── requirements-dev.txt
└── tailwind.config.js
```

## Configuration Files

- **pyproject.toml**: pyproject.toml
- **requirements-dev.txt**: requirements-dev.txt
- **package.json**: package.json
- **package-lock.json**: package-lock.json
- **tailwind.config**: tailwind.config.js
- **postcss.config**: postcss.config.cjs

## Python Project Metadata

- Name: `hr-admin-ui`
- Version: `0.1.0`
- Dependencies:
  - `fastapi==0.112.0`
  - `starlette==0.37.2`
  - `uvicorn[standard]==0.30.6`
  - `itsdangerous==2.2.0`
  - `Jinja2==3.1.4`
  - `python-multipart==0.0.9`
  - `aiofiles==23.2.1`
  - `aiosqlite==0.20.0`
  - `SQLAlchemy[asyncio]==2.0.32`
  - `greenlet==3.2.2`
- Optional Dependencies:
  - **dev**:
    - `aiohttp==3.9.5`
    - `aiogram==3.10.0`
    - `redis==5.0.7`
    - `httpx==0.27.2`
    - `pytest==8.3.3`
    - `pytest-asyncio==0.23.8`
    - `playwright==1.55.0`
    - `ruff==0.6.3`
    - `black==24.4.2`
    - `isort==5.13.2`
    - `mypy==1.11.1`
    - `pre-commit==3.8.0`
    - `alembic==1.13.2`
    - `fakeredis==2.23.2`
    - `APScheduler==3.10.4`
    - `sqladmin==0.21.0`

## Node Package Metadata

- Name: `hr-admin-ui`
- Version: `0.1.0`
- Scripts:
  - `build:css`: `tailwindcss -i backend/apps/admin_ui/static/css/main.css -o backend/apps/admin_ui/static/build/main.css --minify`
- Dev Dependencies:
  - `@tailwindcss/forms`: `^0.5.7`
  - `@tailwindcss/typography`: `^0.5.12`
  - `autoprefixer`: `^10.4.20`
  - `postcss`: `^8.4.41`
  - `tailwindcss`: `^3.4.13`

## FastAPI Applications

### admin_ui
- Error: Failed to import backend.apps.admin_ui.app:app: No module named 'aiohttp'

### admin_api
- Error: Failed to import backend.apps.admin_api.main:app: No module named 'sqladmin'

## SQLAlchemy Models

- Total models: 17
  - `backend.domain.candidates.models.AutoMessage` → `auto_messages` (id, message_text, send_time, target_chat_id, is_active, created_at)
  - `backend.domain.candidates.models.Notification` → `notifications` (id, admin_chat_id, notification_type, message_text, is_sent, created_at, sent_at)
  - `backend.domain.candidates.models.QuestionAnswer` → `question_answers` (id, test_result_id, question_index, question_text, correct_answer, user_answer, attempts_count, time_spent, is_correct, overtime)
  - `backend.domain.candidates.models.TestResult` → `test_results` (id, user_id, raw_score, final_score, rating, total_time, created_at)
  - `backend.domain.candidates.models.User` → `users` (id, telegram_id, fio, city, is_active, last_activity)
  - `backend.domain.models.City` → `cities` (id, name, tz, active, responsible_recruiter_id, criteria, experts, plan_week, plan_month)
  - `backend.domain.models.KPIWeekly` → `kpi_weekly` (week_start, tested, completed_test, booked, confirmed, interview_passed, intro_day, computed_at)
  - `backend.domain.models.MessageTemplate` → `message_templates` (id, key, locale, channel, body_md, version, is_active, updated_at)
  - `backend.domain.models.NotificationLog` → `notification_logs` (id, booking_id, candidate_tg_id, type, payload, status, attempts, last_error, next_retry_at, template_key, template_version, created_at)
  - `backend.domain.models.OutboxNotification` → `outbox_notifications` (id, booking_id, type, payload_json, candidate_tg_id, recruiter_tg_id, status, attempts, created_at, locked_at, next_retry_at, last_error, correlation_id)
  - `backend.domain.models.Recruiter` → `recruiters` (id, name, tg_chat_id, tz, telemost_url, active)
  - `backend.domain.models.Slot` → `slots` (id, recruiter_id, city_id, candidate_city_id, purpose, start_utc, duration_min, status, candidate_tg_id, candidate_fio, candidate_tz, interview_outcome, test2_sent_at, rejection_sent_at, created_at, updated_at)
  - `backend.domain.models.SlotReminderJob` → `slot_reminder_jobs` (id, slot_id, kind, job_id, scheduled_at, created_at, updated_at)
  - `backend.domain.models.SlotReservationLock` → `slot_reservation_locks` (id, slot_id, candidate_tg_id, recruiter_id, reservation_date, expires_at, created_at)
  - `backend.domain.models.TelegramCallbackLog` → `telegram_callback_logs` (id, callback_id, created_at)
  - `backend.domain.models.Template` → `templates` (id, city_id, key, content)
  - `backend.domain.models.TestQuestion` → `test_questions` (id, test_id, question_index, title, payload, is_active, created_at, updated_at)

## Migrations

- Version files: 16
  - `0001_initial_schema.py` (7498 bytes)
  - `0002_seed_defaults.py` (3186 bytes)
  - `0003_add_slot_interview_outcome.py` (938 bytes)
  - `0004_add_slot_bot_markers.py` (1115 bytes)
  - `0005_add_city_profile_fields.py` (1199 bytes)
  - `0006_add_slots_recruiter_start_index.py` (684 bytes)
  - `0007_prevent_duplicate_slot_reservations.py` (1803 bytes)
  - `0008_add_slot_reminder_jobs.py` (1145 bytes)
  - `0009_add_missing_indexes.py` (4827 bytes)
  - `0010_add_notification_logs.py` (3264 bytes)
  - `0011_add_candidate_binding_to_notification_logs.py` (5202 bytes)
  - `0012_update_slots_candidate_recruiter_index.py` (4266 bytes)
  - `0013_enhance_notification_logs.py` (2733 bytes)
  - `0014_notification_outbox_and_templates.py` (10290 bytes)
  - `0015_add_kpi_weekly_table.py` (1992 bytes)
  - `__init__.py` (34 bytes)

## Tests

- Test files: 34
- Test functions: 6
  - `tests/audit_failing_tests/test_double_booking.py`
  - `tests/audit_failing_tests/test_notification_logs.py`
  - `tests/handlers/test_common_free_text.py`
  - `tests/services/test_bot_keyboards.py`
  - `tests/services/test_dashboard_and_slots.py`
  - `tests/services/test_dashboard_calendar.py`
  - `tests/services/test_slot_outcome.py`
  - `tests/services/test_slots_bulk.py`
  - `tests/services/test_slots_delete.py`
  - `tests/services/test_templates_and_cities.py`
  - `tests/services/test_weekly_kpis.py`
  - `tests/test_admin_candidates_service.py`
  - `tests/test_admin_recruiters_ui.py`
  - `tests/test_admin_slots_api.py`
  - `tests/test_admin_state_nullbot.py`
  - `tests/test_bot_app.py`
  - `tests/test_bot_app_smoke.py`
  - `tests/test_bot_confirmation_flows.py`
  - `tests/test_bot_integration_toggle.py`
  - `tests/test_bot_manual_contact.py`
  - `tests/test_bot_reschedule_reject.py`
  - `tests/test_bot_templates.py`
  - `tests/test_bot_test1_notifications.py`
  - `tests/test_bot_test1_validation.py`
  - `tests/test_candidate_services.py`
  - `tests/test_domain_repositories.py`
  - `tests/test_notification_retry.py`
  - `tests/test_reminder_service.py`
  - `tests/test_slot_reservations.py`
  - `tests/test_slots_api_tz.py`
  - `tests/test_state_store.py`
  - `tests/test_template_lookup_and_invalidation.py`
  - `tests/test_timezones.py`
  - `tests/test_ui_screenshots.py`

## CI Workflows

- `.github/workflows/ci.yml`
- `.github/workflows/ui-preview.yml`

## Potential Secret Matches

- `.env.example`
- `DesignSystem.md`
- `README.md`
- `audit/CSS_SIZE.md`
- `audit/DIAGNOSIS.md`
- `audit/INVENTORY.json`
- `audit/INVENTORY.md`
- `audit/METRICS.md`
- `audit/QUALITY.md`
- `audit/REPORT.md`
- `audit/SECURITY.md`
- `audit/collect_metrics.py`
- `audit/generate_inventory.py`
- `audit/metrics.json`
- `audit/run_smoke_checks.py`
- `backend/apps/admin_ui/app.py`
- `backend/apps/admin_ui/routers/slots.py`
- `backend/apps/admin_ui/security.py`
- `backend/apps/admin_ui/services/bot_service.py`
- `backend/apps/admin_ui/services/templates.py`
- `backend/apps/admin_ui/state.py`
- `backend/apps/admin_ui/static/js/modules/template-editor.js`
- `backend/apps/admin_ui/templates/base.html`
- `backend/apps/bot/api_client.py`
- `backend/apps/bot/app.py`
- `backend/apps/bot/config.py`
- `backend/apps/bot/services.py`
- `backend/core/settings.py`
- `config.py`
- `docs/DEVEX.md`
- `docs/DesignSystem.md`
- `docs/LOCAL_DEV.md`
- `docs/TECH_STRATEGY.md`
- `previews/candidate-detail.html`
- `previews/candidate-new.html`
- `previews/candidates.html`
- `previews/cities.html`
- `previews/index.html`
- `previews/questions.html`
- `previews/recruiter-new.html`
- `previews/recruiters.html`
- `previews/slot-new.html`
- `previews/slots.html`
- `previews/templates.html`
- `scripts/dev_doctor.py`
- `tests/test_admin_recruiters_ui.py`
- `tests/test_admin_slots_api.py`
- `tests/test_admin_state_nullbot.py`
- `tests/test_bot_app.py`
- `tests/test_bot_integration_toggle.py`
- `tests/test_slots_api_tz.py`

## Static Assets

- `backend/apps/admin_ui/static`
  - `backend/apps/admin_ui/static/build/main.css`
  - `backend/apps/admin_ui/static/css/cards.css`
  - `backend/apps/admin_ui/static/css/forms.css`
  - `backend/apps/admin_ui/static/css/liquid-dashboard 2.css`
  - `backend/apps/admin_ui/static/css/liquid-dashboard.css`
  - `backend/apps/admin_ui/static/css/lists.css`
  - `backend/apps/admin_ui/static/css/main.css`
  - `backend/apps/admin_ui/static/css/tahoe.css`
  - `backend/apps/admin_ui/static/css/tokens.css`
  - `backend/apps/admin_ui/static/favicon.ico`
  - `backend/apps/admin_ui/static/js/modules/city-selector 2.js`
  - `backend/apps/admin_ui/static/js/modules/city-selector.js`
  - `backend/apps/admin_ui/static/js/modules/dashboard-calendar 2.js`
  - `backend/apps/admin_ui/static/js/modules/dashboard-calendar.js`
  - `backend/apps/admin_ui/static/js/modules/form-dirty-guard 2.js`
  - `backend/apps/admin_ui/static/js/modules/form-dirty-guard.js`
  - `backend/apps/admin_ui/static/js/modules/form-hotkeys.js`
  - `backend/apps/admin_ui/static/js/modules/template-editor.js`
  - `backend/apps/admin_ui/static/js/modules/template-presets.js`
  - `backend/apps/admin_ui/static/js/theme-toggle.js`
  - `backend/apps/admin_ui/static/js/ux-telemetry.js`
- Favicons:
  - `backend/apps/admin_ui/static/favicon.ico`
- CSS builds:
  - `backend/apps/admin_ui/static/build/main.css`
  - `backend/apps/admin_ui/static/css/main.css`
