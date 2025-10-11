# Production Readiness Checklist

## Reliability
- [ ] Admin UI starts with `BOT_ENABLED=0` and no optional deps (currently crashes on missing `aiohttp`).【F:audit/RISKS.md†L4-L7】【82a108†L1-L18】
- [ ] Database bootstrap optional for smoke tests; today `ensure_database_ready` always runs migrations/seeds.【F:audit/RISKS.md†L20-L23】
- [ ] Health probes split into `/healthz` (liveness) and `/readyz` (readiness); currently combined and returns 503 when state manager absent.【F:audit/API_MAP.md†L32-L35】

## Security
- [ ] Mandatory session secret with enforced SessionMiddleware; avoid 500s when secret missing.【F:audit/SECURITY_GAPS.md†L1-L3】
- [ ] Secure headers (HSTS, CSP, COOP/COEP, Referrer-Policy) configured globally.【F:audit/SECURITY_GAPS.md†L2-L2】
- [ ] Cookies flagged `Secure`, `HttpOnly`, `SameSite`; CSRF protection documented for form posts.【F:audit/SECURITY_GAPS.md†L3-L3】
- [ ] pip-audit/npm audit integrated into CI with 0 high severity findings.【F:audit/DEPS.md†L21-L31】

## Observability
- [ ] Request-id middleware + structured logging for FastAPI, forwarded to bot integrations.【F:audit/RISKS.md†L28-L31】
- [ ] Baseline metrics exporter (Prometheus/OpenTelemetry) with latency, error rate, and scheduler queue depth.【F:audit/RISKS.md†L28-L31】
- [ ] Health endpoints expose DB latency, bot mode, and static asset checksum for cache busting.【F:audit/API_MAP.md†L28-L35】

## Performance
- [ ] `/api/slots` paginated with total/count metadata; limit ≤100 with configurable default.【F:audit/RISKS.md†L12-L15】
- [ ] CSS bundle ≤90 KB raw / ≤70 KB gzip after removing duplicates.【F:audit/PERF_BASELINE.md†L4-L12】
- [ ] `/api/*` p95 ≤200 ms measured post-optimisation (load test script + metrics).【F:audit/PERF_BASELINE.md†L16-L24】
- [ ] Dashboard TTI ≤2.0 s (desktop) validated via Playwright/Lighthouse CI run.【F:audit/PERF_BASELINE.md†L16-L24】

## UX & Accessibility
- [ ] Unified base template + tokenised design system (Liquid Glass) with light/dark parity.【F:audit/REPO_MAP.md†L12-L20】
- [ ] Playwright visual diffs within 2 px across desktop/tablet/mobile for key screens.【F:audit/PERF_BASELINE.md†L16-L24】
- [ ] WCAG AA contrast and focus-visible styles documented and enforced via linting/test suite.【F:audit/REPO_MAP.md†L12-L20】

## QA & Testing
- [ ] pytest suite covers admin services, pagination, bot fallbacks (≥85 % coverage target).【F:audit/DEPS.md†L21-L31】
- [ ] Playwright matrix (3 viewports × light/dark) executed in CI; artifacts published per PR.【F:audit/PERF_BASELINE.md†L16-L24】
- [ ] Contract tests for KPI endpoints (`get_weekly_kpis`, `list_weekly_history`) to avoid regressions.【F:audit/API_MAP.md†L17-L24】

## Documentation & DX
- [ ] `docs/LOCAL_DEV.md` kept current with Python 3.12+/Node 20 setup; extras split (`core`, `dev`, `bot`).【F:audit/DEPS.md†L1-L19】
- [ ] `docs/RUNBOOK.md` describes toggles, migrations, disaster recovery, alerting playbooks.【F:docs/RUNBOOK.md†L1-L200】
- [ ] `docs/ROADMAP.md` & `docs/TECH_STRATEGY.md` align with epics/PR plan, updated per milestone.【F:docs/ROADMAP.md†L1-L200】【F:docs/TECH_STRATEGY.md†L1-L200】
