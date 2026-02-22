#!/usr/bin/env bash
set -euo pipefail

# Spike runner for the mixed HTTP profile.
#
# Runs two steps:
# - warm-up at STEADY_RPS for STEADY_SECONDS
# - spike at SPIKE_RPS for SPIKE_SECONDS

BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
ADMIN_USER="${ADMIN_USER:-admin}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-admin}"

STEADY_RPS="${STEADY_RPS:-2000}"
STEADY_SECONDS="${STEADY_SECONDS:-30}"

SPIKE_RPS="${SPIKE_RPS:-6000}"
SPIKE_SECONDS="${SPIKE_SECONDS:-15}"

STAMP="$(date +%Y%m%d_%H%M%S)"
OUT_PARENT="${OUT_PARENT:-.local/loadtest/spike_${STAMP}}"
mkdir -p "${OUT_PARENT}"

echo "Spike test"
echo "Base URL: ${BASE_URL}"
echo "Steady:   ${STEADY_RPS} rps for ${STEADY_SECONDS}s"
echo "Spike:    ${SPIKE_RPS} rps for ${SPIKE_SECONDS}s"
echo "Output:   ${OUT_PARENT}"
echo ""

export BASE_URL ADMIN_USER ADMIN_PASSWORD

export DURATION_SECONDS="${STEADY_SECONDS}"
export TARGET_TOTALS="${STEADY_RPS}"
export OUT_PARENT="${OUT_PARENT}/steady"
./scripts/loadtest_http_capacity.sh

export DURATION_SECONDS="${SPIKE_SECONDS}"
export TARGET_TOTALS="${SPIKE_RPS}"
export OUT_PARENT="${OUT_PARENT}/spike"
./scripts/loadtest_http_capacity.sh

