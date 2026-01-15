# Fix slots serialization issue

## Summary
- Normalized recruiter and city data passed to the `/slots` template so that the context no longer includes raw SQLAlchemy instances when serializing to JSON.
- Added an explicit `slots_context` payload that is pre-encoded with `jsonable_encoder` before being rendered via `tojson` in `slots_list.html`.
- Kept the original server-rendered table behaviour intact by providing dictionaries with the same fields that were previously read from ORM objects.

## Testing
- `pytest tests/services/test_dashboard_and_slots.py -k slots_list_status` *(skipped: starlette dependency unavailable in the container environment)*
- Manual smoke tests of `/slots`, `/candidates`, and `/recruiters` were not executed because the admin UI server is not running inside the execution environment.
