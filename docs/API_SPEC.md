# API Specification

OpenAPI schemas are generated from live FastAPI app factories. Manual edits to generated schemas are not authoritative.

## OpenAPI Process

Use:

```bash
make openapi-export
make openapi-check
```

Generated artifacts:
- `frontend/app/openapi.json`
- `backend/apps/admin_api/openapi.json`
- `frontend/app/src/api/schema.ts`

Any route, schema, response, or API tooling change must pass `make openapi-check`.

## Public Campaign API

Purpose:
- expose active campaign metadata;
- advertise available verification providers;
- avoid leaking inactive/private campaign details.

Expected behavior:
- active campaign `main` returns enabled providers such as Telegram, MAX, and HH when configured;
- invalid campaign or invalid public token returns a safe error;
- no stack traces or PII in public responses.

## Verification Start API

Purpose:
- start provider-specific verification for Telegram, MAX, and HH;
- return a provider start URL, launch payload, or authorize URL.

Provider expectations:
- Telegram returns a valid start response for the bot runtime.
- MAX returns a valid bounded launch response for the pilot surface.
- HH returns an authorize/start response when OAuth configuration is available.

Error policy:
- provider misconfiguration returns a safe controlled error;
- raw provider tokens or callback state are never returned;
- public responses use stable error codes such as `poll_not_found` where applicable.

## Candidate Slot API

Purpose:
- list available slots;
- reserve/book slots transactionally;
- prevent double booking and race conditions;
- return a controlled response when a slot was just taken.

Required behavior:
- slot availability is campaign-aware where campaign context exists;
- retries should be idempotent where an idempotency key is supported;
- booking errors must not leak SQL or internal details.

## Manual Availability API

Purpose:
- collect candidate preferred time windows when no future slots exist;
- keep candidate flow from dead-ending;
- expose requests to admin/backoffice for manual scheduling.

Required behavior:
- store campaign/provider/candidate reference safely;
- do not persist raw public tokens when a reference/hash is available;
- support statuses such as new, in progress, resolved, or cancelled where implemented;
- reject ambiguous text as a precise appointment if date context is missing.

## Admin APIs

Admin APIs cover:
- candidate pipeline and detail;
- scheduling and slot operations;
- manual assignment/replacement actions;
- messaging and notification retries;
- HH integration status;
- AI advisory surfaces;
- operational health and metrics.

Security requirements:
- authenticated principal required;
- CSRF required for state-changing browser/API calls;
- recruiter scoping enforced server-side;
- safe error format without PII/tracebacks.

## HH Integration Endpoints

HH endpoints and workers must classify:
- 401 as refresh or reauth-needed path;
- 403 as forbidden/needs-attention path without hot-loop retry;
- 429 as rate-limited path respecting provider retry hints when available;
- network/5xx as retryable with backoff.

## Safe Error Format

Public and candidate-facing errors should be stable, minimal, and non-sensitive:

```json
{"error": "poll_not_found"}
```

Admin errors can include user-safe messages but must not include secrets, raw tokens, SQL tracebacks, or stack traces.
