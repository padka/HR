#!/usr/bin/env bash
set -euo pipefail

# Steady-state runner for the mixed HTTP profile.
#
# Uses the same mix as scripts/loadtest_http_mix.sh, scaled down from the
# 50k baseline. Choose a total that the system can sustain and run 5 minutes.

BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
ADMIN_USER="${ADMIN_USER:-admin}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-admin}"

TOTAL_RPS="${TOTAL_RPS:-2000}"
DURATION_SECONDS="${DURATION_SECONDS:-300}"

export BASE_URL ADMIN_USER ADMIN_PASSWORD DURATION_SECONDS

# Reuse the capacity scaling script for rate computation.
export TARGET_TOTALS="${TOTAL_RPS}"
export OUT_PARENT="${OUT_PARENT:-.local/loadtest/steady_$(date +%Y%m%d_%H%M%S)}"

./scripts/loadtest_http_capacity.sh

