# Implementation Plan

## 1. Data layer hardening
- Patch `backend/domain/models.py` and new Alembic migration to add `onupdate` to `Slot.updated_at` and create indexes for `slots.candidate_tg_id` / `auto_messages.target_chat_id`.
- Update SQLAlchemy models to mirror the indexes; ensure migrations run in both async and sync contexts.
- Extend existing repository tests (`tests/test_slot_reservations.py`, candidate services suite) to assert the new timestamp behaviour and absence of full scans (e.g. compare query counts with/without filters).

## 2. Slot reservation UX
- Enhance `reserve_slot` to surface dedicated `wrong_recruiter` / `wrong_city` statuses; adjust bot services (`handle_pick_slot`, templates) to render precise hints instead of the generic “slot taken”.
- Add regression tests covering mismatch scenarios and expected replies.

## 3. Recruiter workflow & messaging
- Refresh templates (`backend/apps/bot/templates.py` and city-specific overrides) with the new congratulatory copy and reminder text from the product brief.
- Ensure recruiter confirmation (`handle_approve_slot`) injects updated copy (name, date/time, 15–20 minute duration) and attaches manual contact fallback when `tg_chat_id` missing.

## 4. Candidate scheduling fallback & cache coherence
- After admin changes to cities/recruiters, call `invalidate_candidate_cities_cache()` so the bot immediately reflects new availability.
- Revisit manual-contact fallback keyboard to include the region-specific Telegram link in line with the “Свяжитесь с нами” CTA when no slots exist.

## 5. Reminder flow upgrade
- Extend `kb_attendance_confirm` (and handler logic) to include the third button “Просьба перенести”; implement a new callback path notifying the recruiter/recording the request.
- Update the 2-hour reminder dispatcher to send the revised text and keyboard; back the change with reminder service tests ensuring all three buttons appear.

## 6. Validation & regression
- Run full pytest suite (after installing dependencies) and lint where applicable.
- Smoke-test bot flows locally: Test1 completion → recruiter selection → slot booking → approval → reminder path.
- Prepare PR notes summarising behaviour changes and migration steps.

