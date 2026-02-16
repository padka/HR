#!/usr/bin/env bash
set -euo pipefail

# Capacity discovery runner for the mixed HTTP profile.
#
# Runs multiple short steps at increasing target totals and records results
# into separate output directories. This is meant for diagnostics, not
# "50k RPS on a laptop".

BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
ADMIN_USER="${ADMIN_USER:-admin}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-admin}"

# Space-separated totals (overall target across the mix).
TARGET_TOTALS="${TARGET_TOTALS:-1000 2000 5000 8000 12000}"
DURATION_SECONDS="${DURATION_SECONDS:-60}"

STAMP="$(date +%Y%m%d_%H%M%S)"
OUT_PARENT="${OUT_PARENT:-.local/loadtest/capacity_${STAMP}}"
mkdir -p "${OUT_PARENT}"

BASE_TOTAL=50000

# Baseline mix weights copied from scripts/loadtest_http_mix.sh defaults.
BASE_HEALTH=15000
BASE_APP_DASHBOARD=3000
BASE_AUTH_TOKEN=2000
BASE_DASHBOARD_SUMMARY=10000
BASE_DASHBOARD_INCOMING=12000
BASE_PROFILE=5000
BASE_CALENDAR_EVENTS=3000

scale_rate() {
  local base="$1"
  local total="$2"
  ./.venv/bin/python - <<PY
base = int(${base})
total = int(${total})
base_total = int(${BASE_TOTAL})
rate = int(round(base * (total / base_total)))
print(max(0, rate))
PY
}

echo "Capacity discovery"
echo "Base URL: ${BASE_URL}"
echo "Totals:   ${TARGET_TOTALS}"
echo "Output:   ${OUT_PARENT}"
echo ""

for total in ${TARGET_TOTALS}; do
  echo "== Step total=${total} rps (duration=${DURATION_SECONDS}s) =="

  export BASE_URL
  export ADMIN_USER
  export ADMIN_PASSWORD
  export DURATION_SECONDS

  export RATE_HEALTH="$(scale_rate "${BASE_HEALTH}" "${total}")"
  export RATE_APP_DASHBOARD="$(scale_rate "${BASE_APP_DASHBOARD}" "${total}")"
  export RATE_AUTH_TOKEN="$(scale_rate "${BASE_AUTH_TOKEN}" "${total}")"
  export RATE_DASHBOARD_SUMMARY="$(scale_rate "${BASE_DASHBOARD_SUMMARY}" "${total}")"
  export RATE_DASHBOARD_INCOMING="$(scale_rate "${BASE_DASHBOARD_INCOMING}" "${total}")"
  export RATE_PROFILE="$(scale_rate "${BASE_PROFILE}" "${total}")"
  export RATE_CALENDAR_EVENTS="$(scale_rate "${BASE_CALENDAR_EVENTS}" "${total}")"

  export OUT_DIR="${OUT_PARENT}/total_${total}"
  if ! ./scripts/loadtest_http_mix.sh; then
    echo "Step failed at total=${total}. Treat this as a knee-of-curve candidate and investigate." >&2
    break
  fi
  echo ""
done
