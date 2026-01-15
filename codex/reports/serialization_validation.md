# Serialization validation follow-up

## Summary
- Audited admin UI templates that rely on the `tojson` filter (`index.html`, `slots_list.html`).
- Ensured that the dashboard route encodes calendar and weekly KPI payloads with `jsonable_encoder` before rendering.
- Confirmed slot list helpers continue to deliver JSON-safe payloads for embedded script blocks.

## Testing
- `pytest tests/services/test_dashboard_and_slots.py -q`
- Attempted `pytest -q` (blocked by unrelated suite configuration and uvloop policy conflicts)
- `npm run test:e2e` *(not available; package.json does not define the script)*

## Notes
- Local Playwright smoke tests and manual UI verification are limited in this containerised environment; see PR discussion for details.
