# name|weight(%)|method|path|auth_kind|connections|pipelining
#
# Read-heavy, life-like mix:
# - low /health
# - bearer token reused
# - limited param variants to avoid cardinality explosion
dashboard_summary|35|GET|/api/dashboard/summary|bearer|400|1
dashboard_incoming_6|10|GET|/api/dashboard/incoming?limit=6|bearer|400|1
dashboard_incoming_50|10|GET|/api/dashboard/incoming?limit=50|bearer|400|1
calendar_events_14d|10|GET|/api/calendar/events?start=2026-02-01&end=2026-02-15|bearer|400|1
calendar_events_30d|10|GET|/api/calendar/events?start=2026-02-01&end=2026-03-02|bearer|400|1
profile|24|GET|/api/profile|bearer|400|1
# /auth/token is deliberately excluded from the mix: it is strictly rate-limited and
# would distort knee-of-curve for application endpoints. Token is fetched once.
auth_token|0|POST|/auth/token|form_auth|200|1
health|1|GET|/health|none|200|10
