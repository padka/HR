---
name: security-gate
description: Review RecruitSmart backend, auth, webhook, secret, and data-access changes for validation, trust-boundary, injection, CSRF/XSS/SSRF, logging, rate-limiting, and retry-safety risks.
---

# Security Gate

Use this skill before:

- auth or permission changes
- request handling or session handling
- webhooks or callback endpoints
- secrets, tokens, or environment handling
- file upload/download or path handling
- external integrations and retries
- any data-access change touching PII or business-critical state

Do not use for:

- harmless UI polish
- docs-only work
- copy changes without runtime impact

## Checklist

- Input validation is explicit.
- Auth and authz boundaries are correct.
- Client-side state is not trusted as identity.
- CSRF/XSS/SSRF/path traversal risks are addressed where relevant.
- Secrets and tokens are not logged or exposed.
- Sensitive data is minimized in logs and traces.
- Retry behavior cannot duplicate side effects.
- Rate limiting and abuse paths are considered.
- Least privilege is preserved.
- Error handling does not leak internal details.

## Output

Return:

- concrete findings with severity
- required fixes or safe rationale
- any required follow-up tests
- explicit "no issue found" only if the checklist is clean
