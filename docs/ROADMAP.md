# Implementation Roadmap

## Epics Overview
Each epic contains goals, concrete steps, Definition of Done (DoD), success metrics, risks, and rollback guidance.

### 1. DX & Dependencies Alignment
- **Goals**: Standardise Python 3.12+/Node 20, split extras (`core`, `dev`, `bot`), remove duplicate `requirements-dev.txt`, add guardrails (pre-commit, pip-audit, npm audit, deptry).
- **Key steps**:
  1. Update `pyproject.toml` with extras + Python 3.12, regenerate lockfiles via `uv` or `pip-tools`.
  2. Refresh `dev_doctor`/Makefile to validate interpreter/toolchain, expose `make doctor`, `make audit` targets.
  3. Configure pre-commit (ruff/black/isort/mypy), add deptry + pip-audit/npm audit to CI.
- **DoD**: `make setup && make ui && make lint` green on Python 3.12; `pip-audit`/`npm audit` report 0 high severity.
- **Metrics**: Install time ≤5 min; dependency audit logs stored in CI artifacts.
- **Risks**: Lockfile churn; ensure compatibility matrix (3.12, 3.13) in CI.
- **Rollback**: Re-enable old requirements by pinning to release tag if compatibility issues appear.

### 2. Runtime Stability & Bot Isolation
- **Goals**: Admin UI runs without bot extras, scheduler only starts after migrations succeed, SessionMiddleware fallback safe.
- **Key steps**:
  1. Add `BOT_ENABLED`/`BOT_RUNTIME_ENABLED` feature flag gating imports; provide null bot service.
  2. Defer reminder scheduler until `ensure_database_ready` confirms schema; add timeout + error logging.
  3. Wrap `require_admin` to operate in Basic-only mode when sessions unavailable; surface actionable error messages.
- **DoD**: `BOT_ENABLED=0 make run` works with no Redis/Aiogram installed; `/healthz` returns 200 on empty DB.
- **Metrics**: 0 startup 500s on empty database; cold start ≤3 s with migrations cached.
- **Risks**: Bot functionality regression; add smoke tests with bot enabled to detect drift.
- **Rollback**: Toggle feature flag to re-enable legacy eager imports temporarily.

### 3. UI Unification & Theming
- **Goals**: Single Tailwind pipeline (`main.css`), tokens in `tokens.css`, light/dark parity, remove duplicated assets.
- **Key steps**:
  1. Delete suffixed `* 2.css`/`* 2.js` files; refactor templates to use shared components.
  2. Extract Liquid Glass primitives into partials (cards, KPI tiles, tables) and apply across screens.
  3. Add dark mode support via CSS variables/tokens; update Playwright screenshots.
- **DoD**: CSS ≤90 KB raw / ≤70 KB gzip; Playwright diff ≤2 px across viewports/themes.
- **Metrics**: Dashboard TTI ≤2.0 s; Tailwind build artifact tracked in CI.
- **Risks**: Visual regressions; mitigate with before/after screenshots and design review.
- **Rollback**: Restore previous `static/css` snapshots from git tag if severe regressions.

### 4. Security Hardening
- **Goals**: Enforce secure headers, require session secret, tighten cookies, add CSRF/rate-limit defaults.
- **Key steps**:
  1. Integrate `SecureHeadersMiddleware` (or custom) for HSTS, CSP (report-only first), COOP/COEP, Referrer-Policy.
  2. Fail-fast startup when session secret missing in non-dev; add CLI helper to generate secret.
  3. Add CSRF tokens or double-submit pattern for form posts; document admin auth flows.
- **DoD**: `curl -I` shows HSTS/CSP; automated tests confirm session secret requirement; pip/npm audit clean.
- **Metrics**: Security headers lint in CI; 0 high-severity audit findings.
- **Risks**: CSP blocking inline scripts; start in report-only, iterate allowlist.
- **Rollback**: Toggle CSP to report-only; disable middleware via env flag while debugging.

### 5. Observability & Health
- **Goals**: Structured logs with request-id, split health endpoints, expose basic metrics, instrument timeouts.
- **Key steps**:
  1. Add ASGI middleware for request-id + contextvar logging; propagate to bot service calls.
  2. Implement `/healthz` (process) and `/readyz` (DB/bot) with clear JSON payload.
  3. Integrate Prometheus or OTEL metrics (request latency, DB latency, reminder queue depths).
- **DoD**: Logs include `request_id`; `/healthz` & `/readyz` pass smoke tests; metrics endpoint scraped in CI.
- **Metrics**: Request logging overhead <5 ms; health check coverage in runbook.
- **Risks**: Logging noise; provide sampling + log level toggles.
- **Rollback**: Disable middleware via env flag, revert to standard logging format.

### 6. Performance & Pagination
- **Goals**: Standard pagination schema, capped limits, indexes for heavy queries, caching for dashboard counters.
- **Key steps**:
  1. Introduce `Page[T]` response model with `items`, `total`, `page`, `per_page`, `next_cursor`.
  2. Add DB indexes (slots.status, slots.start_utc, recruiters.name) and SQLAlchemy eager loading to avoid N+1.
  3. Enable gzip/etag/static cache headers for static assets; document budgets.
