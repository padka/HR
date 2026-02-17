#!/usr/bin/env bash
set -euo pipefail

# Spike runner: warmup at STEADY_RPS, then brief spike at SPIKE_RPS.

BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
PROFILE_PATH="${PROFILE_PATH:-}"

STEADY_RPS="${STEADY_RPS:-800}"
STEADY_SECONDS="${STEADY_SECONDS:-30}"

SPIKE_RPS="${SPIKE_RPS:-1200}"
SPIKE_SECONDS="${SPIKE_SECONDS:-30}"

ADMIN_USER="${ADMIN_USER:-admin}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-admin}"

STAMP="$(date +%Y%m%d_%H%M%S)"
PROFILE_NAME="$(basename "${PROFILE_PATH}" .profile)"
OUT_PARENT="${OUT_PARENT:-.local/loadtest/profiles/${PROFILE_NAME}_${STAMP}/spike}"
mkdir -p "${OUT_PARENT}"

echo "Spike test"
echo "Base URL: ${BASE_URL}"
echo "Profile:  ${PROFILE_PATH}"
echo "Steady:   ${STEADY_RPS} rps for ${STEADY_SECONDS}s"
echo "Spike:    ${SPIKE_RPS} rps for ${SPIKE_SECONDS}s"
echo "Output:   ${OUT_PARENT}"
echo ""

export BASE_URL ADMIN_USER ADMIN_PASSWORD PROFILE_PATH

OUT_DIR="${OUT_PARENT}/steady"
curl -sS "${BASE_URL}/metrics" > "${OUT_DIR}/metrics_before.txt" 2>/dev/null || true
TOTAL_RPS="${STEADY_RPS}" DURATION_SECONDS="${STEADY_SECONDS}" OUT_DIR="${OUT_DIR}" ./scripts/loadtest_profiles/run_profile.sh
curl -sS "${BASE_URL}/metrics" > "${OUT_DIR}/metrics_after.txt" 2>/dev/null || true
cp -f "${OUT_DIR}/metrics_after.txt" "${OUT_DIR}/metrics.txt" 2>/dev/null || true
./.venv/bin/python scripts/loadtest_profiles/analyze_step.py "${OUT_DIR}" "${STEADY_RPS}" > "${OUT_DIR}/step.json"

OUT_DIR="${OUT_PARENT}/spike"
curl -sS "${BASE_URL}/metrics" > "${OUT_DIR}/metrics_before.txt" 2>/dev/null || true
TOTAL_RPS="${SPIKE_RPS}" DURATION_SECONDS="${SPIKE_SECONDS}" OUT_DIR="${OUT_DIR}" ./scripts/loadtest_profiles/run_profile.sh
curl -sS "${BASE_URL}/metrics" > "${OUT_DIR}/metrics_after.txt" 2>/dev/null || true
cp -f "${OUT_DIR}/metrics_after.txt" "${OUT_DIR}/metrics.txt" 2>/dev/null || true
./.venv/bin/python scripts/loadtest_profiles/analyze_step.py "${OUT_DIR}" "${SPIKE_RPS}" > "${OUT_DIR}/step.json"

echo ""
echo "Steady step:"
cat "${OUT_PARENT}/steady/step.json"
echo ""
echo "Spike step:"
cat "${OUT_PARENT}/spike/step.json"
