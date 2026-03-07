# Performance Test Plan

## 1. Current State
- The repository already includes load-testing guidance and tooling in `docs/performance/loadtesting.md` and `scripts/loadtest_profiles/*`.
- Historical gate evidence in `docs/performance/results_20260301_go_gate.md` shows the system can pass a `600 rps` mixed profile, but p95 flaps under noisier runtime profiles.
- Current CI does not execute any load or performance smoke automatically.
- Prometheus metrics and DB/cache diagnostics already exist, which is a strong base for measurable perf gates.

## 2. Goals
- Detect API latency regressions before release.
- Identify queue/backlog bottlenecks in notifications and reminders.
- Validate that concurrency controls prevent double booking without destroying throughput.
- Measure dashboard/list endpoints under realistic read-heavy and mixed workloads.
- Measure candidate communication throughput and failure recovery under external dependency degradation.

## 3. Environments and Data Sets

### Environment tiers
- PR: no load test, only cheap perf smoke if route hot paths change.
- Nightly: dedicated ephemeral Postgres + Redis environment with bot integration disabled and representative seed data.
- Pre-release: prod-like runtime profile with `WEB_CONCURRENCY>=2`, Redis enabled, Postgres tuned, representative data volume.

### Minimum seeded dataset
- 50 recruiters.
- 200 cities with realistic recruiter-city mappings.
- 50k candidates with mixed statuses.
- 20k slots across 14 days.
- 5k active outbox rows, including retryable and terminal states.
- 1k chat messages and 500 staff chat threads.

## 4. Required Telemetry
- HTTP latency p50/p95/p99 by route.
- Error rate by route and status class.
- DB pool acquire p95/p99.
- Slow query sample report.
- Redis broker publish/consume latency.
- Outbox queue depth.
- Notification retry count and DLQ count.
- Websocket/calendar broadcast backlog if applicable.
- Frontend bundle size deltas for route-heavy screens.

## 5. Performance Scenarios

| Scenario | Business case | Workload model | Targets | Data volume | KPI / threshold | Suspected bottlenecks | Tools |
|---|---|---|---|---|---|---|---|
| Baseline API smoke | Quick regression check before release | 5 min mixed read-heavy at stable rate | `/api/profile`, `/api/dashboard/summary`, `/api/dashboard/incoming`, `/api/candidates`, `/api/slots` | full seed | error rate <0.5%, route p95 <250ms, p99 <1000ms | cache misses, DB pool contention | existing `scripts/loadtest_profiles`, Prometheus |
| Read-heavy load | Morning recruiter dashboard/list usage | 70% reads, 30% filter changes | dashboard, candidates, calendar, notifications feed | 50k candidates / 20k slots | no knee below target 800 RPS, DB pool acquire p95 <50ms | heavy candidate queries, dashboard joins | profile runner + metrics snapshot |
| Mixed workflow load | Normal business day | read/write mix with slot actions | candidates list/detail, slot propose/book/approve, notifications feed | same | error rate <1%, write p95 <500ms | locking around slot updates, outbox write amplification | profile runner + sampled SQL |
| Booking concurrency | Multiple candidates/bookings hitting same recruiter capacity | bursty parallel booking/reschedule requests | `/api/webapp/booking`, `/api/webapp/reschedule`, `/api/slots/{id}/book` | 500 active candidates, overlapping slots | zero double-bookings, conflicts mapped to 409, no 5xx | row locks, inconsistent SQL vs domain paths | async load harness + DB invariant queries |
| Queue throughput | Notification backlog after incident or campaign | 5k-20k queued outbox items, multiple consumers | notification worker, outbox claim/send/retry | 5k queued rows | queue drains within defined SLA, no duplicate send, retry distribution sane | broker throughput, retry storms, stale locks | custom harness + Prometheus |
| Spike | Sudden hiring campaign or after push notification | 30s steady, 30s spike 1.5x-2x | same critical API routes | full seed | no sustained 5xx, recovery to baseline within 60s | DB pool saturation, cache stampede | existing spike scripts |
| Soak | Memory leak / stale lock / scheduler drift detection | 2-4h moderate mixed load | API + worker + reminders | full seed | latency stable, no queue growth, no unbounded memory/log rate | memory leak, stale locks, periodic jobs | long-running perf rig + system metrics |
| Reporting stress | KPI/history/report queries during ops reviews | bursty analytics and filter use | `/api/kpis/current`, `/api/kpis/history`, recruiter leaderboard, funnel | 12 months history | p95 <750ms, no timeout, no DB starvation of writes | aggregates and wide scans | profile runner + EXPLAIN sampling |
| Search/filter stress | Recruiters using candidates and slots heavily | many different query combinations | `/api/candidates`, `/api/slots`, `/api/dashboard/incoming` | varied filters | stable p95 across top 20 filter combinations | unindexed filters, ORM-generated SQL complexity | scenario matrix harness |
| Frontend render stress | Mobile and desktop users on heavy screens | route open + filter + scroll + tab changes | candidates, candidate detail, messenger, calendar | representative JSON payloads | no long tasks >200ms during critical interactions; no OOM on mobile | large payload rendering, FullCalendar, graph builder | Playwright trace + browser performance panel |