- **DoD**: `/api/slots` p95 ≤200 ms in local profiling; API responses include pagination metadata.
- **Metrics**: Query count per dashboard view ≤5; `EXPLAIN` plan tracked in docs.
- **Risks**: Legacy UI expects old payload; introduce compatibility shim or versioned endpoint.
- **Rollback**: Serve old payload via feature flag while UI migrates.

### 7. Tests & QA
- **Goals**: Strengthen pytest coverage, Playwright matrix, visual diff pipeline, contract tests for KPI & bot flows.
- **Key steps**:
  1. Expand unit/integration tests for slots pagination, bot toggle, candidate CRUD.
  2. Add Playwright scenarios for Dashboard/Slots/Candidates (desktop/tablet/mobile × light/dark).
  3. Upload visual artifacts in CI, enforce ≤2 px diff budget.
- **DoD**: `pytest` + `make screens` green; coverage ≥85 %; Playwright artifacts posted.
- **Metrics**: Flake rate <2 %; diff budget tracked by UI workflow.
- **Risks**: CI duration increase; shard tests or use GitHub Actions matrix.
- **Rollback**: Reduce viewport matrix temporarily if pipeline unstable.

### 8. CI/CD Modernisation
- **Goals**: End-to-end CI with lint/tests/ui/screens/audits, bundle reports, commit linting, PR template.
- **Key steps**:
  1. Update `.github/workflows/ci.yml` to run `make doctor`, `make lint`, `make test`, `make ui`, `make screens`, `pip-audit`, `npm audit`.
  2. Add bundle-size report comment + artifact upload (screenshots, coverage, audits).
  3. Enforce Conventional Commits via commitlint or Danger.
- **DoD**: CI pipeline completes ≤20 min; failures block merge on lint/test/audit/budget breaches.
- **Metrics**: Bundle size trend stored as workflow artifact; PR template referenced in review.
- **Risks**: Workflow complexity; modularise using reusable actions.
- **Rollback**: Revert to previous workflow from tag if blocking release.

### 9. Documentation & Runbooks
- **Goals**: Up-to-date LOCAL_DEV, RUNBOOK, TECH_STRATEGY, PROD_READINESS, ROADMAP, PR_TEMPLATE.
- **Key steps**:
  1. Document setup for Python 3.12/Node 20, extras, env vars, optional bot stack.
  2. Draft runbooks for deploy, rollback, bot toggles, migrations, alert response.
  3. Maintain roadmap & prod readiness checklists, linking to metrics and epics.
- **DoD**: Docs reviewed per PR; onboarding ≤1 day.
- **Metrics**: Feedback loop captured in repo issues.
- **Risks**: Documentation drift; enforce doc check in CI.
- **Rollback**: None – docs can be hotfixed quickly.

### 10. (Optional) Release Container
- **Goals**: Multi-stage Dockerfile producing slim runtime image without secrets.
- **Key steps**: Build base Python image with `uv`/`pip install`, compile Tailwind in Node stage, copy static assets to final stage, add healthcheck.
- **DoD**: `docker build` + `docker run` start admin UI with env vars; documented as optional path.
- **Risks**: Registry constraints; mark as optional deliverable.

## Initial PR Sequence
1. **feature/dx-foundation** – Extras split, Python 3.12 target, pre-commit, make targets, audits.
   - DoD: `make setup && make ui && make lint && pip-audit && npm audit` succeed without bot deps.
2. **feature/ui-core-unify** – Remove duplicate CSS/JS, centralise tokens, implement dark/light theme.
   - DoD: `npm run build:css`, `make screens`; CSS ≤90 KB raw / ≤70 KB gzip; diff ≤2 px.
3. **feature/runtime-stability** – Feature flags for bot, lazy imports, session fallback, scheduler gating.
   - DoD: `BOT_ENABLED=0 make run`, `/healthz`=200, smoke without 500.
4. **feature/slots-cleanup** – API pagination, KPI cards, sticky table, indices.
   - DoD: `pytest tests/services/test_admin_slots_api.py`, profiling shows `/api/slots` p95 ≤200 ms.
5. **feature/candidates-v1** – Candidate table enhancements, inline edits, idempotent actions.
   - DoD: `pytest tests/...`, Playwright scenarios for candidate flows.
6. **feature/sec-obs** – Security headers, request-id middleware, `/readyz`, structured logs.
   - DoD: integration tests verifying headers/logs; curl smoke.
7. **feature/qa-ci** – Expanded CI workflows, Playwright matrix, bundle report, PR template/commitlint.
   - DoD: All workflows green, artifacts attached, budgets enforced.

## Milestone Tracking
- **Milestone A (DX foundations)**: Epics 1 & 9 complete; PR 1 merged.
- **Milestone B (Stability & UI)**: Epics 2 & 3 delivered; PRs 2–3 merged.
- **Milestone C (Perf & Security)**: Epics 4–6 complete; PRs 4–6 merged with metrics captured.
- **Milestone D (QA & CI)**: Epic 7–8 done; PR 7 merged; readiness review executed using `docs/PROD_READINESS.md`.

## Rollback Strategy
- Tag each merged milestone; maintain changelog of config toggles (bot, CSP, feature flags).
- For runtime regressions, disable new middleware/feature via env toggles documented in runbook.
- Maintain migrations as additive only; provide SQL rollback scripts in runbook if emergency down-migration required.
