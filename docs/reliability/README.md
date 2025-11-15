# Reliability Artifacts

This directory stores evidence collected during reliability/regression exercises:

- `*-loadtest.json` and `.csv` — raw outputs from `scripts/loadtest_notifications.py`.
- `*-grafana.png` — screenshots of alert dashboards.
- `*-sandbox.json` / `.md` — telemetry + notes from `scripts/e2e_notifications_sandbox.py`.

Guidelines:

1. Use ISO dates in filenames (`YYYYMMDD-description.ext`) to keep the chronology sortable.
2. Keep raw tool output untouched; add context/analysis next to it in a `README` or Markdown note.
3. Do **not** commit secrets (bot tokens, Redis URLs with credentials). Sanitize exports before adding them.

CI jobs place their temporary load-test exports under this directory and upload them as artifacts; they are not committed back to the repository.
