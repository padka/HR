# vNext Baseline Metrics

**Date:** 2026-02-25
**Branch:** codex/test-builder-v1

## 1. Code Size

### Backend (Python) — Top files by line count
| File | Lines |
|------|-------|
| `backend/apps/bot/services.py` | **7,423** |
| `backend/apps/admin_ui/routers/api.py` | **3,753** |
| `backend/apps/admin_ui/services/candidates.py` | **3,517** |
| `backend/apps/admin_ui/services/dashboard.py` | **2,164** |
| `backend/apps/admin_ui/services/slots.py` | **1,918** |
| `backend/domain/repositories.py` | **1,521** |
| `backend/apps/admin_ui/routers/candidates.py` | **1,357** |
| `backend/domain/models.py` | **1,241** |
| `backend/core/ai/service.py` | **1,207** |
| `backend/apps/bot/reminders.py` | **1,194** |

**Target:** backend <= 2000 lines per file
**Files exceeding target:** 4 (bot/services.py, routers/api.py, services/candidates.py, services/dashboard.py)

### Frontend (TS/TSX) — Top files by line count
| File | Lines |
|------|-------|
| `src/api/schema.ts` (generated) | **4,827** |
| `routes/app/candidate-detail.tsx` | **2,234** |
| `routes/app/dashboard.tsx` | **1,268** |
| `routes/app/test-builder-graph.tsx` | **1,147** |
| `routes/app/slots.tsx` | **1,052** |
| `routes/app/city-edit.tsx` | **1,004** |
| `routes/app/messenger.tsx` | **945** |
| `routes/app/calendar.tsx` | **923** |
| `routes/app/system.tsx` | **914** |
| `routes/__root.tsx` | **908** |

**Target:** frontend route <= 1200 lines
**Files exceeding target (excl. generated):** 2 (candidate-detail.tsx, dashboard.tsx)

## 2. Lint / Code Quality

### Ruff (current config: E, F, I, B, UP)
- **Violations:** 1 (E902 io-error — path issue, not real code)
- **Effective:** 0 real violations with current ruleset

### Ruff (ALL rules — true tech debt)
- **Total violations:** 12,136
- **Auto-fixable:** 5,243
- **Top categories:**
  - E501 (line-too-long): 2,014
  - COM812 (missing-trailing-comma): 1,376
  - UP045 (non-pep604-annotation): 1,356
  - UP006 (non-pep585-annotation): 881
  - D103 (undocumented-public-function): 656
  - C901 (complex-structure): 123
  - PLR0913 (too-many-arguments): 78
  - PLR0912 (too-many-branches): 76

## 3. Supply Chain Security

### pip-audit
- **Vulnerabilities:** 20 in 10 packages
- **Critical/High packages:**
  - starlette 0.37.2 (CVE-2024-47874, CVE-2025-54121) → fix: 0.47.2
  - jinja2 3.1.4 (3 CVEs) → fix: 3.1.6
  - python-multipart 0.0.9 (2 CVEs) → fix: 0.0.22
  - cryptography 46.0.3 (CVE-2026-26007) → fix: 46.0.5
  - authlib 1.6.5 (CVE-2025-68158) → fix: 1.6.6
  - python-jose 3.3.0 (4 PYSECs) → fix: 3.4.0
  - pypdf 6.7.0 (3 CVEs) → fix: 6.7.1
  - filelock 3.20.0 (2 CVEs) → fix: 3.20.3
  - virtualenv 20.35.4 (CVE-2026-22702) → fix: 20.36.1
- **Broken install:** `~qlalchemy` invalid dist in .venv

### npm audit
- **Vulnerabilities:** 2 (1 moderate, 1 high)
- **Package:** minimatch (9 paths affected)
- **Fix:** `npm audit fix`

### Dependency source conflict
- **pyproject.toml** — core deps (fastapi, starlette, SQLAlchemy, etc.)
- **requirements.txt** + **requirements-dev.txt** — separate files at project root
- **Conflict risk:** versions may drift between pyproject.toml and requirements*.txt

## 4. Frontend Architecture

### API Client
- **Centralized:** `src/api/client.ts` with `apiFetch<T>()` wrapper
- **Features:** CSRF management, retry on 403, credentials included
- **Double prefix /api/api/:** **0 occurrences** (not present)
- **Raw fetch calls outside client:** 2 (login, streaming download)

### data-testid
- **Current count:** **0** (zero attributes in entire frontend)
- **Target:** all interactive elements for e2e stability

### E2E Tests (Playwright)
- **Total selectors:** 34 across 9 test files
- **Stable (getByRole/getByText):** 17 (50%)
- **Fragile (class/href/text-regex):** 17 (50%)
- **Fragile patterns:**
  - Class-based CSS selectors: 8
  - Attribute selectors (href, title): 5
  - Text-based regex filters: 4

## 5. KPI Summary vs Targets

| KPI | Baseline | Target | Gap |
|-----|----------|--------|-----|
| pip-audit high/critical | 20 vulns | 0 | -20 |
| npm audit high/critical | 1 high | 0 | -1 |
| Backend max file size | 7,423 lines | 2,000 | -5,423 |
| Frontend max route size | 2,234 lines | 1,200 | -1,034 |
| Flaky tests | TBD | 0 | TBD |
| data-testid coverage | 0 | full | 0% |
| Fragile e2e selectors | 17 (50%) | 0 | -17 |
| CI gate pass (2x green) | TBD | yes | TBD |
| p95 latency | TBD | <=600ms | TBD |
