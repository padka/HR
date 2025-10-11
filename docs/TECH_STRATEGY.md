# Technical Strategy

## Vision
Deliver a modular, production-ready admin platform for HR operations with:
- Stable runtime independent of optional bot services.
- Unified Liquid Glass UI system with light/dark parity and WCAG AA compliance.
- Guarded supply chain (audits, pre-commit) and observable infrastructure (request-id, metrics, health splits).

## Guiding Principles
1. **Separation of concerns** – Admin UI must boot without Telegram bot/Redis; bot features behind explicit flags/null services.【F:audit/RISKS.md†L4-L7】
2. **Design system first** – Single Tailwind pipeline, shared tokens, and component library reused across screens.【F:audit/REPO_MAP.md†L12-L20】
3. **Performance budgets** – `/api/*` p95 ≤200 ms, Dashboard TTI ≤2 s, CSS ≤90 KB raw / ≤70 KB gzip.【F:audit/PERF_BASELINE.md†L4-L24】
4. **Security by default** – Mandatory session secret, secure headers, audit pipelines; treat missing deps as fatal in prod.【F:audit/SECURITY_GAPS.md†L1-L7】
5. **Observability everywhere** – Structured logs, request-id propagation, health readiness separation, metrics for scheduler/bot state.【F:audit/RISKS.md†L28-L31】
6. **Documentation as code** – Keep roadmap/runbook/prod readiness docs updated per PR; CI enforces doc touchpoints.【F:docs/ROADMAP.md†L1-L200】

## Architecture Targets
- **Backend**: FastAPI with modular routers, SQLAlchemy 2.0 async, SQLite/Postgres support. Introduce service interfaces (`BotClient`, `ReminderScheduler`) with null implementations.
- **Frontend**: Tailwind JIT build, PostCSS autoprefixing, tokens in `tokens.css`, components in `templates/components/`. Build pipeline checks CSS size + theme diffs.
- **Data layer**: Add indices and pagination helpers, deduplicate `UTCDateTime`, ensure migrations additive and tracked.
- **DevEx**: `uv`-driven dependency management, extras for `core`, `dev`, `bot`, pre-commit enforcing style, `make doctor` verifying env.
- **CI/CD**: GitHub Actions matrix (3.12, 3.13), caching for poetry/uv, Playwright screenshot artifacts, bundle reports, commit linting.
- **Observability**: Implement middleware stack (request-id, timing), integrate OpenTelemetry or Prometheus client, optional Sentry instrumentation.

## Milestones (linked to `docs/ROADMAP.md`)
1. **DX Foundations** – Extras split, audits, doc refresh. Unblocks consistent onboarding.
2. **Runtime Isolation** – Feature flags, null services, safe session fallback. Enables admin-only deployment.
3. **UI Core** – Liquid Glass tokens, duplicate asset removal, theme parity.
4. **Perf/Security** – Pagination, budgets, secure headers, metrics.
5. **QA/CI** – Playwright matrix, coverage, artifact pipelines, commit linting.

## Technical Bets
- Adopt `uv` for reproducible Python installs (fast resolver, lock export).
- Use `deptry` to detect unused/missing deps; integrate `pip-audit` & `npm audit` for supply-chain checks.
- Consider `fastapi-limiter` or Starlette middleware for rate limiting once security epic begins.
- Evaluate OpenTelemetry vs. custom logging; choose minimal vendor lock-in.

## Out of Scope (for now)
- Feature development altering business logic or API contracts (requires explicit flag & plan).
- Non-additive migrations or destructive schema changes.
- Embedding production secrets in repo; rely on external secret management.

## Success Metrics
- All readiness checklist items checked in `docs/PROD_READINESS.md`.
- CI pipeline consistently green with ≤20 min duration.
- 0 internal 500s on empty DB + `BOT_ENABLED=0` smoke tests.
- Playwright diffs ≤2 px and CSS budgets maintained for each release.
