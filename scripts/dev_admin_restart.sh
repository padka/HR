#!/usr/bin/env bash
# Restart helper: frees the Admin UI port, then runs dev_admin.sh.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORT="${PORT:-8000}"

free_port() {
  if ! command -v lsof >/dev/null 2>&1; then
    echo "⚠ lsof not found; cannot auto-stop port ${PORT}."
    return 0
  fi

  local pids
  pids="$(lsof -tiTCP:"${PORT}" -sTCP:LISTEN || true)"
  if [ -z "${pids}" ]; then
    echo "✓ Port ${PORT} is free."
    return 0
  fi

  echo "Stopping process(es) on port ${PORT}: ${pids}"
  kill ${pids} || true
  sleep 1

  if lsof -tiTCP:"${PORT}" -sTCP:LISTEN >/dev/null 2>&1; then
    echo "Force killing remaining process(es) on port ${PORT}."
    lsof -tiTCP:"${PORT}" -sTCP:LISTEN | xargs kill -9 || true
  fi
}

free_port
exec "${SCRIPT_DIR}/dev_admin.sh"
