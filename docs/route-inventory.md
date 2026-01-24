# Route Inventory (admin_ui) — Auth & Scoping (100% covered)

Status legend: ✅ done, ⏳ todo

| Route | Entity | Action | Guard | Ownership check | Status |
| --- | --- | --- | --- | --- | --- |
| GET /candidates, /detailization | candidate | read list | `require_principal` | `list_candidates` → scope_candidates (users.responsible_recruiter_id) | ✅ |
| GET /candidates/{id} | candidate | read detail | `require_principal` | `get_candidate_detail` enforces responsible_recruiter_id | ✅ |
| POST /candidates/create | candidate | create | `require_principal` | recruiter principal → responsible_recruiter_id forced = principal.id | ✅ |
| POST /candidates/{id}/update/toggle/status/delete | candidate | write/delete | `require_principal` | `update_candidate`/`toggle_candidate_activity`/`update_candidate_status`/`delete_candidate` all check responsible_recruiter_id | ✅ |
| POST /candidates/{id}/invite-token | candidate | write | `require_principal` | ensure_candidate_scope before token; service checks owner | ✅ |
| GET /candidates/{id}/resend-test2 | candidate/slot | write | `require_principal` | ensure_candidate_scope; slot lookup filtered; slot outcome uses scoped set_slot_outcome | ✅ |
| POST /candidates/{id}/interview-notes (+download) | candidate | write/read | `require_principal` | ensure_candidate_scope + `save_interview_notes` owner check | ✅ |
| POST /candidates/{id}/slots/{slot_id}/approve | slot | write | `require_principal` | ensure_candidate_scope + ensure_slot_scope | ✅ |
| GET/POST /candidates/{id}/schedule-slot | slot | create | `require_principal` | candidate detail scoped; recruiter principal only self; schedule_manual_candidate_slot checks principal | ✅ |
| GET/POST /candidates/{id}/schedule-intro-day, assign-city | slot/candidate | create/update | `require_principal` | candidate detail scoped; recruiter principal blocked from assigning other recruiters | ✅ |
| POST /candidates/delete-all | candidate | bulk delete | `require_admin` | admin-only route | ✅ |
| GET /slots | slot | read list | `require_principal` | list_slots -> scope_slots (recruiter_id) | ✅ |
| GET /slots/{id} | slot | read detail | `require_principal` | ensure_slot_scope | ✅ |
| POST /slots/create, /bulk_create, POST /slots (API) | slot | create | `require_principal` | recruiter principal → recruiter_id forced=self; city assignment validated | ✅ |
| PUT /slots/{id} | slot | write | `require_principal` | ensure_slot_scope | ✅ |
| POST/DELETE /slots/{id}/delete | slot | delete | `require_principal` | ensure_slot_scope within delete_slot | ✅ |
| POST /slots/delete_all | slot | bulk delete | `require_principal` | delete_all_slots filters by recruiter_id | ✅ |
| POST /slots/bulk (assign/remind/delete) | slot | bulk write | `require_principal` | bulk_* guard recruiter_id | ✅ |
| POST /slots/{id}/outcome | slot | write | `require_principal` | ensure_slot_scope inside set_slot_outcome | ✅ |
| POST /slots/{id}/reschedule, /reject_booking | slot | write | `require_principal` | ensure_slot_scope in service | ✅ |
| GET /cities, /cities/{id} | city | read | `require_principal` | scope_cities via recruiter_cities M2M | ✅ |
| Dashboard /, /dashboard, /dashboard/funnel, /dashboard/funnel/step | dashboard | read | `require_principal` | recruiter principal → recruiter_id forced; counts/KPI/calendar scoped | ✅ |
| API /api/slots, /api/kpis/current, /api/dashboard/calendar | api | read | `require_principal` | recruiter principal → recruiter_id forced; calendar filtered by recruiter_id | ✅ |
| Admin-only routers (recruiters, templates, questions, workflow, system) | admin ops | varied | app wiring `require_admin` | ✅ |

Proof/Grep: all @router.post/put/delete in candidates.py & slots.py depend on `require_principal` or `require_admin`; ownership checks centralized via `ensure_candidate_scope` / `ensure_slot_scope` and scope_* in `backend/core/scoping.py`.