## 6. Endpoint and Job Priorities

### P0 targets
- `/api/candidates`
- `/api/candidates/{candidate_id}`
- `/api/slots`
- `/api/slots/{slot_id}/approve_booking`
- `/api/slots/{slot_id}/reject_booking`
- `/api/candidates/{candidate_id}/schedule-slot`
- `/api/candidates/{candidate_id}/schedule-intro-day`
- `/api/webapp/booking`
- `/api/webapp/reschedule`
- notification worker poll/claim/send loop

### P1 targets
- `/api/dashboard/summary`
- `/api/dashboard/incoming`
- `/api/calendar/events`
- `/api/notifications/feed`
- `/api/kpis/current`
- recruiter chat send/retry endpoints

## 7. DB-Focused Checks
- Run `EXPLAIN ANALYZE` for `candidates`, `dashboard/incoming`, `calendar/events`, and notification feed queries under seeded volume.
- Track N+1 via SQLAlchemy echo/profile sampling for candidate detail and dashboard calculations.
- Validate indexes used by slot status, candidate owner, recruiter-city M2M, outbox status/next retry, and notification log uniqueness.
- Confirm `FOR UPDATE` and `SKIP LOCKED` paths maintain throughput without deadlocks under concurrency.

## 8. Queue and Worker Tests
- Measure queue drain rate for `NotificationService` with Redis broker and DB fallback.
- Simulate transient Telegram/Max errors and verify retry slope does not create retry storm.
- Simulate worker restart with stale `locked_at` rows and verify re-claim behavior.
- Measure reminder scheduling throughput after bulk slot generation and after mass reject/reschedule.

## 9. Frontend Performance Checks
- Enforce bundle budget via existing `frontend/app/scripts/check-bundle-budgets.mjs`.
- Record route-level initial load and interaction timings for:
  - Dashboard
  - Candidates
  - Candidate detail
  - Slots
  - Messenger
- Add Playwright traces for mobile viewport on critical screens.
- Fail nightly if horizontal overflow, long paint stalls, or severe bundle regressions appear.

## 10. Release Thresholds

### Minimum release thresholds
- Mixed profile: error rate <1%, max p95 <250ms, max p99 <1000ms.
- Booking concurrency: zero double-bookings, zero 5xx for expected conflicts.
- Queue throughput: backlog recovery within agreed SLA after seeded failure storm.
- Dashboard and candidates list: no route p95 >500ms under read-heavy profile.
- No DB pool exhaustion under canonical release profile.

### No-go signals
- Any deterministic path to duplicate booking or duplicate intro-day reservation under concurrent load.
- Worker backlog growth without automatic recovery.
- Persistent p95 regression >25% against previous accepted baseline.
- Route errors caused by expected business conflicts rather than proper 4xx handling.

## 11. Execution Cadence
- On PR when hot paths change: lightweight query-plan review and optional focused perf smoke.
- Nightly: mixed profile + booking concurrency + queue throughput smoke.
- Pre-release: full mixed + spike + selected soak + queue recovery run.
- After deploy: 5-minute canary perf smoke and health/metrics confirmation.

## 12. Immediate Next Steps
1. Wire existing `scripts/loadtest_profiles` into a nightly GitHub Actions workflow.
2. Create seeded Postgres+Redis perf environment.
3. Add booking concurrency invariant check harness.
4. Publish baseline dashboards for p95/p99, DB pool, outbox depth, retry counts.
