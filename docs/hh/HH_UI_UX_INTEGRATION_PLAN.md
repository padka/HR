# HH UI UX Integration Plan

## Candidate detail
Add HH block with:
- source badge `HH`
- `resume_id`, `negotiation_id`, `vacancy_id`
- employer state badge
- sync state badge (`synced`, `pending_sync`, `failed_sync`, `conflicted`)
- deep link to HH resume / negotiation / vacancy where available
- last sync timestamp
- raw last error preview
- manual re-sync button
- list of currently available HH actions

## Candidate lists
Add:
- source filter (`bot`, `manual_call`, `hh`, etc.)
- sync state filter
- icons for `pending_sync` and `conflict`
- safe bulk actions only where action is known to be supported for all selected records

## Admin / system area
Add HH integration page:
- connect/disconnect employer account
- token health / expiry
- current employer / manager account
- current webhook receiver URL
- last webhook received at
- last sync error
- buttons for test connection, refresh token, re-register webhooks, re-sync vacancy, re-sync candidate

## UX rules
- Never show recruiter arbitrary HH statuses as editable dropdown.
- Show only available actions fetched from HH.
- If action execution is async, show `pending_sync` immediately.
- If conflict exists, show explicit blocking banner, not silent mismatch.
- If HH is unavailable, local recruiter action should surface `queued / failed / retrying`, not silently disappear.
