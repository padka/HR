[CodexAudit]
Rule: Run audit orchestration natively in Codex chat via `.codex/audit/*`, not external orchestrator code.
Rationale: keep control local and HITL-first.
Pattern:
- read `system_prompt.md`
- read `queue.txt` and `architect_decisions.md`

[ApprovalGate]
Rule: Do not edit repo files, decision memory, or queue state until the user explicitly approves the proposed audit action in chat.
Rationale: prevent unreviewed mutations.
Pattern:
- audit -> propose -> ask approval

[AuditMemory]
Rule: Store only global reusable audit rules in compact ADR form and deduplicate or compact before every ledger write.
Rationale: prevent context bloat and policy drift.
Pattern:
- `[TAG]`
- `Rule:` / `Rationale:` / `Pattern:`

[RedisIndex]
Rule: Redis-backed auxiliary indexes must lazily self-repair stale members on miss or expiry before metrics or existence checks are trusted.
Rationale: TTL expiry can leave orphaned index entries and inflate false evictions.
Pattern:
- `WATCH key`
- `if not EXISTS key: SREM index member`

[SQLAlchemyTx]
Rule: Business writes must run inside explicit transaction scopes and must not rely on session close for correctness.
Rationale: implicit close rolls back and hides missed commits.
Pattern:
- `async with session.begin(): ...`
- `await uow.commit()`

[UnitOfWorkLifecycle]
Rule: Async `UnitOfWork` instances are single-use unless repositories are fully rebound on every enter.
Rationale: closed-session repo handles become stale on reuse.
Pattern:
- one `async with uow`
- new instance per transaction scope

[WebhookIdempotency]
Rule: Webhook dedup must use insert-first unique-key reservation, not read-before-write existence checks.
Rationale: concurrent retries race past pre-checks.
Pattern:
- `INSERT idempotency key`
- unique conflict => duplicate success

[OutboundDelivery]
Rule: Persist outbound MAX send intent before provider delivery and finalize it after provider acknowledgement.
Rationale: crash windows after send can duplicate side effects.
Pattern:
- reserve outbound row
- send provider message
- mark `sent` or `failed`

[CacheBootstrap]
Rule: Global cache clients must fail closed during bootstrap and must not be published before connectivity is proven.
Rationale: half-connected singletons hide startup failure and shift errors to runtime.
Pattern:
- create local pool/client
- `PING`
- publish globals only after success
