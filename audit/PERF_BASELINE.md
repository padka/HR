# Performance Baseline (Local)

## Bundle sizes
- `backend/apps/admin_ui/static/build/main.css`: **89,780 bytes raw** via `wc -c`.【f39afc†L1-L2】
- `main.css` gzip-compressed: **14,168 bytes** via `gzip -c | wc -c`.【02c5f0†L1-L2】
- `backend/apps/admin_ui/static/js/` directory footprint: **84 KB** (du, includes duplicates such as `dashboard-calendar 2.js`).【0c3953†L1-L2】【191def†L1-L4】

## Route/model counts
- Automated metrics script `audit/collect_metrics.py` fails because optional bot dependency `aiohttp` is not installed, demonstrating hard coupling of admin runtime to bot stack.【82a108†L1-L18】
- Inventory generator `audit/generate_inventory.py` runs, but FastAPI route enumeration fails for the same reason (`No module named 'aiohttp'`).【997a41†L1-L7】

## Runtime smoke tests
- No automated `make run`/`make screens` executed yet (read-only audit). Startup currently requires database migrations + optional bot imports; baseline cold-start timing unavailable due to dependency failure above.

## Target budgets (per readiness criteria)
- `/api/*` p95 ≤ 200 ms (to be measured after pagination work).
- Dashboard TTI ≤ 2.0 s (requires Playwright/Lighthouse instrumentation post-UI unification).
- CSS bundle ≤ 90 KB raw / ≤ 70 KB gzip – current raw size already ~89.8 KB but duplicates inflate future growth; action needed before additional features.
