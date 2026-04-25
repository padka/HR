# Integrations

RecruitSmart Maxpilot currently integrates with Telegram, bounded MAX pilot
surfaces, and HH. All provider flows must be idempotent and safe under retries.

## Telegram

Current runtime:

- Telegram bot service handles candidate messaging.
- Polling is the hardened fallback mode.
- Webhook is the preferred future state, but only with secret-token validation
  and nginx hardening.

Polling rules:

- use bounded exponential backoff with jitter on network timeouts;
- do not drop pending updates during normal operation;
- aggregate noisy timeout logs;
- keep update handling idempotent.

Future webhook requirements:

- HTTPS only;
- secret path and header validation;
- POST only;
- small body limit;
- fast 2xx after enqueue or short synchronous handling;
- rollback through Telegram webhook deletion and polling restore.

## MAX

Current state is bounded pilot only:

- `/api/max/launch`
- `/api/max/webhook`
- `/miniapp`
- shared `/api/candidate-access/*`
- operator rollout controls

MAX must reuse shared candidate journey contracts. Do not fork Test1, screening,
booking, or launch semantics into MAX-only business logic.

Hardening rules:

- silent active-assignment replacement is rejected by default;
- explicit MAX-only replacement is allowed only for the intended controlled
  path;
- candidate/advisory surfaces must not expose internal exception strings.

## HH

HH integration covers authorization/start responses, employer/vacancy sync, and
background job status.

Failure handling policy:

- 401: refresh once, then mark as needing reauth if still unauthorized.
- 403: controlled forbidden/permission state; do not hot-loop.
- 429: respect provider retry guidance when available.
- 5xx/network: retry with exponential backoff and jitter.

Logs must include masked diagnostics only:

- endpoint class;
- status code;
- correlation id when available;
- reason category;
- no credential values.

## Secret Rotation

HH Client Secret rotation process:

1. Revoke or replace the secret in the provider cabinet.
2. Store the new value through the approved secure channel.
3. Restart affected service during rollout.
4. Verify HH auth/API behavior.
5. Confirm logs do not contain old or new secret values.

Telegram and MAX credentials follow the same no-log/no-doc/no-shell-output rule.

## Expected Response Posture

Provider start APIs should return valid launch/authorize payloads or safe
errors. Public candidate responses must not include stack traces, raw provider
payload internals, or secret-bearing fields.
