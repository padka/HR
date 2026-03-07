# PRODUCTION READINESS REPORT v2 — Recruitsmart Admin

## 1) Executive Summary
- **Вердикт:** **GO** (canary rollout).
- **Основание:** закрыт последний P1-блокер по perf gate (`mixed 600 rps`), остальные критичные functional/security/migration gate уже были зелёные.
- **Ключевое условие GO:** runtime topology с `WEB_CONCURRENCY>=2` для `admin_ui`/`admin_api`.

## 2) Итог по целям recheck

| Цель | Статус | Evidence |
|---|---|---|
| Закрыть critical issue `POST /api/candidates` | ✅ Closed | `artifacts/recheck_v2/logs/api_smoke_candidate_create_contract_postfix_18111.txt`, `artifacts/recheck_v2/test_results/test_admin_candidate_schedule_slot_postfix.log` |
| Подтвердить UI split create/schedule | ✅ Closed | `frontend/app/src/app/routes/app/candidate-new.tsx`, `artifacts/recheck_v2/test_results/candidate_new_ui_postfix.log` |
| Пройти formal/security gates | ✅ Pass | `artifacts/recheck_v2/test_results/formal_gate_v2_postfix.log`, `artifacts/recheck_v2/security/pip_audit_v2_postfix.txt`, `artifacts/recheck_v2/security/npm_audit_v2_postfix.json` |
| Пройти perf gate 600 rps | ✅ Pass | `artifacts/recheck_v2/perf/perf_gate_v2_workers2_pass.log`, `artifacts/recheck_v2/perf/perf_gate_summary_v2_workers2_pass.json` |

## 3) Top Risks (P0/P1) и статус

| Приоритет | Риск | Статус | Evidence | Mitigation |
|---|---|---|---|---|
| P1 | Нарушение perf-envelope при single-worker запуске | **Mitigated** | `artifacts/recheck_v2/perf/analyze_step_single_worker_reference_gate_thresholds.json` | Зафиксирован `WEB_CONCURRENCY>=2` в compose/env/runbook |
| P1 | Некорректная оценка latency при multi-worker только по `/metrics` | **Mitigated** | `scripts/loadtest_profiles/analyze_step.py`, `artifacts/recheck_v2/perf/analyze_step_workers2_reference.json` | В анализ добавлен client-side latency merge из autocannon |
| P0 | Data-loss/auth-bypass/system-down | **Not found** | Security + auth smoke артефакты ниже | Canary + rollback triggers остаются обязательными |

## 4) Coverage Map (tested / untested)

### 4.1 Протестировано

| Область | Результат | Evidence |
|---|---|---|
| Backend create/schedule contract | Pass | `artifacts/recheck_v2/test_results/test_admin_candidate_schedule_slot_postfix.log` |
| Frontend candidate-new flow | Pass | `artifacts/recheck_v2/test_results/candidate_new_ui_postfix.log` |
| API smoke create-flow (live) | Pass | `artifacts/recheck_v2/logs/api_smoke_candidate_create_contract_postfix_18111.txt` |
| API smoke schedule-slot без tg | Pass (`400 candidate_telegram_missing`) | `artifacts/recheck_v2/logs/api_smoke_schedule_slot_missing_tg_postfix_18111.txt` |
| Formal gate | Pass (`manual_pending`) | `artifacts/recheck_v2/test_results/formal_gate_latest_v2_postfix.json` |
| Security audits | Pass | `artifacts/recheck_v2/security/pip_audit_v2_postfix.txt`, `artifacts/recheck_v2/security/npm_audit_v2_postfix.json`, `artifacts/recheck_v2/security/secret_scan_v2_postfix.log` |
| Perf gate @600 rps (closure) | Pass | `artifacts/recheck_v2/perf/perf_gate_v2_workers2_pass.log` |

### 4.2 Untested / partially tested

| Область | Почему | Риск | Следующий шаг |
|---|---|---|---|
| Fresh clean-room compose rehearsal в closure-цикле | Не перепрогонялся после perf closure | Medium | Выполнить перед боевым окном и приложить `docker compose logs` |
| Full DB-level backup/restore (`pg_dump/pg_restore`) в closure-цикле | В этом цикле не повторялся | Medium | Повторить drill перед production freeze |
| Cross-browser smoke (Firefox/WebKit) | В цикле использован Chromium | Low | Добавить nightly matrix |

## 5) Bugs (severity + repro + evidence)

