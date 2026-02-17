#!/usr/bin/env bash
set -euo pipefail

# Generic profile runner for admin_ui HTTP load tests.
#
# Inputs:
# - PROFILE_PATH: pipe-delimited file describing request mix (see profiles/*.profile)
# - TOTAL_RPS: target total RPS across the mix
# - DURATION_SECONDS: run duration
#
# Outputs:
# - Writes autocannon JSON results into OUT_DIR
# - Writes aggregated summary to stdout (via summarize_profile.py)
#
# Notes:
# - Token is obtained once and reused for all Bearer requests.
# - This is a diagnostics harness; it will be "client capped" on laptops at high totals.

BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
PROFILE_PATH="${PROFILE_PATH:-}"
TOTAL_RPS="${TOTAL_RPS:-2000}"
DURATION_SECONDS="${DURATION_SECONDS:-60}"

ADMIN_USER="${ADMIN_USER:-admin}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-admin}"

WORKERS="${WORKERS:-2}"
SAMPLE_INTERVAL_MS="${SAMPLE_INTERVAL_MS:-1000}"

OUT_DIR="${OUT_DIR:-}"

if [[ -z "${PROFILE_PATH}" ]]; then
  echo "PROFILE_PATH is required (e.g. scripts/loadtest_profiles/profiles/read_heavy.profile)" >&2
  exit 2
fi
if [[ ! -f "${PROFILE_PATH}" ]]; then
  echo "Profile file not found: ${PROFILE_PATH}" >&2
  exit 2
fi

if ! command -v jq >/dev/null 2>&1; then
  echo "jq is required for token parsing. Install jq and retry." >&2
  exit 1
fi

STAMP="$(date +%Y%m%d_%H%M%S)"
if [[ -z "${OUT_DIR}" ]]; then
  OUT_DIR=".local/loadtest/profiles/$(basename "${PROFILE_PATH}" .profile)_${STAMP}/run"
fi
mkdir -p "${OUT_DIR}"

echo "Base URL: ${BASE_URL}"
echo "Profile:  ${PROFILE_PATH}"
echo "Total:    ${TOTAL_RPS} rps"
echo "Duration: ${DURATION_SECONDS}s"
echo "Output:   ${OUT_DIR}"

TOKEN="${AUTH_TOKEN:-}"
if [[ -z "${TOKEN}" ]]; then
  echo "Obtaining access token..."
  resp="$(
    curl -sS -m 5 --connect-timeout 2 -X POST \
      -H 'Content-Type: application/x-www-form-urlencoded' \
      --data-urlencode "username=${ADMIN_USER}" \
      --data-urlencode "password=${ADMIN_PASSWORD}" \
      "${BASE_URL}/auth/token" || true
  )"
  TOKEN="$(echo "${resp}" | jq -r '.access_token // empty' 2>/dev/null || true)"
fi
if [[ -z "${TOKEN}" || "${TOKEN}" == "null" ]]; then
  echo "Failed to obtain access token from ${BASE_URL}/auth/token" >&2
  echo "Hint: set ADMIN_USER/ADMIN_PASSWORD or AUTH_TOKEN explicitly." >&2
  exit 1
fi

AUTH_HEADER="Authorization=Bearer ${TOKEN}"

# CSRF token + cookie jar (for state-changing API calls).
COOKIE_JAR="${OUT_DIR}/cookies.txt"
CSRF_TOKEN=""
COOKIE_HEADER=""
csrf_resp="$(
  curl -sS -m 5 --connect-timeout 2 \
    -c "${COOKIE_JAR}" -b "${COOKIE_JAR}" \
    "${BASE_URL}/api/csrf" || true
)"
CSRF_TOKEN="$(echo "${csrf_resp}" | jq -r '.token // empty' 2>/dev/null || true)"
if [[ -n "${CSRF_TOKEN}" && -f "${COOKIE_JAR}" ]]; then
  COOKIE_HEADER="$(awk 'BEGIN{out=\"\"} !/^#/ && NF>=7 { if(length(out)) out=out\"; \"; out=out $6\"=\" $7 } END{print out}' "${COOKIE_JAR}")"
