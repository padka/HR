# name|weight(%)|method|path|auth_kind|connections|pipelining|body_file(optional)
#
# Write-heavy profile (controlled):
# - Requires PERF_CANDIDATE_ID to exist.
# - Uses proper CSRF token + cookie (run_profile.sh fetches /api/csrf once).
chat_send|60|POST|/api/candidates/__CANDIDATE_ID__/chat|bearer_csrf|200|1|scripts/loadtest_profiles/bodies/chat_send.json
chat_history|10|GET|/api/candidates/__CANDIDATE_ID__/chat?limit=50|bearer|200|1
candidate_detail|10|GET|/api/candidates/__CANDIDATE_ID__|bearer|200|1
dashboard_incoming|10|GET|/api/dashboard/incoming?limit=6|bearer|200|1
auth_token|8|POST|/auth/token|form_auth|200|1
health|2|GET|/health|none|200|10

