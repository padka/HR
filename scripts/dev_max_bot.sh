#!/usr/bin/env bash
# Development helper to run the MAX bot webhook service locally.
# Loads .env.local (or .env.local.example) and prints a safe checklist.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

echo "==================================================="
echo "Starting MAX Bot (development mode)"
echo "==================================================="

ENV_FILE=".env.local"
if [ ! -f "$ENV_FILE" ]; then
  ENV_FILE=".env.local.example"
  echo "ℹ Using $ENV_FILE (copy to .env.local and set MAX_BOT_TOKEN/SESSION_SECRET locally)."
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
  echo "✓ Using virtual environment: .venv"
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

echo "✓ Loaded env from $ENV_FILE"
python3 - <<'PY'
import os, urllib.parse
db = os.getenv("DATABASE_URL", "")
redis = os.getenv("REDIS_URL", "")
def fmt_db(url: str):
    if not url:
        return "missing"
    try:
        parsed = urllib.parse.urlparse(url)
        user = parsed.username or ""
        host = parsed.hostname or ""
        port = parsed.port or ""
        dbname = (parsed.path or "").lstrip("/")
        return f"{parsed.scheme} user={user} host={host} port={port} db={dbname}"
    except Exception as e:
        return f"unparseable ({e})"
def fmt_redis(url: str):
    if not url:
        return "missing"
    try:
        parsed = urllib.parse.urlparse(url)
        host = parsed.hostname or ""
        port = parsed.port or ""
        db = (parsed.path or "").lstrip("/") or "0"
        return f"{parsed.scheme} host={host} port={port} db={db}"
    except Exception as e:
        return f"unparseable ({e})"
print("Checklist:")
print(f"  DATABASE_URL      : {fmt_db(db)}")
print(f"  REDIS_URL         : {fmt_redis(redis)}")
print(f"  MAX_BOT_ENABLED   : {os.getenv('MAX_BOT_ENABLED', '')}")
print(f"  MAX_BOT_TOKEN set : {'yes' if os.getenv('MAX_BOT_TOKEN') else 'no'}")
print(f"  MAX_WEBHOOK_URL   : {os.getenv('MAX_WEBHOOK_URL', '') or 'missing'}")
print(f"  MAX secret set    : {'yes' if os.getenv('MAX_WEBHOOK_SECRET') else 'no'}")
PY

echo ""
echo "Running database migrations..."
python3 scripts/run_migrations.py

PORT="${MAX_BOT_PORT:-8010}"
echo ""
echo "Starting uvicorn (http://localhost:${PORT})..."
exec uvicorn backend.apps.max_bot.app:create_app --factory --host 0.0.0.0 --port "${PORT}" --reload
