# Critical User Flows

## Flow 1. Recruiter login and scoped dashboard access

### Preconditions
- Recruiter has active `AuthAccount`.
- Recruiter is linked to at least one city and has candidate/slot data.

### Steps
1. Open `/app/login` or call `/auth/login`.
2. Authenticate as recruiter.
3. Open `/api/profile`, `/api/dashboard/summary`, `/api/candidates`, `/api/slots`.

### Expected result
- Auth succeeds.
- Recruiter sees only scoped data.
- Foreign candidates/slots/cities are hidden as `404`, not leaked as `403` or visible objects.

### Failure points
- Bearer/session parity mismatch.
- `responsible_recruiter_id` scoping diverges from `recruiter_cities` city ACL.
- Cached dashboard payload leaks unscoped data.

### Side effects
- Session cookie or bearer token issued.
- Audit trail should record login and protected actions.

### Regression zones
- `backend/apps/admin_ui/security.py`
- `backend/core/scoping.py`
- `backend/apps/admin_ui/app.py`
- `backend/apps/admin_ui/services/dashboard.py`
- `backend/apps/admin_ui/services/candidates.py`

### Manual test
- Log in as admin and recruiter in separate browser contexts.
- Compare counts for candidates, slots, cities, dashboard widgets.
- Request foreign object ids directly and confirm `404` for recruiter.

### Automation
- API integration suite for admin/recruiter/unauthenticated.
- Playwright recruiter-vs-admin smoke.

## Flow 2. Manual candidate creation and ownership assignment

### Preconditions
- Admin or recruiter with city scope.
- Recruiter and city dictionaries exist.

### Steps
1. Open candidate creation route or call `POST /api/candidates`.
2. Create candidate with/without Telegram identifier.
3. Optionally assign responsible recruiter.
4. Open candidate detail.

### Expected result
- Candidate appears in correct pipeline/status.
- Ownership fields are correct.
- Recruiter cannot create or mutate candidates outside scope.

### Failure points
- Validation drift between frontend and backend.
- Missing recruiter/city ownership checks.
- HH URL parsing or enrichment errors affecting detail page.

### Side effects
- Candidate record created/updated.
- Optional invite token or downstream status initialization.

### Regression zones
- `backend/apps/admin_ui/services/candidates.py`
- `backend/apps/admin_ui/routers/api.py`
- `frontend/app/src/app/routes/app/candidate-new.tsx`

### Manual test
- Create candidate with minimal fields, then with Telegram and city/recruiter references.
- Verify list, detail, and assignment fields.

### Automation
- API CRUD suite with admin and recruiter principals.
- Frontend form smoke.

## Flow 3. Candidate pipeline progression after Test 1

### Preconditions
- Candidate exists with `lead`, `contacted`, or `invited` status.

### Steps
1. Trigger Test 1 completion or set status through workflow action.
2. Candidate moves to `test1_completed` then `waiting_slot` or `slot_pending`.
3. Open candidate detail and pipeline view.

### Expected result
- Only valid `STATUS_TRANSITIONS` are accepted.
- Retreats are no-op, invalid transitions raise conflict.
- UI actions reflect current allowed transitions.

### Failure points
- Drift between `status.py`, workflow API, and UI action rendering.
- Duplicate side effects when same action repeats.

### Side effects
- Analytics events.
- Template and bot preparation for next steps.

### Regression zones
- `backend/domain/candidates/status.py`
- `backend/domain/candidates/status_service.py`
- `backend/domain/candidates/actions.py`
- `backend/apps/admin_ui/services/candidates.py`

### Manual test
- Attempt legal and illegal transitions from several statuses.
- Repeat the same transition twice.

### Automation
- Status transition matrix tests.
- Workflow API contract tests.

## Flow 4. Recruiter schedules interview slot for candidate

### Preconditions
- Candidate is eligible for scheduling.
- Free slot exists.

### Steps
1. Open candidate detail or slots flow.
2. Request available slots.
3. Schedule slot for candidate.
4. Optionally approve/reject/reschedule.

### Expected result
- Slot becomes `pending` or `booked` according to path.
- Candidate status updates consistently.
- Duplicate active interview/introduction conflicts are blocked deterministically.

### Failure points
- Double booking under race.
- Conflict mapped as `500` instead of business `409`.
- Scope violations on recruiter-owned slots.

### Side effects
- Reservation lock, notification log, outbox event, candidate status update.

### Regression zones
- `backend/domain/repositories.py`
- `backend/domain/slot_service.py`
- `backend/apps/admin_ui/services/slots.py`
- `backend/apps/admin_ui/routers/api.py`

### Manual test
- Schedule same candidate twice concurrently.
- Schedule against foreign recruiter slot.
- Reject and reschedule with notification services disabled.

### Automation
- Postgres-backed integration tests with concurrent requests.
- Playwright critical scheduling flow.

## Flow 5. Candidate self-service booking via Telegram WebApp

### Preconditions
- Candidate is authenticated with valid Telegram WebApp initData.
- Candidate exists in `users`.
- Free slot exists.

### Steps
1. Call `/api/webapp/me`.
2. Fetch `/api/webapp/slots`.
3. `POST /api/webapp/booking`.
4. Optionally `POST /api/webapp/reschedule` or `/cancel`.

### Expected result
- Booking ownership is tied to authenticated Telegram user.
- Slot transitions remain valid.
- Cross-purpose conflicts are blocked.

### Failure points
- SQL path diverges from domain reservation logic.
- Missing idempotency or locking between booking/reschedule/cancel.
- Candidate can manipulate someone else’s booking.

### Side effects
- Slot row updated directly.
- Analytics events logged.

### Regression zones
- `backend/apps/admin_api/webapp/auth.py`
- `backend/apps/admin_api/webapp/routers.py`

