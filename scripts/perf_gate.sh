#!/usr/bin/env bash
set -euo pipefail

# Performance gate for GO-live readiness.
# Runs a mixed profile at a single target envelope (default 600 rps) and
# fails when latency/error thresholds are exceeded.

BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
PROFILE_PATH="${PROFILE_PATH:-scripts/loadtest_profiles/profiles/mixed.profile}"
TOTAL_RPS="${TOTAL_RPS:-600}"
DURATION_SECONDS="${DURATION_SECONDS:-20}"
ADMIN_USER="${ADMIN_USER:-admin}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-admin}"
PERF_GATE_WARMUP_ROUNDS="${PERF_GATE_WARMUP_ROUNDS:-12}"

# GO threshold contract
KNEE_ERROR_RATE_MAX="${KNEE_ERROR_RATE_MAX:-0.01}"             # < 1%
KNEE_LATENCY_P95_MAX_SECONDS="${KNEE_LATENCY_P95_MAX_SECONDS:-0.25}"  # < 250ms
KNEE_LATENCY_P99_MAX_SECONDS="${KNEE_LATENCY_P99_MAX_SECONDS:-1.0}"   # < 1000ms
KNEE_POOL_ACQUIRE_P95_MAX_SECONDS="${KNEE_POOL_ACQUIRE_P95_MAX_SECONDS:-0.10}"
KNEE_POOL_MIN_SAMPLES="${KNEE_POOL_MIN_SAMPLES:-50}"

STAMP="$(date +%Y%m%d_%H%M%S)"
OUT_PARENT="${OUT_PARENT:-.local/loadtest/perf_gate_${STAMP}}"
mkdir -p "${OUT_PARENT}"

echo "Perf gate"
echo "  BASE_URL=${BASE_URL}"
echo "  PROFILE_PATH=${PROFILE_PATH}"
echo "  TOTAL_RPS=${TOTAL_RPS}"
echo "  DURATION_SECONDS=${DURATION_SECONDS}"
echo "  PERF_GATE_WARMUP_ROUNDS=${PERF_GATE_WARMUP_ROUNDS}"
echo "  OUT_PARENT=${OUT_PARENT}"
echo ""

if [[ "${PERF_GATE_WARMUP_ROUNDS}" -gt 0 ]]; then
  echo "Running warmup (${PERF_GATE_WARMUP_ROUNDS} rounds)..."
  token_json="$(curl -fsS -X POST "${BASE_URL}/auth/token" -d "username=${ADMIN_USER}&password=${ADMIN_PASSWORD}")"
  token="$(printf '%s' "${token_json}" | jq -r '.access_token // empty')"
  if [[ -z "${token}" ]]; then
    echo "perf-gate: failed to obtain auth token for warmup" >&2
    exit 2
  fi
  declare -a warm_paths=(
    "/api/dashboard/summary"
    "/api/dashboard/incoming?limit=6"
    "/api/dashboard/incoming?limit=50"
    "/api/profile"
    "/api/calendar/events?start=2026-02-01&end=2026-02-15"
    "/api/calendar/events?start=2026-02-01&end=2026-03-02"
    "/api/candidates?page=1&per_page=20"
    "/api/candidates?page=1&per_page=20&status=waiting_slot"
    "/api/notifications/feed?status=pending"
  )
  for _ in $(seq 1 "${PERF_GATE_WARMUP_ROUNDS}"); do
    for path in "${warm_paths[@]}"; do
      curl -fsS -H "Authorization: Bearer ${token}" "${BASE_URL}${path}" >/dev/null || true
    done
  done
  echo "Warmup complete."
  echo ""
fi

export BASE_URL PROFILE_PATH DURATION_SECONDS ADMIN_USER ADMIN_PASSWORD
export KNEE_ERROR_RATE_MAX KNEE_LATENCY_P95_MAX_SECONDS KNEE_LATENCY_P99_MAX_SECONDS
export KNEE_POOL_ACQUIRE_P95_MAX_SECONDS KNEE_POOL_MIN_SAMPLES
TARGET_TOTALS="${TOTAL_RPS}" OUT_PARENT="${OUT_PARENT}" ./scripts/loadtest_profiles/capacity.sh

STEP_JSON="${OUT_PARENT}/total_${TOTAL_RPS}/step.json"
if [[ ! -f "${STEP_JSON}" ]]; then
  echo "perf-gate: missing step.json at ${STEP_JSON}" >&2
  exit 2
fi

cp -f "${STEP_JSON}" "${OUT_PARENT}/perf_gate_summary.json"

is_knee="$(jq -r '.is_knee // false' "${STEP_JSON}")"
error_rate="$(jq -r '.error_rate // 0' "${STEP_JSON}")"
p95="$(jq -r '.max_latency_p95_seconds // 0' "${STEP_JSON}")"
p99="$(jq -r '.max_latency_p99_seconds // 0' "${STEP_JSON}")"
reasons="$(jq -c '.reasons // []' "${STEP_JSON}")"

echo "Gate result:"
echo "  error_rate=${error_rate}"
echo "  max_latency_p95_seconds=${p95}"
echo "  max_latency_p99_seconds=${p99}"
echo "  reasons=${reasons}"
echo "  summary=${OUT_PARENT}/perf_gate_summary.json"

if [[ "${is_knee}" == "true" ]]; then
  echo "perf-gate: FAIL (threshold exceeded)"
  exit 1
fi

echo "perf-gate: PASS"
