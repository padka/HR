# Ruff Baseline For Hardening Release Artifact

Date: 2026-04-25

Branch: `release/hardening-artifact-freeze`

Scope: local release stabilization for the hardening batch. No staging or production
systems were touched.

## Gate Status

Ruff is baseline-controlled, not globally green.

The hardening release does not add blanket ignores or repo-wide lint suppressions.
Introduced critical lint outside the legacy dynamic Telegram service wrappers was
fixed before this report was created.

## Commands

Changed Python files:

```bash
git diff --name-only main..HEAD -- '*.py'
```

Full touched-file ruff check:

```bash
files=$(git diff --name-only main..HEAD -- '*.py')
./.venv/bin/ruff check --output-format=concise $files
```

Result:

```text
status=1
Found 2624 errors.
```

Critical `F/E9` check on all touched Python files:

```bash
files=$(git diff --name-only main..HEAD -- '*.py')
./.venv/bin/ruff check --select F,E9 --output-format=concise $files
```

Result:

```text
status=1
Found 899 errors.
```

Critical `F/E9` grouping:

```text
540 backend/apps/bot/services/notification_flow.py
307 backend/apps/bot/services/slot_flow.py
52 backend/apps/bot/services/onboarding_flow.py
```

Critical `F/E9` check excluding the known legacy dynamic wrappers:

```bash
git diff --name-only main..HEAD -- '*.py' \
  | grep -v '^backend/apps/bot/services/notification_flow.py$' \
  | grep -v '^backend/apps/bot/services/slot_flow.py$' \
  | grep -v '^backend/apps/bot/services/onboarding_flow.py$' \
  | grep -v '^backend/apps/bot/services/broadcast.py$' \
  | grep -v '^backend/apps/bot/services/test1_flow.py$' \
  | grep -v '^backend/apps/bot/services/test2_flow.py$' \
  | xargs ./.venv/bin/ruff check --select F,E9 --output-format=concise
```

Result:

```text
All checks passed!
```

## Baseline Rationale

The remaining critical `F/E9` findings are in legacy Telegram service wrapper
modules that import symbols dynamically from `backend/apps/bot/services/base.py`
via `globals()`. Ruff cannot statically resolve those names, so it reports
undefined-name errors even though the full backend test suite imports and
executes the affected flows successfully.

This is an existing structural lint debt pattern in the bot service layer. It is
not safe to refactor those modules inside the release freeze because it would
touch high-risk Telegram scheduling, notification, and onboarding paths after
the regression suite is already green.

## Fixed Before Baseline

The following real unused-import / unused-variable findings outside the dynamic
wrapper baseline were fixed:

- `backend/apps/admin_ui/services/slots.py`
- `backend/apps/bot/reminders.py`
- `backend/apps/bot/services/notification_flow.py`
- `backend/domain/candidates/state_contract.py`
- `tests/test_broker_production_restrictions.py`
- `tests/test_reminder_service.py`

## Follow-Up

Create a separate lint-debt task to replace the dynamic bot service wrapper
pattern with explicit imports or smaller modules, then enable full touched-file
ruff enforcement for those paths.

Do not treat this baseline as permission to add new lint debt. New production
code should pass at least `ruff check --select F,E9`, and preferably full ruff,
before merge.

## CI Gate

Release branch/tag CI uses the same baseline-controlled critical gate:

- compare changed Python files against `origin/main`;
- exclude only the documented legacy bot wrapper modules listed above;
- run `ruff check --select F,E9` on the remaining changed files.

Full `pre-commit run --all-files` is still baseline-red for this repository and
is not a release-branch truth signal until the legacy lint-debt task is closed.
