# Migration Map: Jinja → React/TSX (Admin UI)

> Last updated: 2026-01-24 (Cleanup + API align)

Status legend:
- **DONE**: React page covers the legacy feature set for that area. Ready for legacy removal.
- **PARTIAL**: React page exists but does not cover full legacy workflow.
- **TODO**: No React page or only stub.
- **DECIDE**: Needs explicit decision (keep server-rendered vs migrate).

---

## Current Progress Summary

| Metric | Value |
|--------|-------|
| React/TSX coverage | ~98% |
| SPA routes implemented | 22 |
| Legacy templates | 2 (public test pages only) |
| Backup/preview files pending cleanup | 1 (.env.backup) |

**Areas requiring legacy Jinja:**
- Public pages: test2_public (keep server-rendered)

---

## Migration Matrix

| Area | Legacy Template(s) | SPA Route | Status | Specific Gaps |
|------|-------------------|-----------|--------|---------------|
| **Dashboard** | `index.html` | `/app/dashboard` | DONE | ✅ Funnel chart<br>✅ Calendar view<br>✅ Weekly KPIs<br>✅ Date/recruiter filters<br>✅ Summary cards |
| **Candidates list** | `candidates_list.html` | `/app/candidates` | DONE | ✅ Search + status filters<br>✅ Status badges with colors<br>✅ Recruiter column<br>✅ Board/Kanban view<br>✅ Calendar view |
| **Candidate detail** | `candidates_detail.html` | `/app/candidates/:id` | DONE | ✅ Profile info + stats<br>✅ Actions panel<br>✅ Slots table with purpose<br>✅ Test sections<br>✅ Chat with send<br>✅ Status badge with styling<br>✅ Schedule slot modal<br>✅ Schedule intro day modal<br>✅ Full workflow status center |
| **Candidate detailization** | `candidates_detailization.html` | `/app/candidates` | DONE | ✅ Merged into candidates list with status filters (hired/not_hired) |
| **Candidate create** | `candidates_new.html` | `/app/candidates/new` | DONE | ✅ Full form with city/recruiter/datetime<br>✅ Preview panel<br>✅ Quick date buttons<br>✅ Timezone display |
| **Schedule manual slot** | `schedule_manual_slot.html` | `/app/candidates/:id` (modal) | DONE | ✅ Modal in candidate detail<br>✅ City/recruiter selects<br>✅ Custom message option |
| **Schedule intro day** | `schedule_intro_day.html` | `/app/candidates/:id` (modal) | DONE | ✅ Modal in candidate detail<br>✅ Date/time picker |
| **Slots list** | `slots_list.html` | `/app/slots` | DONE | ✅ Table/Cards/Agenda views<br>✅ Status/recruiter/limit filters<br>✅ Pagination<br>✅ Sheet modal with all actions<br>✅ Approve/Reject for PENDING<br>✅ Reschedule for BOOKED<br>✅ Booking modal (assign candidate)<br>✅ Bulk select + delete/remind<br>✅ Status badges with colors<br>✅ Link to create slots |
| **Slots create** | `slots_new.html` | `/app/slots/create` | DONE | ✅ Single create form<br>✅ Bulk create UX<br>✅ Validation parity |
| **Recruiters list** | `recruiters_list.html` | `/app/recruiters` | DONE | ✅ Cards with stats/load/next slot<br>✅ Inline activation toggle<br>✅ Delete action |
| **Recruiters create** | `recruiters_new.html` | `/app/recruiters/new` | DONE | ✅ Full form with sections<br>✅ Validation<br>✅ City tiles with search<br>✅ Selection counter<br>✅ TZ hint |
| **Recruiters edit** | `recruiters_edit.html` | `/app/recruiters/:id/edit` | DONE | ✅ Summary hero card<br>✅ Full form with cities<br>✅ City tiles + pills preview<br>✅ Delete<br>✅ Validation |
| **Cities list** | `cities_list.html` | `/app/cities` | DONE | ✅ Card layout with TZ/plan/experts/stages<br>✅ Inline plan/active update<br>✅ Delete action |
| **Cities create** | `cities_new.html` | `/app/cities/new` | DONE | ✅ Full form with sections<br>✅ TZ auto-suggest + validation<br>✅ Plan presets (5/10/20, 30/60/100)<br>✅ Recruiter tiles with search |
| **Cities edit** | `cities_edit.html` | `/app/cities/:id/edit` | DONE | ✅ Summary hero card<br>✅ Full form<br>✅ TZ validation + current time<br>✅ Plan presets<br>✅ Recruiter tiles + pills preview<br>✅ Delete |
| **Templates list** | `templates_unified.html` | `/app/templates` | DONE | ✅ Stage templates editor<br>✅ Custom templates filters<br>✅ Notifications summary<br>✅ Message templates grouped by stage with toggles/delete |
| **Templates create** | `templates_new.html` | `/app/templates/new` | DONE | ✅ Create form<br>✅ Editor parity |
| **Templates edit** | `templates_edit.html` | `/app/templates/:id/edit` | DONE | ✅ Edit form<br>✅ Editor parity |
| **Message templates** | `message_templates_form.html`, `message_templates_list.html` | `/app/message-templates` | DONE | ✅ List/Create/Edit<br>✅ History UI |
| **Questions list** | `questions_list.html` | `/app/questions` | DONE | ✅ List<br>✅ Create/clone |
| **Questions edit** | `questions_edit.html` | `/app/questions/:id/edit` | DONE | ✅ JSON builder + templates<br>✅ Preview + validation guard |
| **Profile** | `profile.html` | `/app/profile` | DONE | ✅ Admin/recruiter view<br>✅ Legacy profile features parity |
| **Login/Logout** | `auth.py` (HTML) | `/app/login` | DONE | ✅ Native SPA login<br>✅ Legacy fallback |
| **Public test pages** | `test2_public.html`, `test2_public_result.html` | — | DONE | Keep server-rendered (public access) |
| **System/health** | — | `/app/system` | DONE | ✅ Health snapshot<br>✅ Bot integration status |
| **Regions/timezones** | — | — | DONE | ✅ Timezone options via `/api/timezones` wired in forms |