fi

scale_rate() {
  local weight="$1"
  local total="$2"
  ./.venv/bin/python - <<PY
weight = float(${weight})
total = float(${total})
# autocannon overallRate is per worker when -w is used.
workers = int(${WORKERS})
rate = int(round((total * (weight / 100.0)) / max(1, workers)))
print(max(0, rate))
PY
}

run_one() {
  local name="$1"
  shift
  echo "Starting: ${name}"
  npx -y autocannon \
    -L "${SAMPLE_INTERVAL_MS}" \
    -w "${WORKERS}" \
    --json \
    "$@" \
    > "${OUT_DIR}/${name}.json" \
    2> "${OUT_DIR}/${name}.err" &
  echo "$!" > "${OUT_DIR}/${name}.pid"
}

maybe_run_one() {
  local name="$1"
  local rate="$2"
  shift 2
  if [[ "${rate}" -le 0 ]]; then
    echo "Skipping: ${name} (rate=${rate})"
    return 0
  fi
  run_one "${name}" --overallRate "${rate}" "$@"
}

while IFS="|" read -r name weight method path auth_kind connections pipelining body_file; do
  [[ -z "${name}" ]] && continue
  [[ "${name}" =~ ^# ]] && continue

  weight="${weight:-0}"
  method="${method:-GET}"
  auth_kind="${auth_kind:-none}"
  connections="${connections:-200}"
  pipelining="${pipelining:-1}"
  body_file="${body_file:-}"

  rate="$(scale_rate "${weight}" "${TOTAL_RPS}")"
  # Simple placeholder substitution for controlled write profiles.
  path="${path//__CANDIDATE_ID__/${PERF_CANDIDATE_ID:-1}}"
  url="${BASE_URL}${path}"

  common_args=(-c "${connections}" -p "${pipelining}" -d "${DURATION_SECONDS}")
  extra_args=()
  if [[ -n "${body_file}" ]]; then
    if [[ ! -f "${body_file}" ]]; then
      echo "Body file not found for ${name}: ${body_file}" >&2
      exit 2
    fi
    extra_args=(-H "Content-Type=application/json" -b "$(cat "${body_file}")")
  fi

  if [[ "${auth_kind}" == "bearer" ]]; then
    args=("${common_args[@]}" -m "${method}" -H "${AUTH_HEADER}")
    if ((${#extra_args[@]})); then
      args+=("${extra_args[@]}")
    fi
    args+=("${url}")
    maybe_run_one "${name}" "${rate}" \
      "${args[@]}"
    continue
  fi

  if [[ "${auth_kind}" == "bearer_csrf" ]]; then
    if [[ -z "${CSRF_TOKEN}" || -z "${COOKIE_HEADER}" ]]; then
      echo "CSRF token/cookie missing; cannot run ${name} safely." >&2
      exit 2
    fi
    args=(
      "${common_args[@]}"
      -m "${method}"
      -H "${AUTH_HEADER}"
      -H "X-CSRF-Token: ${CSRF_TOKEN}"
      -H "Cookie: ${COOKIE_HEADER}"
    )
    if ((${#extra_args[@]})); then
      args+=("${extra_args[@]}")
    fi
    args+=("${url}")
    maybe_run_one "${name}" "${rate}" "${args[@]}"
    continue
  fi

  if [[ "${auth_kind}" == "form_auth" ]]; then
    maybe_run_one "${name}" "${rate}" \
      "${common_args[@]}" \
      -m POST \
      -H "Content-Type=application/x-www-form-urlencoded" \
      -b "username=${ADMIN_USER}&password=${ADMIN_PASSWORD}" \
      "${url}"
    continue
  fi

  # Unauthenticated GET by default.
  maybe_run_one "${name}" "${rate}" \
    "${common_args[@]}" \
    -m "${method}" \
    "${url}"
done < "${PROFILE_PATH}"

echo "Waiting for workers to complete..."
wait

echo "Summarizing results..."
./.venv/bin/python scripts/loadtest_profiles/summarize_profile.py "${OUT_DIR}"

echo "Done."
