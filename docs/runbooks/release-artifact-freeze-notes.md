# Release Artifact Freeze Notes

Date: 2026-04-25

## Source

- Source branch: `production-hardening-candidate-scale`
- Safety branch: `release/hardening-artifact-freeze`
- HEAD: `473d9d3 fix(max): normalize callback ingress`
- `main...HEAD`: `0 0` before freeze, so the hardening batch existed only in the dirty worktree.

## Preservation Artifacts

- Worktree patch: `/tmp/recruitsmart-hardening-worktree.patch`
- Index patch: `/tmp/recruitsmart-hardening-index.patch`
- Untracked archive: `/tmp/recruitsmart-hardening-untracked.tgz`
- Status snapshot: `/tmp/recruitsmart-hardening-status.txt`
- Diff stat snapshot: `/tmp/recruitsmart-hardening-diff-stat.txt`
- Changed tracked files snapshot: `/tmp/recruitsmart-hardening-diff-name-only.txt`
- Untracked files snapshot: `/tmp/recruitsmart-hardening-untracked-files.txt`

## Snapshot Summary

- Dirty status lines: 116
- Tracked files changed: 107
- Untracked paths: 24
- Worktree patch size: 721760 bytes
- Index patch size: 0 bytes
- Untracked archive size: 2374703 bytes

## Changed File Areas

- Admin API: candidate access, MAX launch/webhook/chat, app middleware wiring, OpenAPI artifact.
- Admin UI: middleware, AI routes, candidate/slot APIs, HH integration summary, bot state, dashboard, chat and scheduling services.
- Bot runtime: polling/app startup, handlers, reminders, notification flow, onboarding, slot/manual availability flow.
- Core: environment loading, settings, logging redaction, MAX adapter, AI service/prompts/schemas/fake provider.
- Domain: candidate lifecycle/status/actions, HH integration client/contracts/jobs, scheduling repair, repositories, models, slot assignment service.
- Frontend: generated API schema/services, candidate detail, dashboard, incoming, slots, miniapp, CSS, tests.
- Tests: HH, logging redaction, production config, MAX surfaces, candidate access, slots/manual availability, AI, bot integration, outbox/reminders.
- Docs/runbooks: production hardening rollout plan and this freeze note.

## Known Failing Or Non-Green Gates At Freeze

- Full backend suite latest full run: `1193 passed`, `5 skipped`, `1 failed`.
- Failing full-suite case: `tests/test_ai_copilot.py::test_ai_candidate_coach_drafts_modes_and_invalid` returned `403` instead of `400` only in full-suite order.
- Same AI test isolated: passed.
- `tests/test_ai_copilot.py` file isolated: passed.
- `ruff check` on touched whole files: red due broad pre-existing legacy lint debt; introduced-code delta still needs explicit baseline classification.
- Migration chain mismatch: local migrations end at `0103_persistent_application_idempotency_keys`; production audit reports `0105_unique_users_max_user_id`.

## Safety Constraints

- No staging or production access was used.
- No DB migration was run.
- No destructive operation was performed.
- No secrets were printed or copied into this document.
