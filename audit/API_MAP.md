# API and Route Map

## Admin UI (HTML/Jinja)
| Path | Methods | Source | Notes |
| --- | --- | --- | --- |
| `/` | GET | `dashboard.index` | Dashboard landing; aggregates counts, KPIs, calendar, bot status; errors logged but swallowed when upstream services fail.【F:backend/apps/admin_ui/routers/dashboard.py†L68-L114】 |
| `/slots` | GET | `slots.slots_list` | Table view with recruiter/status/city filters; server-side pagination present (page/per_page) but API counterpart lacks envelopes.【F:backend/apps/admin_ui/routers/slots.py†L93-L148】 |
| `/slots/new` | GET | `slots.slots_new` | Slot creation form with recruiter/city options.【F:backend/apps/admin_ui/routers/slots.py†L150-L181】 |
| `/slots/{id}/edit` | GET | `slots.slots_edit` | Slot edit UI; drives modal actions and bot dispatch helpers.【F:backend/apps/admin_ui/routers/slots.py†L183-L266】 |
| `/candidates` | GET | `candidates.candidates_list` | Candidate directory with filters (search, city, active, rating, tests/messages flags).【F:backend/apps/admin_ui/routers/candidates.py†L23-L60】 |
| `/candidates/{id}` | GET | `candidates.candidates_detail` | Candidate detail/inline edit view; redirects to list when not found.【F:backend/apps/admin_ui/routers/candidates.py†L73-L104】 |
| `/recruiters` | GET | `recruiters.recruiters_list` | Recruiter listing with modal for create/edit; uses shared recruiter services.【F:backend/apps/admin_ui/routers/recruiters.py†L13-L38】 |
| `/cities` | GET | `cities.cities_list` | City catalogue; toggles active status, renders template forms.【F:backend/apps/admin_ui/routers/cities.py†L19-L85】 |
| `/regions` | GET | `regions.regions_list` | Regional summary page grouping cities by zone.【F:backend/apps/admin_ui/routers/regions.py†L13-L52】 |
| `/templates` | GET | `templates.templates_list` | Template management UI for city-specific message bodies.【F:backend/apps/admin_ui/routers/templates.py†L19-L63】 |
| `/questions` | GET | `questions.questions_list` | Lists screening questions/test scenarios.【F:backend/apps/admin_ui/routers/questions.py†L15-L46】 |

## Admin UI JSON endpoints (`/api` prefix)
| Path | Methods | Source | Notes |
| --- | --- | --- | --- |
| `/api/health` | GET | `api.api_health` | Returns dashboard counts; doubles as lightweight health signal.【F:backend/apps/admin_ui/routers/api.py†L21-L27】 |
| `/api/dashboard/calendar` | GET | `api.api_dashboard_calendar` | Calendar snapshot (days param 1–60); 400 on invalid date; no caching.【F:backend/apps/admin_ui/routers/api.py†L30-L45】 |
| `/api/recruiters` | GET | `api.api_recruiters` | Recruiter metadata for filters/autocomplete.【F:backend/apps/admin_ui/routers/api.py†L47-L50】 |
| `/api/cities` | GET | `api.api_cities` | City metadata; reused by form components.【F:backend/apps/admin_ui/routers/api.py†L52-L55】 |
| `/api/slots` | GET | `api.api_slots` | Slot feed; accepts recruiter/status filter, but returns raw list with `limit` default 100 and cap 500 (no pagination metadata).【F:backend/apps/admin_ui/routers/api.py†L57-L66】 |
| `/api/templates` | GET | `api.api_templates` | Template retrieval by city/key; returns 404 when not found.【F:backend/apps/admin_ui/routers/api.py†L69-L75】 |
| `/api/kpis/current` | GET | `api.api_weekly_kpis` | KPI snapshot; defers to bot service metrics.【F:backend/apps/admin_ui/routers/api.py†L78-L80】 |
| `/api/kpis/history` | GET | `api.api_weekly_history` | KPI history list with limit/offset (max 104 weeks).【F:backend/apps/admin_ui/routers/api.py†L83-L88】 |
| `/api/template_keys` | GET | `api.api_template_keys` | Static list of template keys for UI dropdowns.【F:backend/apps/admin_ui/routers/api.py†L91-L105】 |
| `/api/city_owners` | GET | `api.api_city_owners` | Aggregates recruiter ownership per city; 400 on errors.【F:backend/apps/admin_ui/routers/api.py†L108-L112】 |
| `/api/bot/integration` | GET/POST | `api.api_bot_integration_status` / `api.api_bot_integration_update` | Toggle runtime integration switch; tightly coupled to in-process bot state.【F:backend/apps/admin_ui/routers/api.py†L115-L166】 |

## System & health endpoints
| Path | Methods | Source | Notes |
| --- | --- | --- | --- |
| `/health` | GET | `system.health_check` | Aggregates DB, state manager, bot service; returns 503 when state manager missing; no ready vs live separation.【F:backend/apps/admin_ui/routers/system.py†L23-L65】 |
| `/health/bot` | GET | `system.bot_health` | Detailed bot runtime probe hitting Telegram when runtime available; couples admin UI to bot/aiogram imports.【F:backend/apps/admin_ui/routers/system.py†L67-L145】 |
| `/.well-known/appspecific/com.chrome.devtools.json` | GET | `system.devtools_probe` | Empty 204 for Chrome DevTools detection.【F:backend/apps/admin_ui/routers/system.py†L17-L31】 |
| `/favicon.ico` | GET | `system.favicon_redirect` | Redirects to static asset; duplicates with static mount.【F:backend/apps/admin_ui/routers/system.py†L13-L22】 |

## Admin API (`backend.apps.admin_api`)
| Path | Methods | Source | Notes |
| --- | --- | --- | --- |
| `/` | GET | `main.create_app.root` | JSON stub exposing `/admin` dashboard; app mounts SQLAdmin views for CRUD (requires optional `sqladmin`).【F:backend/apps/admin_api/main.py†L16-L25】 |
| `/admin/*` | HTML | `admin.mount_admin` | SQLAdmin interface covering Recruiters, Cities, Templates, Slots via ModelView definitions.【F:backend/apps/admin_api/admin.py†L1-L53】 |
