---
name: scalability-review
description: Review RecruitSmart endpoints, jobs, scheduling, analytics, and candidate pipeline flows for complexity, query count, concurrency, idempotency, burst behavior, and failure isolation.
---

# Scalability Review

Use this skill for:

- endpoints or handlers with meaningful traffic
- list/search/filter pages
- scheduling, slot assignment, or reminder jobs
- analytics or KPI calculations
- message fan-out, queueing, or webhook paths
- candidate pipeline flows with repeated reads or writes

Do not use for:

- copy-only work
- docs-only work
- trivial UI text changes

## Checklist

- Query count is bounded.
- N+1 risks are removed or justified.
- Hot-path work is cached or deferred where safe.
- DB session scope is short and explicit.
- Concurrency and burst behavior are understood.
- Idempotency is preserved.
- Retry behavior will not amplify load.
- Failure isolation is clear.
- Observability exists for the path.
- Any background warm-up or prefetch is bounded.

## Output

Return:

- bottlenecks
- scaling risks
- minimal safe optimizations
- metrics or tests to watch
- explicit trade-offs
