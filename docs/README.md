# RecruitSmart Canonical Docs Index

## Purpose
Единый индекс канонической технической документации RecruitSmart Admin. Этот файл определяет active source of truth по архитектуре, данным, фронтенду, безопасности, QA и runbooks.

## Owner
Platform Engineering

## Status
Canonical

## Last Reviewed
2026-03-25

## Source Paths
- `docs/architecture/*`
- `docs/data/*`
- `docs/frontend/*`
- `docs/security/*`
- `docs/qa/*`
- `docs/runbooks/*`
- `docs/adr/*`
- `backend/migrations/`
- `frontend/app/src/app/main.tsx`
- `backend/apps/admin_ui/app.py`

## Related Diagrams
- `docs/architecture/overview.md`
- `docs/architecture/runtime-topology.md`
- `docs/architecture/core-workflows.md`
- `docs/data/erd.md`
- `docs/qa/critical-flow-catalog.md`

## Change Policy
Любое изменение архитектурной границы, runtime-топологии, data model, auth/token semantics, route tree, release gate или incident procedure обновляет соответствующий canonical раздел в том же change set. Исторические документы не редактируются как рабочий source of truth.

## Canonical Sections
| Section | Purpose | Canonical source |
| --- | --- | --- |
| Architecture | System context, runtime topology, workflows | `docs/architecture/*` |
| Data | ERD, data dictionary, migration policy, lifecycle enums | `docs/data/*` + `backend/migrations/` |
| Frontend | Route tree, screen inventory, state flows, design system, ownership | `docs/frontend/*` + `frontend/app/src/app/main.tsx` |
| Security | Trust boundaries, auth/token model, security regression areas | `docs/security/*` |
| QA | Test plan, RTM, environments, release gate, critical flows | `docs/qa/*` |
| Runbooks | Operational failure handling | `docs/runbooks/*` |
| ADR | Stable architectural and process decisions | `docs/adr/*` |

## Source-Of-Truth Rules
- HTTP contracts: backend OpenAPI and live routers in `backend/apps/*`.
- Data model and schema evolution: `backend/migrations/` plus `docs/data/*`.
- Workflow and interaction diagrams: `docs/architecture/*` in Markdown + Mermaid.
- SPA route tree: `frontend/app/src/app/main.tsx`; current canonical route inventory covers 37 frontend routes and must not be confused with backend FastAPI route count.
- Auth, session, portal and MAX token semantics: `docs/security/*`.
- Release readiness and regression policy: `docs/qa/*`.

## Historical Boundary
- `docs/archive/*` is historical/reference-only and does not override canonical docs.
- Legacy root docs such as `docs/MIGRATIONS.md`, `docs/TECHNICAL_OVERVIEW.md`, `docs/route-inventory.md` and similar are reference material unless they are explicitly linked from canonical pages as supporting context.
- If a legacy document conflicts with live code or canonical docs, follow live code first, then canonical docs.

## Reading Order
1. `docs/architecture/overview.md`
2. `docs/architecture/runtime-topology.md`
3. `docs/architecture/core-workflows.md`
4. `docs/data/erd.md`
5. `docs/data/data-dictionary.md`
6. `docs/frontend/README.md`
7. `docs/security/trust-boundaries.md`
8. `docs/security/auth-and-token-model.md`
9. `docs/qa/master-test-plan.md`
10. `docs/qa/release-gate-v2.md`
11. `docs/adr/README.md`
