# Audit Report

## Findings

### P1 — `slots.updated_at` never refreshes on updates
- **Evidence:** The `Slot.updated_at` column is defined with only a default timestamp and no `onupdate`, so it never changes after the row is inserted.【F:backend/domain/models.py†L86-L118】
- **Impact:** Admin UI timelines, reminder schedulers, and potential reporting that rely on the "last touched" timestamp receive stale data. This makes it impossible to distinguish fresh reservations from legacy ones and complicates investigating stuck reminders.
- **Fix plan:** Add `onupdate=datetime.now(timezone.utc)` to the ORM column (and matching Alembic migration to backfill and adjust default). Cover with a regression test around `approve_slot`/`reject_slot` to ensure `updated_at` advances.

### P1 — Missing indexes on hot query fields (`slots.candidate_tg_id`, `auto_messages.target_chat_id`)
- **Evidence:** Candidate dashboards and analytics run `IN` and correlated subqueries on `Slot.candidate_tg_id` and `AutoMessage.target_chat_id`, but the schema lacks supporting indexes.【F:backend/apps/admin_ui/services/candidates.py†L199-L275】【F:backend/migrations/versions/0001_initial_schema.py†L138-L147】
- **Impact:** At scale, these queries devolve into full scans, degrading the admin panel (filters, analytics) and reminder lookups, increasing latency and DB load.
- **Fix plan:** Create btree indexes on both columns via Alembic (e.g. `ix_slots_candidate_tg_id`, `ix_auto_messages_target_chat_id`). Update tests or add new ones exercising the candidate service with large fixture sets to assert performance-sensitive paths use the indexes (via EXPLAIN in integration tests or by monitoring query count/time).

### P2 — Reservation rejects on recruiter/city mismatch surface as “slot taken”
- **Evidence:** `reserve_slot` returns the generic `slot_taken` status when the selected recruiter or city does not match expectations.【F:backend/domain/repositories.py†L278-L282】 The bot reuses the "slot already taken" copy, misleading candidates when the actual problem is choosing a slot from another region.
- **Impact:** Users receive confusing feedback, retry the same action, or escalate to support, increasing manual load.
- **Fix plan:** Introduce explicit statuses (e.g. `wrong_recruiter`, `wrong_city`), propagate them through bot services to render dedicated messages, and add tests covering mismatched recruiter/city flows.

### P2 — Bot city cache never invalidated after admin changes
- **Evidence:** `CandidateCityRegistry.invalidate()` exists but nothing calls it from admin flows (city CRUD, recruiter-city reassignment).【F:backend/apps/bot/city_registry.py†L12-L96】
- **Impact:** The bot can serve stale city/recruiter availability for up to the cache TTL (5 minutes), causing candidates to see outdated choices right after an admin update.
- **Fix plan:** Wire cache invalidation into admin city/recruiter update paths (e.g. services in `backend/apps/admin_ui/services/cities.py` and recruiter update handlers). Add async tests ensuring a newly created city appears immediately after update via cache invalidation.

### P2 — Reminder prompt lacks “request reschedule” option required by flow
- **Evidence:** The 2-hour reminder sends `kb_attendance_confirm` with only “Подтверждаю”/“Не смогу”.【F:backend/apps/bot/keyboards.py†L174-L183】【F:backend/apps/bot/reminders.py†L236-L244】 The new recruiting flow mandates three buttons including “Просьба перенести”.
- **Impact:** Candidates cannot request a reschedule straight from the reminder, breaking the stated UX and forcing manual outreach.
- **Fix plan:** Extend the keyboard to include the third action, add corresponding handler logic, and cover via reminder service tests ensuring the keyboard renders all buttons.

### P3 — Coverage gap: recruiter/city mismatch reservation path
- **Evidence:** Test suite exercises duplicate reservations and locks but does not cover the wrong recruiter/city branches in `reserve_slot`.【F:backend/domain/repositories.py†L278-L282】【F:tests/test_slot_reservations.py†L1-L120】
- **Impact:** Future changes risk regressing the new explicit error handling without automated detection.
- **Fix plan:** Add parametrised tests in `tests/test_slot_reservations.py` to assert the new dedicated statuses and message mapping.