### Manual test
- Use valid and expired initData.
- Book, reschedule, and cancel same slot from parallel clients.

### Automation
- API integration tests on Postgres.
- Replay suite with real signed initData fixture and clock skew cases.

## Flow 6. Interview outcome and Test 2 dispatch

### Preconditions
- Candidate has active interview slot.
- Recruiter or bot flow reaches outcome decision.

### Steps
1. Submit slot outcome or workflow action.
2. System transitions candidate to `test2_sent`, `test2_completed`, or rejection path.
3. Candidate detail and notifications update.

### Expected result
- Status changes follow contract.
- Test 2 messages and templates are sent once.
- Repeat submission is idempotent.

### Failure points
- Duplicate Test 2 sends.
- Bot unavailable but status already changed.
- Notification log inconsistency.

### Side effects
- Outbox entries, message logs, analytics, report generation.

### Regression zones
- `backend/apps/bot/services.py`
- `backend/apps/admin_ui/services/slots.py`
- `backend/apps/admin_ui/services/candidates.py`

### Manual test
- Submit outcome twice.
- Repeat after temporary bot outage.

### Automation
- Existing idempotency tests plus degraded bot service tests.
- Add UI/API parity checks.

## Flow 7. Intro day scheduling and handoff

### Preconditions
- Candidate passed interview/test stage.
- Intro day slot exists or can be created.
- Max feature flags/routes are configured if handoff is enabled.

### Steps
1. Schedule intro day from candidate detail/API.
2. Cancel active interview slot if required.
3. Dispatch intro-day invitation.
4. Send Max sales handoff when configured.

### Expected result
- Candidate holds one active purpose at a time.
- Interview slot and assignment cleanup are consistent.
- Max handoff chooses correct recruiter/city/default route.

### Failure points
- Duplicate intro-day scheduling.
- Missing cleanup of old interview assignment.
- Max routing misconfiguration or silent adapter failure.

### Side effects
- Slot creation/update, outbox entries, Max group message, candidate status change.

### Regression zones
- `backend/apps/admin_ui/services/candidates.py`
- `backend/apps/admin_ui/services/max_sales_handoff.py`
- `backend/domain/repositories.py`

### Manual test
- Schedule intro day twice.
- Schedule with recruiter and city route configs.
- Simulate Max adapter unavailable.

### Automation
- API integration tests for handoff enabled/disabled/no-route/adapter-failure cases.

## Flow 8. Recruiter sends manual chat message to candidate

### Preconditions
- Candidate has Telegram or compatible messenger identifier.
- Recruiter opens candidate chat.

### Steps
1. Open `/api/candidates/{candidate_id}/chat`.
2. `POST /api/candidates/{candidate_id}/chat` with `client_request_id`.
3. If failed, `POST /api/candidates/{candidate_id}/chat/{message_id}/retry`.

### Expected result
- Duplicate `client_request_id` returns same message, not duplicate send.
- Rate limit is enforced predictably.
- Recruiter sees message status that matches actual send outcome.

### Failure points
- In-memory rate limit breaks in multi-worker setup.
- Chat marked sent without provider acceptance.
- Retry duplicates the send.

### Side effects
- `ChatMessage` persisted, bot send invoked, optional conversation mode updated.

### Regression zones
- `backend/apps/admin_ui/services/chat.py`
- `backend/apps/admin_ui/services/bot_service.py`
- `backend/domain/candidates/services.py`

### Manual test
- Send same message twice with same `client_request_id`.
- Exceed message rate limit.
- Retry after forced provider error.

### Automation
- Service/API tests for duplicate, failed, retried, and multi-worker rate-limit behavior.

## Flow 9. Notifications worker processes queued delivery with retry and DLQ semantics

### Preconditions
- Outbox contains due entries.
- Broker and/or direct fallback path available.

### Steps
1. Worker claims batch.
2. Sends notification.
3. On transient failure schedules retry.
4. On terminal failure marks failed or DLQ.

### Expected result
- No double-send under concurrent consumers.
- Retry delay follows policy or provider hint.
- Metrics and health reflect queue depth and failures.

### Failure points
- Stale locks not released.
- Duplicate broker delivery.
- Failure class miscategorized as retryable.

### Side effects
- Outbox updates, logs, metrics, broker publish/consume.

### Regression zones
- `backend/apps/bot/services.py`
- `backend/domain/repositories.py`
- `backend/apps/admin_ui/state.py`

### Manual test
- Force Telegram retry-after.
- Force forbidden/unauthorized failure.
- Restart worker mid-queue.

### Automation
- Redis/Postgres integration tests with failure injection.

## Flow 10. Release startup and migration run

### Preconditions
- Fresh or partially migrated Postgres database.
- Dedicated migration role configured.

### Steps
1. Run `python scripts/run_migrations.py`.
2. Start `admin_ui`, `admin_api`, `bot`, `max_bot`.
3. Probe `/ready` and `/health`.

### Expected result
- Migration chain upgrades cleanly.
- Runtime starts without trying to perform forbidden DDL as app user.
- Health endpoints reflect degraded dependencies accurately.

### Failure points
- Custom migration runner chain mismatch.
- SQLite path hides PostgreSQL-only SQL issues.
- Startup side effects create bot/notification failures before app is ready.

### Side effects
- Schema changes, bootstrap seed operations, cache/broker/bot initialization.

### Regression zones
- `backend/migrations/runner.py`
- `scripts/run_migrations.py`
- `backend/apps/admin_ui/app.py`
- `backend/apps/admin_ui/state.py`

### Manual test
- Run against clean Postgres and app-role-only runtime.
- Start with Redis down, then with bot disabled, then with Max disabled.

### Automation
- Migration contract in PR and nightly, plus staging deploy smoke.
