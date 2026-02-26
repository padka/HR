# Formal Gate: Sprint 1/2

## Purpose
Formal gate for:
- Sprint 1: UX/conversion blockers.
- Sprint 2: external security hardening.

The gate creates a reproducible PASS/FAIL report with explicit manual sign-off items.

## Run

```bash
python3 scripts/formal_gate_sprint12.py
```

Optional flags:

```bash
python3 scripts/formal_gate_sprint12.py \
  --manual-sprint1-ux pass \
  --manual-sprint1-demo pass \
  --manual-sprint2-security pass \
  --fail-on-pending
```

## Artifacts
- `.local/gates/sprint1_2/latest.json`
- `.local/gates/sprint1_2/latest.md`
- `.local/gates/sprint1_2/route_inventory.md`
- `docs/gates/SPRINT1_2_LAST_RUN.md` (mirrored summary)
- `docs/gates/SPRINT1_2_ROUTE_INVENTORY_LAST_RUN.md` (mirrored inventory)

## Criteria Matrix

### Sprint 1
- `S1-1`: smoke/a11y/focus e2e + regression flow (`city -> slot -> candidate`) green.
- `S1-2`: core CRUD flow regressions absent (backend + frontend checks).
- `S1-3`: no P1 UX defects in `slots/cities/candidates` (manual sign-off).
- `S1-4`: demo gate `city -> slot -> candidate` (manual sign-off).

### Sprint 2
- `S2-1`: unauthorized requests to closed endpoints return `401/403`.
- `S2-2`: security regressions cover API + websocket auth/scope filtering.
- `S2-3`: no critical unguarded routes in admin surface (route inventory).
- `S2-4`: internal security review sign-off (manual).

## Exit Codes
- `0`: no automatic failures (`pass` or `manual_pending`).
- `2`: at least one failed criterion/check.
- `3`: no failures, but manual sign-off is pending and `--fail-on-pending` is set.
