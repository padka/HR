# name|weight(%)|method|path|auth_kind|connections|pipelining
#
# Mixed (UI-like) read profile:
# dashboard + incoming + calendar + profile + candidates list + notifications ops.
dashboard_summary|25|GET|/api/dashboard/summary|bearer|400|1
dashboard_incoming_6|8|GET|/api/dashboard/incoming?limit=6|bearer|400|1
dashboard_incoming_50|7|GET|/api/dashboard/incoming?limit=50|bearer|400|1
calendar_events_14d|7|GET|/api/calendar/events?start=2026-02-01&end=2026-02-15|bearer|400|1
calendar_events_30d|8|GET|/api/calendar/events?start=2026-02-01&end=2026-03-02|bearer|400|1
profile|15|GET|/api/profile|bearer|400|1
candidates_list_page1|10|GET|/api/candidates?page=1&per_page=20|bearer|400|1
candidates_list_waiting|10|GET|/api/candidates?page=1&per_page=20&status=waiting_slot|bearer|400|1
notifications_feed_pending|6|GET|/api/notifications/feed?status=pending|bearer|200|1
auth_token|3|POST|/auth/token|form_auth|200|1
health|1|GET|/health|none|200|10

