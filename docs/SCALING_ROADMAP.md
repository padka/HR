# Scaling Roadmap

This roadmap is ordered by production risk. Each phase should have an owner,
issue tracker entry, validation plan, and rollback notes before implementation.

## Phase 0 - Production Stabilization

Scope:

- create a real staging target;
- automate staging and production smoke;
- complete HH secret rotation;
- sanitize or restrict historical sensitive logs under an approved retention
  decision;
- add slot availability monitor;
- keep migration history fully documented.

Acceptance:

- staging smoke is repeatable;
- production smoke is attached to each release;
- no candidate dead-end when slots are unavailable;
- no new raw sensitive values in logs.

## Phase 1 - Observability And SLO

Scope:

- Prometheus/Grafana or equivalent;
- Sentry or equivalent error tracking;
- structured logs with request id;
- alerts for candidate 5xx, slots, HH stale, Telegram stale, disk, memory, and
  certificate expiry;
- weekly production readiness report.

Acceptance:

- on-call can see candidate readiness in one dashboard;
- alert thresholds are documented;
- false-positive rate is tracked and tuned.

## Phase 2 - Messaging Reliability

Scope:

- Telegram webhook with secret-token validation;
- MAX notification retry queue;
- idempotent message delivery;
- dead-letter queue;
- provider outage mode.

Acceptance:

- duplicate provider delivery does not duplicate candidate actions;
- provider outage does not block unrelated flows;
- rollback to polling remains documented until webhook is stable.

## Phase 3 - Scheduling Scale

Scope:

- automatic slot inventory;
- recruiter calendar sync;
- campaign capacity rules;
- waitlist;
- overbooking protection;
- manual availability SLA;
- auto-assignment engine.

Acceptance:

- active campaigns maintain future inventory above threshold;
- slot booking remains race-safe under burst traffic;
- manual requests have visible SLA state.

## Phase 4 - Worker And Job Architecture

Scope:

- dedicated queue workers;
- retry/backoff/jitter policy;
- job retention;
- dead job dashboard;
- circuit breakers for external APIs.

Acceptance:

- HH and notification jobs do not run in hot loops;
- dead/retry queues are visible;
- retention can run in dry-run and approved execution modes.

## Phase 5 - Infrastructure Scale

Scope:

- CDN for candidate assets;
- blue-green or canary deploys;
- managed PostgreSQL/Redis or hardened backup and replication;
- infrastructure as code for nginx, systemd, and env templates;
- restore tests;
- resource alerts;
- horizontal candidate frontend scaling.

Acceptance:

- static asset latency decreases;
- restore procedure is tested;
- deploy rollback is operator-safe and timed.

## Phase 6 - Recruiting Intelligence

Scope:

- funnel analytics;
- campaign conversion reporting;
- source/provider analytics;
- AI candidate advisory with guardrails;
- recruiter copilot;
- n8n automations;
- drop-off anomaly detection;
- quality scoring with human review.

Acceptance:

- AI output cannot directly mutate candidate status without explicit action;
- analytics are explainable to recruiters;
- human review remains in scoring workflows.

## Phase 7 - Enterprise Readiness

Scope:

- RBAC;
- audit log;
- data retention policy;
- GDPR/PII export/delete process;
- admin action history;
- secrets vault;
- environment promotion policy.

Acceptance:

- sensitive admin actions are auditable;
- data export/delete process is documented and tested;
- production secrets are no longer stored in ad hoc env files.
