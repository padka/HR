# Observability

RecruitSmart Maxpilot needs lightweight but explicit observability for candidate
traffic, scheduling, HH sync, Telegram delivery, and infrastructure pressure.

## Correlation

Every externally visible request should have:

- `request_id` in response headers;
- request/correlation id in application logs;
- provider correlation fields when available and safe to log;
- no raw sensitive query or credential values.

## Health Checks

Live checks:

- process starts;
- HTTP service responds.

Ready checks:

- database connectivity;
- Redis connectivity where used by the service;
- critical schema compatibility.

External providers must not fail readiness by default. They should appear in
diagnostics and alerts.

## Required Metrics

Candidate:

- candidate flow 2xx/4xx/5xx by route group;
- public campaign lookup failures;
- invalid token safe-error count;
- manual availability request count;
- future available slots count by campaign.

Scheduling:

- reservation attempts;
- double-booking prevention count;
- idempotent booking replay count;
- manual request status counts.

HH:

- job counts by status;
- oldest queued/running job age;
- last successful sync timestamp;
- 401/403/429 counts by integration;
- retention dry-run/deletion counts.

Telegram:

- last successful poll/update timestamp;
- timeout count;
- bounded backoff state;
- duplicate update count;
- notification retry count.

Infrastructure:

- app 5xx rate;
- DB connectivity and latency;
- Redis connectivity and latency;
- disk usage;
- memory and swap pressure;
- certificate expiry;
- nginx config validation status.

## Alert Thresholds

Minimum required alerts:

- `future_slots_count` below configured threshold for active campaign `main`;
- candidate flow 5xx above baseline;
- HH sync stale beyond threshold;
- persistent HH forbidden state;
- Telegram last update too old;
- disk usage above 80 percent;
- memory pressure sustained;
- certificate expiry under 14 days;
- nginx config validation failure.

## Dashboards

Operator dashboard should show:

- campaign readiness;
- future slots and manual availability queue;
- HH sync summary;
- Telegram status;
- candidate route health;
- recent safe errors;
- infrastructure pressure.

Do not include secrets or unnecessary PII in metrics labels.
