# Formal Gate Sprint 1/2

- Generated at: `2026-03-01T08:08:51.071759+00:00`
- Overall: `fail`
- Sprint 1 Gate: `fail`
- Sprint 2 Gate: `manual_pending`

## Criteria

| ID | Sprint | Criterion | Status | Evidence |
| --- | --- | --- | --- | --- |
| `S1-1` | `Sprint 1` | Smoke/a11y/focus e2e green | `pass` | frontend_e2e_gate log |
| `S1-2` | `Sprint 1` | Core CRUD UI/API flows without blocking regressions | `fail` | backend_crud_regression + frontend checks |
| `S1-3` | `Sprint 1` | No P1 UX defects in slots/cities/candidates | `manual_pending` | manual QA sign-off |
| `S1-4` | `Sprint 1` | Live demo gate: city -> slot -> candidate | `manual_pending` | demo protocol sign-off |
| `S2-1` | `Sprint 2` | Unauthorized access to closed endpoints returns 401/403 | `pass` | backend_security_regression |
| `S2-2` | `Sprint 2` | Security regression covers API and websocket | `pass` | tests/test_admin_surface_hardening.py |
| `S2-3` | `Sprint 2` | No critical open routes without auth in admin surface | `pass` | route_inventory.md |
| `S2-4` | `Sprint 2` | Internal security review sign-off | `manual_pending` | security review record |

## Automated Checks

| Check | Status | Duration (s) | Command |
| --- | --- | --- | --- |
| `backend_security_regression` | `pass` | `11.8` | `/Users/mikhail/Projects/recruitsmart_admin/.venv/bin/pytest tests/test_admin_surface_hardening.py tests/test_calendar_hub_scope.py tests/test_perf_metrics_endpoint.py tests/test_admin_auth_no_basic_challenge.py tests/test_rate_limiting.py -q` |
| `backend_crud_regression` | `pass` | `15.7` | `/Users/mikhail/Projects/recruitsmart_admin/.venv/bin/pytest tests/test_admin_slots_api.py tests/test_admin_candidates_service.py -q` |
| `frontend_lint` | `pass` | `1.8` | `npm run lint` |
| `frontend_typecheck` | `fail` | `3.6` | `npm run typecheck` |
| `frontend_unit` | `pass` | `1.5` | `npm run test` |
| `frontend_build` | `pass` | `1.6` | `npm run build` |
| `frontend_e2e_gate` | `pass` | `29.4` | `npx playwright test tests/e2e/smoke.spec.ts tests/e2e/a11y.spec.ts tests/e2e/focus.cities.spec.ts tests/e2e/focus.slots.spec.ts tests/e2e/regression-flow.spec.ts` |

## Route Inventory

- Status: `pass`
- Findings: `0`
- Inventory artifact: `/Users/mikhail/Projects/recruitsmart_admin/.local/gates/sprint1_2/route_inventory.md`

## Manual Sign-Off

- Sprint 1 UX sign-off: `manual_pending`
- Sprint 1 demo sign-off: `manual_pending`
- Sprint 2 security review sign-off: `manual_pending`

## Artifacts

- JSON: `/Users/mikhail/Projects/recruitsmart_admin/.local/gates/sprint1_2/latest.json`
- Markdown: `/Users/mikhail/Projects/recruitsmart_admin/.local/gates/sprint1_2/latest.md`
