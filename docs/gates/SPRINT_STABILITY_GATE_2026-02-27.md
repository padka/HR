# Sprint Stability Gate — 2026-02-27

## Scope
- P0 auth/bearer correctness
- P0 slot booking conflict mapping
- P0/P1 status funnel consistency regression pack
- P1 AI Interview Script readiness checks
- P1 top-3 UI smoke + mobile + a11y
- P1 load baseline for `GET /api/candidates`

## Implemented backend fixes
1. Bearer token strictness: invalid/expired bearer no longer falls back to session/dev auth.
2. Slot booking conflict hardening:
   - deterministic `409 candidate_already_booked`
   - deterministic `400 slot_not_free`
   - controlled `400 slot_booking_failed` for unexpected reservation errors
   - `existing_slot_id` lookup in conflict path.
3. Candidates list performance hardening:
   - replaced full message-history fetch per candidate with SQL aggregates (`count`) + windowed latest message query.
   - removed per-page overfetch of `AutoMessage` rows for candidate cards.

## Regression matrix (executed)
| Area | Suite | Result |
|---|---|---|
| Auth + booking API | `tests/test_profile_settings_api.py tests/test_admin_slots_api.py` | ✅ 30 passed |
| Status + schedule flows | `tests/test_admin_candidate_schedule_slot.py tests/test_admin_candidates_service.py` (targeted) | ✅ 4 passed |
| Reschedule + transition guards | `tests/test_slot_assignment_reschedule_replace.py tests/test_reschedule_requests_scoping.py tests/test_status_service_transitions.py tests/test_admin_candidate_status_update.py` | ✅ 16 passed |
| AI interview script | `tests/test_interview_script_ai.py tests/test_interview_script_feedback.py tests/test_openai_provider_responses_api.py` | ✅ 12 passed |
| Candidate services | `tests/test_admin_candidates_service.py tests/test_candidate_services.py` | ✅ 21 passed |
| Combined backend pack | selected reliability pack | ✅ 59 passed |
| Frontend unit smoke | `ui-cosmetics + incoming-demo + slots.filters` | ✅ 10 passed |
| E2E desktop+mobile+a11y | Playwright grep `ui cosmetics smoke|a11y` | ✅ 11 passed |

## Load baseline (`GET /api/candidates`)
Tool: `autocannon`

### Baseline before optimization
- 20 connections, 60s:
  - avg RPS: **141.85**
  - p50: **124ms**
  - p90: **234ms**
  - p97.5: **261ms**
  - p99: **385ms**
  - error rate: **0.0%**
- 40 connections, 60s:
  - avg RPS: **140.9**
  - p50: **257ms**
  - p90: **389ms**
  - p97.5: **436ms**
  - p99: **469ms**
  - error rate: **0.0%**

### Baseline after optimization
- 20 connections, 45s:
  - avg RPS: **162.98**
  - p50: **110ms**
  - p90: **211ms**
  - p97.5: **224ms**
  - p99: **230ms**
  - error rate: **0.0%**

### Stress check (degradation point)
- high-pressure profile produced 503 bursts (expected beyond capacity envelope), identifying knee above stable envelope.

Artifacts:
- `.tmp/load_sprint/candidates_baseline_20c.json`
- `.tmp/load_sprint/candidates_baseline_40c.json`
- `.tmp/load_sprint/candidates_postopt_20c.json`
- `.tmp/load_sprint/candidates_steady.json`
- `.tmp/load_sprint/candidates_spike.json`

## Known residuals
1. Full staging-only checks (real infra alerts/telemetry wiring) require staging runtime and are tracked separately.
2. For higher concurrency envelopes (`40c+`), additional slot/test query trimming may still be needed for stricter p95 budgets.

## Release recommendation
- Ready for `testing` branch sanity pass for covered scope.
- Keep capacity guard near stable envelope until additional query/index optimization for higher concurrency.
