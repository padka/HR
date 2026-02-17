#!/usr/bin/env bash
set -euo pipefail

# Capacity discovery runner: stepwise ramp until knee-of-curve.
#
# Artifacts:
# - OUT_PARENT/total_<rps>/{*.json,metrics.txt,step.json}
#
# Knee criteria live in analyze_step.py (can be overridden via env).

BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
PROFILE_PATH="${PROFILE_PATH:-}"
TARGET_TOTALS="${TARGET_TOTALS:-200 400 800 1200 1600}"
DURATION_SECONDS="${DURATION_SECONDS:-45}"

ADMIN_USER="${ADMIN_USER:-admin}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-admin}"

STAMP="$(date +%Y%m%d_%H%M%S)"
PROFILE_NAME="$(basename "${PROFILE_PATH}" .profile)"
OUT_PARENT="${OUT_PARENT:-.local/loadtest/profiles/${PROFILE_NAME}_${STAMP}/capacity}"
mkdir -p "${OUT_PARENT}"

echo "Capacity discovery"
echo "Base URL: ${BASE_URL}"
echo "Profile:  ${PROFILE_PATH}"
echo "Totals:   ${TARGET_TOTALS}"
echo "Duration: ${DURATION_SECONDS}s per step"
echo "Output:   ${OUT_PARENT}"
echo ""

export BASE_URL ADMIN_USER ADMIN_PASSWORD PROFILE_PATH DURATION_SECONDS

knee_total=""
prev_total=""

for total in ${TARGET_TOTALS}; do
  echo "== Step total=${total} rps =="
  OUT_DIR="${OUT_PARENT}/total_${total}"
  mkdir -p "${OUT_DIR}"

  TOTAL_RPS="${total}" OUT_DIR="${OUT_DIR}" ./scripts/loadtest_profiles/run_profile.sh

  curl -sS "${BASE_URL}/metrics" > "${OUT_DIR}/metrics.txt" 2>/dev/null || true
  ./.venv/bin/python scripts/loadtest_profiles/analyze_step.py "${OUT_DIR}" "${total}" > "${OUT_DIR}/step.json"
  cat "${OUT_DIR}/step.json"
  echo ""

  is_knee="$(jq -r '.is_knee // false' "${OUT_DIR}/step.json" 2>/dev/null || echo "false")"
  if [[ "${is_knee}" == "true" ]]; then
    knee_total="${total}"
    break
  fi
  prev_total="${total}"
done

if [[ -n "${knee_total}" ]]; then
  echo "KNEE detected at total=${knee_total} rps (previous stable=${prev_total:-n/a})"
  echo "{\"knee_total\": ${knee_total}, \"stable_total\": ${prev_total:-null}}" > "${OUT_PARENT}/knee.json"
else
  echo "No knee detected in provided totals; treating last step as stable."
  echo "{\"knee_total\": null, \"stable_total\": ${prev_total:-null}}" > "${OUT_PARENT}/knee.json"
fi

