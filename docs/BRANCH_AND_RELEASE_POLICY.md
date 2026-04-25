# Branch And Release Policy

This policy applies to RecruitSmart Maxpilot release branches and production
hardening work.

## Dirty Worktree

Dirty worktree release artifacts are forbidden.

Before CI handoff:

```bash
git status --short
git log --oneline main..HEAD
git diff main..HEAD --stat
```

If local uncommitted work exists, preserve it with patch/archive artifacts before
any branch switch, reset, or cleanup.

## Branch Naming

Release branch:

```text
release/<scope>
```

Feature branch:

```text
production-hardening-candidate-scale
```

Codex scratch branch:

```text
codex/<scope>
```

## RC Tags

RC tag format:

```text
rc/hardening-candidate-scale-YYYYMMDD-N
```

Create a new RC tag when:

- committed application code changes after the previous RC;
- required docs/specs/runbooks become part of the release artifact;
- CI must prove a new clean Git ref.

Do not create a new RC tag only to rename a report or hide a failing gate.

## Final Tags

Final production tag format:

```text
vYYYY.MM.DD-hardening-candidate-scale
```

Create the final tag only after production smoke is green and main contains the
release.

## Generated Artifacts

OpenAPI generated artifacts are committed intentionally when API contracts
change. Generated artifacts must be updated through the repo tooling, not manual
edits.

## Ruff Baseline Waiver

Full Ruff remains baseline-red for legacy debt. Release reports may claim:

- critical `F,E9` gate is green on touched files;
- full Ruff baseline waiver is documented.

Release reports must not claim full Ruff is green until the baseline is removed.

## Merge To Main

Merge to main requires:

- CI green on the selected RC;
- staging smoke green;
- migration path validated or formally waived;
- docs/runbooks updated;
- no open P0/P1 release blockers.

## Branch Deletion

Temporary branches may be deleted only after:

- main contains the release;
- final release tag exists;
- production deployed ref is recorded;
- rollback ref is recorded;
- production smoke is green;
- safety artifacts are archived or explicitly retained.

Never delete protected production branches or final release tags.

## Rollback Refs

Each production rollout must record:

- previous deployed ref;
- new deployed ref;
- DB backup path;
- env/config backup path;
- rollback command.
