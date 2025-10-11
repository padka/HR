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
│   └── generate_inventory.py
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
│   │   │   │   ├── questions.py
│   │   │   │   ├── recruiters.py
│   │   │   │   ├── slots.py
│   │   │   │   └── templates.py
│   │   │   ├── static/
│   │   │   │   ├── css/
│   │   │   │   │   ├── cards.css
│   │   │   │   │   ├── forms.css
│   │   │   │   │   ├── lists.css
│   │   │   │   │   ├── main.css
│   │   │   │   │   ├── tahoe.css
│   │   │   │   │   └── tokens.css
│   │   │   │   ├── js/
│   │   │   │   │   └── modules/
│   │   │   │   │       ├── form-hotkeys.js
│   │   │   │   │       ├── template-editor.js
│   │   │   │   │       └── template-presets.js
│   │   │   │   └── favicon.ico
│   │   │   ├── templates/
│   │   │   │   ├── partials/
│   │   │   │   │   ├── components.html
│   │   │   │   │   ├── form_shell.html
│   │   │   │   │   └── list_toolbar.html
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
│   │   │   └── __init__.py
│   │   ├── __init__.py
│   │   └── runner.py
│   └── __init__.py
├── docs/
│   ├── Audit.md
│   ├── DesignSystem.md
│   ├── IMPLEMENTATION_PLAN.md
│   ├── TEST1_CONTRACTS.md
│   ├── TEST1_FIX_PLAN.md
│   ├── TEST1_GAPS_CHECKLIST.md
│   ├── TEST1_STATE_MACHINE.md
│   └── TEST1_TRACES.md
├── previews/
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
├── tests/
│   ├── audit_failing_tests/
│   │   ├── test_double_booking.py
│   │   └── test_notification_logs.py
│   ├── handlers/
│   │   └── test_common_free_text.py
│   ├── services/
│   │   ├── test_bot_keyboards.py
│   │   ├── test_dashboard_and_slots.py
│   │   ├── test_slot_outcome.py
│   │   ├── test_slots_bulk.py
│   │   ├── test_slots_delete.py
│   │   └── test_templates_and_cities.py
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
│   └── render_previews.py
├── ui_screenshots/
│   └── .gitkeep
├── .DS_Store
├── .env.example
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
- Optional Dependencies:
  - **dev**:
    - `fastapi`
    - `uvicorn`
    - `jinja2`
    - `sqlalchemy[asyncio]`
    - `aiogram`
    - `aiosqlite`
    - `redis`
    - `httpx`
    - `pytest`
    - `pytest-asyncio`
    - `playwright`
    - `ruff`

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
- Error: Failed to import backend.apps.admin_ui.app:app: No module named 'fastapi'

### admin_api
- Error: Failed to import backend.apps.admin_api.main:app: No module named 'fastapi'

## SQLAlchemy Models

- Error: Failed to import models: No module named 'sqlalchemy'

## Migrations

- Version files: 15
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
  - `__init__.py` (34 bytes)

## Tests

- Test files: 32
- Test functions: 4
  - `tests/audit_failing_tests/test_double_booking.py`
  - `tests/audit_failing_tests/test_notification_logs.py`
  - `tests/handlers/test_common_free_text.py`
  - `tests/services/test_bot_keyboards.py`
  - `tests/services/test_dashboard_and_slots.py`
  - `tests/services/test_slot_outcome.py`
  - `tests/services/test_slots_bulk.py`
  - `tests/services/test_slots_delete.py`
  - `tests/services/test_templates_and_cities.py`
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
- `audit/generate_inventory.py`
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
- `docs/DesignSystem.md`
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
- `tests/test_admin_recruiters_ui.py`
- `tests/test_admin_slots_api.py`
- `tests/test_admin_state_nullbot.py`
- `tests/test_bot_app.py`
- `tests/test_slots_api_tz.py`

## Static Assets

- `backend/apps/admin_ui/static`
  - `backend/apps/admin_ui/static/build/main.css`
  - `backend/apps/admin_ui/static/css/main.css`
  - `backend/apps/admin_ui/static/css/tokens.css`
  - `backend/apps/admin_ui/static/favicon.ico`
  - `backend/apps/admin_ui/static/js/modules/city-selector.js`
  - `backend/apps/admin_ui/static/js/modules/dashboard-calendar.js`
  - `backend/apps/admin_ui/static/js/modules/form-dirty-guard.js`
  - `backend/apps/admin_ui/static/js/modules/form-hotkeys.js`
  - `backend/apps/admin_ui/static/js/modules/template-editor.js`
  - `backend/apps/admin_ui/static/js/modules/template-presets.js`
- Favicons:
  - `backend/apps/admin_ui/static/favicon.ico`
- CSS builds:
  - `backend/apps/admin_ui/static/build/main.css`
  - `backend/apps/admin_ui/static/css/main.css`
