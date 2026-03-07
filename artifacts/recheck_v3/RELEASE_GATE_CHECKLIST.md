# RELEASE GATE CHECKLIST (recheck v3)

Дата: 2026-03-01

| Gate | Статус | Evidence |
|---|---|---|
| Source-of-truth документы и v2 baseline прочитаны | PASS | `artifacts/recheck_v3/logs/PRODUCTION_READINESS_REPORT_v2.snapshot.md`, `artifacts/recheck_v3/logs/RELEASE_CHECKLIST.snapshot.md`, `artifacts/recheck_v3/logs/loadtesting.snapshot.md` |
| `WEB_CONCURRENCY>=2` зафиксирован в topology | PASS | `artifacts/recheck_v3/logs/recon_service_inventory.txt`, `artifacts/recheck_v3/logs/worker_topology_v3.txt` |
| Boot production-like topology через docker compose | SKIPPED (high risk) | `artifacts/recheck_v3/logs/compose_up_v3.log` (Docker daemon недоступен) |
| Health/readiness endpoints (`admin_ui` + `admin_api`) | PASS | `artifacts/recheck_v3/logs/health_check_v3.txt` |
| Formal gate Sprint1/2 | PASS (`manual_pending`) | `artifacts/recheck_v3/test_results/formal_gate_v3.log`, `artifacts/recheck_v3/test_results/formal_gate_latest_v3.json` |
| Backend domain/RBAC/concurrency/migrations suites | PASS | `artifacts/recheck_v3/test_results/backend_suite_v3.log` |
| Frontend lint/typecheck/unit | PASS | `artifacts/recheck_v3/test_results/frontend_lint_v3.log`, `artifacts/recheck_v3/test_results/frontend_typecheck_v3.log`, `artifacts/recheck_v3/test_results/frontend_unit_subset_v3.log` |
| Frontend e2e smoke | PASS | `artifacts/recheck_v3/test_results/frontend_e2e_smoke_v3.log` |
| Critical flow smoke (create/schedule/reschedule/search/kanban move) | PASS | `artifacts/recheck_v3/smoke/critical_flow_smoke_v3.json` |
| Perf gate mixed 600 rps (multi-worker) | PASS | `artifacts/recheck_v3/perf/perf_gate_v3_workers2_pass.log`, `artifacts/recheck_v3/perf/perf_gate_summary_v3_workers2_pass.json`, `artifacts/recheck_v3/perf/perf_gate_v3_workers2_pass.rc` |
| Доп. perf profile read-heavy (short) | PASS | `artifacts/recheck_v3/perf/read_heavy_short_v3.log`, `artifacts/recheck_v3/perf/read_heavy_short_v3_step.json` |
| Analyze-step merge (autocannon + metrics) | PASS | `artifacts/recheck_v3/perf/analyze_step_v3_workers2_manual.json` |
| Security baseline (secrets + pip + npm + dry-run install) | PASS | `artifacts/recheck_v3/security/secret_scan_v3.log`, `artifacts/recheck_v3/security/pip_audit_v3.txt`, `artifacts/recheck_v3/security/npm_audit_v3.json`, `artifacts/recheck_v3/security/pip_install_dry_run_v3.txt` |
| Auth/Authz quick smoke | PASS | `artifacts/recheck_v3/logs/auth_authz_smoke_v3.txt`, `artifacts/recheck_v3/logs/auth_csrf_validation_v3.txt` |
| Live Telegram/OpenAI integration rehearsal | SKIPPED (medium risk) | `artifacts/recheck_v3/ops_health_v3.json` (bot/AI отключены в recheck env) |
| UI evidence screenshots | PASS | `artifacts/recheck_v3/smoke/ui_candidates_list_v3.png`, `artifacts/recheck_v3/smoke/ui_candidates_kanban_v3.png` |

## OVERALL
- **PASS (Conditional GO)**
- Условия перед production window: закрыть пункты из `PRE_RELEASE_WINDOW_CHECKLIST.md`.
- Неблокирующий `manual_pending` из formal gate вынесен в pre-release window с владельцами и шагами проверки.
