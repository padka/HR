#!/usr/bin/env bash
# Development helper to run the Telegram bot locally (polling).
# Loads .env.local (or .env.local.example) and prints a safe checklist.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

echo "==================================================="
echo "Starting Telegram Bot (development mode)"
echo "==================================================="

if [ -n "${BOT_TOKEN:-}" ]; then
  echo "⚠ Detected BOT_TOKEN in shell environment; ignoring it and using env file instead."
  unset BOT_TOKEN
fi

ENV_FILE=".env.local"
if [ ! -f "$ENV_FILE" ]; then
  ENV_FILE=".env.local.example"
  echo "ℹ Using $ENV_FILE (copy to .env.local and set BOT_TOKEN/SESSION_SECRET locally)."
fi

load_env_file() {
  set -a
  # shellcheck disable=SC1090
  source "$1"
  set +a
}

load_env_file "$ENV_FILE"
export ENVIRONMENT="${ENVIRONMENT:-development}"

# Activate virtual environment if it exists
if [ -d ".venv" ]; then
    echo "✓ Using virtual environment: .venv"
    # shellcheck disable=SC1091
    source .venv/bin/activate
fi

echo "✓ Loaded env from $ENV_FILE"
python3 - "$ENV_FILE" <<'PY'
import os, urllib.parse, sys
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
print(f"  DATABASE_URL: {fmt_db(db)}")
print(f"  REDIS_URL   : {fmt_redis(redis)}")
token = os.getenv("BOT_TOKEN", "")
print(f"  BOT_TOKEN present: {'yes' if token else 'no'}")
print(f"  BOT_TOKEN has colon: {(':' in token)}")
PY

echo ""
echo "Starting bot (polling)..."
exec python3 bot.py