### BUG-R2-001 (Closed)
- Severity: P1
- Component: Candidate intake (`POST /api/candidates`, `/app/candidates/new`)
- Repro (исторически): create с датой/временем без tg возвращал 400/409 и ломал flow.
- Expected: create-only `201`, scheduling отдельным шагом.
- Actual (после фикса): create стабильно `201`, schedule отдельно.
- Evidence:
  - `artifacts/recheck_v2/logs/api_smoke_candidate_create_contract_postfix_18111.txt`
  - `artifacts/recheck_v2/test_results/test_admin_candidate_schedule_slot_postfix.log`
  - `artifacts/recheck_v2/test_results/candidate_new_ui_postfix.log`
- Suspected root cause (до фикса): смешанный create+scheduling контракт.

### BUG-R2-003 (Closed)
- Severity: P1
- Component: Performance gate (`scripts/perf_gate.sh`)
- Repro:
  1. Запуск gate на single-worker стенде.
  2. Получался `latency_p95>0.25`.
- Expected: `error_rate <1%`, `p95<=0.25s`, `p99<1.0s`.
- Actual (после closure): PASS на release topology.
- Evidence:
  - Fail reference: `artifacts/recheck_v2/perf/perf_gate_v2_postfix_18111_tuned_with_serverlog.log`
  - Pass reference: `artifacts/recheck_v2/perf/perf_gate_v2_workers2_pass.log`
  - Analyzer references: `artifacts/recheck_v2/perf/analyze_step_single_worker_reference_gate_thresholds.json`, `artifacts/recheck_v2/perf/analyze_step_workers2_reference.json`
- Suspected root cause: single-worker saturation + неполная visibility latency при multi-worker анализе только по `/metrics`.

## 6) Security Checklist

| Проверка | Статус | Evidence |
|---|---|---|
| Auth smoke / authz sanity | Pass | `artifacts/recheck_v2/logs/authz_smoke.txt` |
| Python dependency audit | Pass | `artifacts/recheck_v2/security/pip_audit_v2_postfix.txt` |
| Node dependency audit (`high/critical`) | Pass | `artifacts/recheck_v2/security/npm_audit_v2_postfix.json` |
| Secrets scan | Pass | `artifacts/recheck_v2/security/secret_scan_v2_postfix.log` |

## 7) Performance Results

| Профиль | Topology | Target | Achieved | Error rate | p95 | p99 | Статус |
|---|---|---:|---:|---:|---:|---:|---|
| mixed gate (historical fail) | single worker | 600 rps | ~601 rps | 0.0% | 0.5s | 0.5s | ❌ Fail |
| mixed gate (closure pass) | workers=2 | 600 rps | 600 rps | 0.0% | 0.25s | 0.5s | ✅ Pass |

Evidence:
- Fail: `artifacts/recheck_v2/perf/perf_gate_v2_postfix_18111_tuned_with_serverlog.log`
- Pass: `artifacts/recheck_v2/perf/perf_gate_v2_workers2_pass.log`
- Summary: `artifacts/recheck_v2/perf/perf_gate_summary_v2_workers2_pass.json`

## 8) Reliability / Integrations

| Проверка | Статус | Evidence |
|---|---|---|
| Telegram sandbox | Pass | `artifacts/recheck_v2/ops/telegram_sandbox_v2.json` |
| OpenAI live json-mode | Pass | `artifacts/recheck_v2/ops/openai_live_json_mode_v2.json` |
| OpenAI app endpoint | Pass | `artifacts/recheck_v2/ops/openai_admin_endpoint_v2.json` |
| Migration contract | Pass | `artifacts/recheck_v2/ops/migrations_prod_without_migration_url.log`, `artifacts/recheck_v2/ops/migrations_prod_with_migration_url_hardened.log` |

## 9) Release Checklist Status
- Детальный чеклист: `artifacts/recheck_v2/RELEASE_GATE_CHECKLIST.md`
- Текущее состояние: **OVERALL PASS**.
- Контракт rollout: canary `10% -> 50% -> 100%`, rollback trigger по error-rate/latency/outbox depth.

## 10) Go/No-Go Decision
- **GO**.
- Обязательные guardrails:
  1. `WEB_CONCURRENCY>=2` на runtime.
  2. Redis-backed rate limiting в production (не memory fallback).
  3. Мониторинг p95/p99/5xx и готовый rollback по runbook.
