#!/usr/bin/env bash
set -euo pipefail

# Steady-state runner for a given profile at a fixed total RPS.

BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
PROFILE_PATH="${PROFILE_PATH:-}"

TOTAL_RPS="${TOTAL_RPS:-800}"
DURATION_SECONDS="${DURATION_SECONDS:-300}"

ADMIN_USER="${ADMIN_USER:-admin}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-admin}"

STAMP="$(date +%Y%m%d_%H%M%S)"
PROFILE_NAME="$(basename "${PROFILE_PATH}" .profile)"
OUT_PARENT="${OUT_PARENT:-.local/loadtest/profiles/${PROFILE_NAME}_${STAMP}/steady}"
OUT_DIR="${OUT_DIR:-${OUT_PARENT}/total_${TOTAL_RPS}}"
mkdir -p "${OUT_DIR}"

echo "Steady run"
echo "Base URL: ${BASE_URL}"
echo "Profile:  ${PROFILE_PATH}"
echo "Total:    ${TOTAL_RPS} rps"
echo "Duration: ${DURATION_SECONDS}s"
echo "Output:   ${OUT_DIR}"
echo ""

export BASE_URL ADMIN_USER ADMIN_PASSWORD PROFILE_PATH TOTAL_RPS DURATION_SECONDS OUT_DIR

./scripts/loadtest_profiles/run_profile.sh
curl -sS "${BASE_URL}/metrics" > "${OUT_DIR}/metrics.txt" 2>/dev/null || true
./.venv/bin/python scripts/loadtest_profiles/analyze_step.py "${OUT_DIR}" "${TOTAL_RPS}" > "${OUT_DIR}/step.json"
cat "${OUT_DIR}/step.json"

