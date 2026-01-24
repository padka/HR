#!/usr/bin/env bash
# Development helper to run CRM stack (Admin UI + SPA) from one command.
# Optional: set RUN_BOT=1 or RUN_API=1 to include bot/admin_api.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

ENV_FILE=".env.local"
if [ ! -f "$ENV_FILE" ]; then
  ENV_FILE=".env.local.example"
  echo "Using $ENV_FILE (copy to .env.local and set secrets locally)."
fi

load_env_file() {
  set -a
  # shellcheck disable=SC1090
  source "$1"
  set +a
}

load_env_file "$ENV_FILE"
export ENVIRONMENT="${ENVIRONMENT:-development}"

if [ -d ".venv" ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

if [ "${RUN_MIGRATIONS:-1}" = "1" ]; then
  echo "Running migrations..."
  python3 scripts/run_migrations.py
fi

declare -a pids=()

start_bg() {
  local name="$1"
  shift
  echo "Starting ${name}..."
  "$@" &
  pids+=($!)
}

start_bg "Admin UI (http://localhost:8000)" \
  python3 -m uvicorn backend.apps.admin_ui.app:app --host 0.0.0.0 --port 8000 --reload

if [ "${RUN_API:-0}" = "1" ]; then
  start_bg "Admin API (http://localhost:8100)" \
    python3 -m uvicorn backend.apps.admin_api.main:app --host 0.0.0.0 --port 8100 --reload
fi

if [ "${RUN_BOT:-0}" = "1" ]; then
  start_bg "Telegram bot (polling)" python3 bot.py
fi

if [ "${RUN_VITE:-1}" = "1" ]; then
  start_bg "Vite dev server (http://localhost:5173)" npm --prefix frontend/app run dev
fi

cleanup() {
  if [ "${#pids[@]}" -gt 0 ]; then
    echo "Stopping background processes..."
    kill "${pids[@]}" 2>/dev/null || true
    wait "${pids[@]}" 2>/dev/null || true
  fi
}

trap cleanup INT TERM EXIT
wait