---

## Files Pending Cleanup (Phase D)

### Backup Files (safe to delete)
- [ ] `.env.backup` (root level)

### Preview HTML Files (already removed)
- [x] All preview files have been removed

### Legacy JS/CSS Artifacts (removed)
- [x] `backend/apps/admin_ui/static/js/` полностью удалён (SPA покрывает фронтенд, legacy шаблоны удалены)
- [x] `backend/apps/admin_ui/static/build/main.css` удалён как устаревший build Tailwind

### Legacy Templates (removed)
- [x] Удалены legacy Jinja шаблоны (кроме public test pages)
- [x] Оставлены `test2_public.html`, `test2_public_result.html` как публичные страницы

---

## Execution Plan (Phase B)

### Priority 1: Complete Candidate Flows ✅ DONE
1. [x] Add candidate create form (`/app/candidates/new`)
2. [x] Merge detailization into detail view (status filters on list)
3. [x] Add schedule manual slot modal to detail
4. [x] Add schedule intro day modal to detail
5. [x] Full workflow status center parity

### Priority 2: Complete Slots Flows ✅ DONE
1. [x] Approve/Reject slot actions
2. [x] Reschedule flow
3. [x] Booking flow (assign candidate to slot)
4. [x] Bulk actions (select multiple, bulk delete/remind)
5. [x] Bulk create UX polish (success feedback, preview)

### Priority 3: Complete Dashboard
1. [x] Funnel chart (pipeline visualization)
2. [x] Calendar view (slots by date)
3. [x] Weekly KPIs
4. [x] Date/recruiter filters

### Priority 4: Admin CRUD Parity ✅ DONE
1. [x] Recruiters: validation, inline deactivation
2. [x] Cities: validation, inline actions
3. [x] Templates: unified editor parity
4. [x] Questions: create/clone
5. [x] Message templates: history UI

### Priority 5: Auth & System ✅ DONE
1. [x] Native SPA login form
2. [x] System/health dashboard (optional)

### Priority 6: Cleanup (Phase D)
1. [ ] Delete backup/current files
2. [x] Delete preview HTML files
3. [x] Remove legacy templates after parity confirmed
4. [x] Remove legacy JS/CSS modules
5. [x] Update documentation

---

## Decision Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-01-24 | Public test pages (DECIDE) | Keep server-rendered: public access, no auth, SEO not needed but simpler |
| 2026-01-24 | Detailization → merge into detail | Reduces navigation, single source of truth for candidate info |
| 2026-01-24 | Scheduling → modals in detail | Better UX than separate pages |
| 2026-01-24 | Dashboard SPA uses `/api/dashboard/funnel` + recruiter-filtered KPI/calendar | Enables date/recruiter filtering while keeping summary endpoint backward compatible |

---

## Notes

- **SPA mount point**: `/app/*` (static mount in `app.py:441`)
- **SPA build output**: `frontend/dist/`
- **Dev proxy**: Vite proxies `/api`, `/slots`, `/auth` to FastAPI
- **Role guard**: `RoleGuard` component checks principal type (admin/recruiter)
- **API types**: Generated from OpenAPI schema (`src/api/schema.ts`)
