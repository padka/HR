#!/usr/bin/env bash
set -euo pipefail

# Mixed HTTP load test for local RecruitSmart Admin UI.
#
# Goal: attempt a target overall RPS distribution across multiple endpoints for a fixed duration.
# Uses autocannon via npx (no repo dependency install required).

BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
DURATION_SECONDS="${DURATION_SECONDS:-300}"

ADMIN_USER="${ADMIN_USER:-admin}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-admin}"

# Total target is 50k RPS. Adjust per-endpoint rates here.
RATE_HEALTH="${RATE_HEALTH:-15000}"
RATE_APP_DASHBOARD="${RATE_APP_DASHBOARD:-3000}"
RATE_AUTH_TOKEN="${RATE_AUTH_TOKEN:-2000}"
RATE_DASHBOARD_SUMMARY="${RATE_DASHBOARD_SUMMARY:-10000}"
RATE_DASHBOARD_INCOMING="${RATE_DASHBOARD_INCOMING:-12000}"
RATE_PROFILE="${RATE_PROFILE:-5000}"
RATE_CALENDAR_EVENTS="${RATE_CALENDAR_EVENTS:-3000}"

CONNECTIONS_LIGHT="${CONNECTIONS_LIGHT:-200}"
CONNECTIONS_HEAVY="${CONNECTIONS_HEAVY:-400}"
PIPELINING_LIGHT="${PIPELINING_LIGHT:-10}"
PIPELINING_HEAVY="${PIPELINING_HEAVY:-1}"
WORKERS="${WORKERS:-2}"
SAMPLE_INTERVAL_MS="${SAMPLE_INTERVAL_MS:-1000}"

STAMP="$(date +%Y%m%d_%H%M%S)"
OUT_DIR="${OUT_DIR:-.local/loadtest/http_mix_${STAMP}}"
mkdir -p "${OUT_DIR}"

echo "Base URL: ${BASE_URL}"
echo "Duration: ${DURATION_SECONDS}s"
echo "Output:   ${OUT_DIR}"

if ! command -v jq >/dev/null 2>&1; then
  echo "jq is required for token parsing. Install jq and retry." >&2
  exit 1
fi

TOKEN="${AUTH_TOKEN:-}"
if [[ -z "${TOKEN}" ]]; then
  echo "Obtaining access token..."
  TOKEN=""
  for attempt in 1 2 3; do
    resp="$(
      curl -sS -m 5 --connect-timeout 2 -X POST \
        -H 'Content-Type: application/x-www-form-urlencoded' \
        --data-urlencode "username=${ADMIN_USER}" \
        --data-urlencode "password=${ADMIN_PASSWORD}" \
        "${BASE_URL}/auth/token" || true
    )"
    # jq may fail on non-JSON (e.g. degraded HTML); keep it best-effort.
    parsed="$(echo "${resp}" | jq -r '.access_token // empty' 2>/dev/null || true)"
    if [[ -n "${parsed}" && "${parsed}" != "null" ]]; then
      TOKEN="${parsed}"
      break
    fi
    echo "Token attempt ${attempt} failed (non-JSON or missing access_token)." > "${OUT_DIR}/auth_token_attempt_${attempt}.err"
    echo "${resp}" > "${OUT_DIR}/auth_token_attempt_${attempt}.body" || true
    sleep 1
  done
fi

if [[ -z "${TOKEN}" || "${TOKEN}" == "null" ]]; then
  echo "Failed to obtain access token from ${BASE_URL}/auth/token" >&2
  echo "Hint: system may be degraded or ADMIN_USER/ADMIN_PASSWORD are wrong." >&2
  exit 1
fi

AUTH_HEADER="Authorization=Bearer ${TOKEN}"

run_one() {
  local name="$1"
  shift
  echo "Starting: ${name}"
  # We use --json to produce a single JSON summary per run.
  # -L controls sampling interval to reduce overhead for long tests.
  npx -y autocannon \
    -L "${SAMPLE_INTERVAL_MS}" \
    -w "${WORKERS}" \
    --json \
    "$@" \
    > "${OUT_DIR}/${name}.json" \
    2> "${OUT_DIR}/${name}.err" &
  echo "$!" > "${OUT_DIR}/${name}.pid"
}

# Skip endpoints by setting their RATE_* env var to 0.
maybe_run_one() {
  local name="$1"
  local rate="$2"
  shift 2
  if [[ "${rate}" -le 0 ]]; then
    echo "Skipping: ${name} (overallRate=${rate})"
    return 0
  fi
  run_one "${name}" --overallRate "${rate}" "$@"
}

# Unauthenticated / static-ish
maybe_run_one "health" "${RATE_HEALTH}" \
  -c "${CONNECTIONS_LIGHT}" -p "${PIPELINING_LIGHT}" -d "${DURATION_SECONDS}" \
  "${BASE_URL}/health"

maybe_run_one "app_dashboard" "${RATE_APP_DASHBOARD}" \
  -c "${CONNECTIONS_LIGHT}" -p "${PIPELINING_HEAVY}" -d "${DURATION_SECONDS}" \
  "${BASE_URL}/app/dashboard"

# Auth token (form POST)
maybe_run_one "auth_token" "${RATE_AUTH_TOKEN}" \
  -c "${CONNECTIONS_LIGHT}" -p "${PIPELINING_HEAVY}" -d "${DURATION_SECONDS}" \
  -m POST \
  -H "Content-Type=application/x-www-form-urlencoded" \
  -b "username=${ADMIN_USER}&password=${ADMIN_PASSWORD}" \
  "${BASE_URL}/auth/token"

# Authenticated APIs (read-only)
maybe_run_one "dashboard_summary" "${RATE_DASHBOARD_SUMMARY}" \
  -c "${CONNECTIONS_HEAVY}" -p "${PIPELINING_HEAVY}" -d "${DURATION_SECONDS}" \
  -H "${AUTH_HEADER}" \
  "${BASE_URL}/api/dashboard/summary"

maybe_run_one "dashboard_incoming" "${RATE_DASHBOARD_INCOMING}" \
  -c "${CONNECTIONS_HEAVY}" -p "${PIPELINING_HEAVY}" -d "${DURATION_SECONDS}" \
  -H "${AUTH_HEADER}" \
  "${BASE_URL}/api/dashboard/incoming?limit=6"

maybe_run_one "profile" "${RATE_PROFILE}" \
  -c "${CONNECTIONS_HEAVY}" -p "${PIPELINING_HEAVY}" -d "${DURATION_SECONDS}" \
  -H "${AUTH_HEADER}" \
  "${BASE_URL}/api/profile"

# Calendar range kept small to avoid enormous payloads in the load generator.
maybe_run_one "calendar_events" "${RATE_CALENDAR_EVENTS}" \
  -c "${CONNECTIONS_HEAVY}" -p "${PIPELINING_HEAVY}" -d "${DURATION_SECONDS}" \
  -H "${AUTH_HEADER}" \
  "${BASE_URL}/api/calendar/events?start=2026-02-01&end=2026-02-16"

echo "Waiting for workers to complete..."
wait

echo "Summarizing results..."
./.venv/bin/python scripts/summarize_autocannon.py "${OUT_DIR}"/*.json

echo "Done."
