#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

ENV_FILE=".env.local"
if [ ! -f "$ENV_FILE" ]; then
  ENV_FILE=".env.local.example"
fi

load_env_file() {
  set -a
  # shellcheck disable=SC1090
  source "$1"
  set +a
}

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "error: required command not found: $1" >&2
    exit 1
  fi
}

is_port_listening() {
  python3 - "$1" <<'PY'
import socket, sys
port = int(sys.argv[1])
sock = socket.socket()
sock.settimeout(0.5)
try:
    sock.connect(("127.0.0.1", port))
except OSError:
    print("0")
else:
    print("1")
finally:
    sock.close()
PY
}

wait_for_http() {
  local url="$1"
  local label="$2"
  local attempts="${3:-60}"
  local delay="${4:-1}"
  local i
  for ((i=1; i<=attempts; i++)); do
    if curl -fsS "$url" >/dev/null 2>&1; then
      return 0
    fi
    sleep "$delay"
  done
  echo "error: $label did not become ready: $url" >&2
  return 1
}

extract_trycloudflare_url() {
  local logfile="$1"
  grep -Eo 'https://[-a-z0-9]+\.trycloudflare\.com' "$logfile" 2>/dev/null | head -n 1 || true
}

start_quick_tunnel() {
  local name="$1"
  local target_url="$2"
  local logfile="$TMP_DIR/${name}.log"
  cloudflared tunnel --url "$target_url" --no-autoupdate >"$logfile" 2>&1 &
  local pid=$!
  local url=""
  local i
  for ((i=1; i<=45; i++)); do
    url="$(extract_trycloudflare_url "$logfile")"
    if [ -n "$url" ]; then
      echo "$pid|$url|$logfile"
      return 0
    fi
    if ! kill -0 "$pid" >/dev/null 2>&1; then
      break
    fi
    sleep 1
  done
  echo "error: failed to establish ${name} quick tunnel" >&2
  [ -f "$logfile" ] && tail -n 20 "$logfile" >&2 || true
  return 1
}

resolve_max_link_base() {
  if [ -n "${MAX_BOT_LINK_BASE:-}" ]; then
    printf '%s\n' "${MAX_BOT_LINK_BASE%/}"
    return 0
  fi

  python3 - <<'PY'
import json
import os
import re
import sys
import urllib.error
import urllib.request

token = os.getenv("MAX_BOT_TOKEN", "").strip()
if not token:
    print("error: MAX_BOT_TOKEN is missing", file=sys.stderr)
    sys.exit(1)

req = urllib.request.Request(
    "https://platform-api.max.ru/me",
    headers={
        "Accept": "application/json",
        "Authorization": token,
    },
)

def extract_link(payload: dict) -> str | None:
    profile = payload.get("user") if isinstance(payload.get("user"), dict) else payload
    for key in ("link", "url", "public_url"):
        value = str(profile.get(key) or "").strip().rstrip("/")
        if value.startswith("https://"):
            return value
    for key in ("username", "slug", "handle", "public_name", "login"):
        value = str(profile.get(key) or "").strip().lstrip("@")
        if re.fullmatch(r"[A-Za-z0-9._-]{1,120}", value):
            return f"https://max.ru/{value}"
    for key in ("user_id", "id", "uid"):
        value = str(profile.get(key) or "").strip()
        digits = "".join(ch for ch in value if ch.isdigit())
        if digits:
            return f"https://max.ru/id{digits}_bot"
    return None

try:
    with urllib.request.urlopen(req, timeout=15) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
except urllib.error.HTTPError as exc:
    body = exc.read().decode("utf-8", errors="replace")
    print(f"error: MAX /me failed with HTTP {exc.code}: {body}", file=sys.stderr)
    sys.exit(1)
except Exception as exc:
    print(f"error: MAX /me request failed: {exc}", file=sys.stderr)
    sys.exit(1)

link = extract_link(payload)
if not link:
    print("error: MAX /me did not expose a resolvable public bot link", file=sys.stderr)
    sys.exit(1)
print(link)
PY
}

start_service() {
  local name="$1"
  local port="$2"
  local logfile="$TMP_DIR/${name}.service.log"
  shift 2
  "$@" >"$logfile" 2>&1 &
  local pid=$!
  echo "$pid|$logfile"
}

cleanup() {
  local pid
  for pid in "${MAX_PID:-}" "${ADMIN_PID:-}" "${MAX_TUNNEL_PID:-}" "${ADMIN_TUNNEL_PID:-}"; do
    if [ -n "${pid:-}" ] && kill -0 "$pid" >/dev/null 2>&1; then
      kill "$pid" >/dev/null 2>&1 || true
    fi
  done
  wait >/dev/null 2>&1 || true
  [ -n "${TMP_DIR:-}" ] && rm -rf "$TMP_DIR"
}

trap cleanup EXIT INT TERM

require_cmd cloudflared
require_cmd curl
require_cmd python3

load_env_file "$ENV_FILE"
export ENVIRONMENT="${ENVIRONMENT:-development}"
ADMIN_PORT="${DEV_MAX_LIVE_ADMIN_PORT:-8000}"
MAX_PORT="${DEV_MAX_LIVE_MAX_PORT:-8010}"

if [ -d ".venv" ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

if [ "${MAX_BOT_ENABLED:-}" != "1" ] && [ "${MAX_BOT_ENABLED:-}" != "true" ] && [ "${MAX_BOT_ENABLED:-}" != "TRUE" ]; then
  echo "error: MAX_BOT_ENABLED must be true/1 for live MAX bootstrap" >&2
  exit 1
fi
if [ -z "${MAX_BOT_TOKEN:-}" ]; then
  echo "error: MAX_BOT_TOKEN is required for live MAX bootstrap" >&2
  exit 1
fi
if [ "$(is_port_listening "$ADMIN_PORT")" = "1" ]; then
  echo "error: port $ADMIN_PORT is already in use; stop the existing admin service first or set DEV_MAX_LIVE_ADMIN_PORT" >&2
  exit 1
fi
if [ "$(is_port_listening "$MAX_PORT")" = "1" ]; then
  echo "error: port $MAX_PORT is already in use; stop the existing MAX bot service first or set DEV_MAX_LIVE_MAX_PORT" >&2
  exit 1
fi

TMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/attila-max-live.XXXXXX")"

echo "Using env file: $ENV_FILE"
echo "Using local ports: admin=$ADMIN_PORT max=$MAX_PORT"
echo "Resolving MAX bot public link..."
RESOLVED_MAX_BOT_LINK_BASE="$(resolve_max_link_base)"
if [ -z "$RESOLVED_MAX_BOT_LINK_BASE" ]; then
  echo "error: could not resolve MAX bot public link base" >&2
  exit 1
fi
echo "Resolved MAX bot link: $RESOLVED_MAX_BOT_LINK_BASE"

echo "Opening public HTTPS tunnels..."
IFS='|' read -r ADMIN_TUNNEL_PID ADMIN_PUBLIC_URL ADMIN_TUNNEL_LOG <<<"$(start_quick_tunnel admin http://127.0.0.1:$ADMIN_PORT)"
IFS='|' read -r MAX_TUNNEL_PID MAX_PUBLIC_BASE MAX_TUNNEL_LOG <<<"$(start_quick_tunnel max http://127.0.0.1:$MAX_PORT)"
MAX_WEBHOOK_PUBLIC_URL="${MAX_PUBLIC_BASE%/}/webhook"

echo "Running migrations..."
python3 scripts/run_migrations.py

export CRM_PUBLIC_URL="$ADMIN_PUBLIC_URL"
export CANDIDATE_PORTAL_PUBLIC_URL="$ADMIN_PUBLIC_URL"
export MAX_WEBHOOK_URL="$MAX_WEBHOOK_PUBLIC_URL"
export MAX_BOT_LINK_BASE="$RESOLVED_MAX_BOT_LINK_BASE"

echo "Starting admin UI with public candidate portal URL..."
IFS='|' read -r ADMIN_PID ADMIN_LOG <<<"$(start_service admin "$ADMIN_PORT" uvicorn backend.apps.admin_ui.app:create_app --factory --host 0.0.0.0 --port "$ADMIN_PORT")"
wait_for_http "http://127.0.0.1:$ADMIN_PORT/health" "admin UI"

echo "Starting MAX bot webhook service..."
IFS='|' read -r MAX_PID MAX_LOG <<<"$(start_service max "$MAX_PORT" uvicorn backend.apps.max_bot.app:create_app --factory --host 0.0.0.0 --port "$MAX_PORT")"
wait_for_http "http://127.0.0.1:$MAX_PORT/health" "MAX bot"

echo ""
echo "Attila Recruiting live-local MAX bootstrap is ready."
echo "Admin UI        : $ADMIN_PUBLIC_URL/app"
echo "Admin login     : $ADMIN_PUBLIC_URL/app/login"
echo "Admin health    : $ADMIN_PUBLIC_URL/health"
echo "Candidate portal: $ADMIN_PUBLIC_URL/candidate/start"
echo "MAX webhook     : $MAX_WEBHOOK_PUBLIC_URL"
echo "MAX link base   : $MAX_BOT_LINK_BASE"
echo ""
echo "Local URLs:"
echo "  http://127.0.0.1:$ADMIN_PORT/app"
echo "  http://127.0.0.1:$MAX_PORT/health"
echo ""
echo "Logs:"
echo "  admin service : $ADMIN_LOG"
echo "  max service   : $MAX_LOG"
echo "  admin tunnel  : $ADMIN_TUNNEL_LOG"
echo "  max tunnel    : $MAX_TUNNEL_LOG"
echo ""
echo "Next checks:"
echo "  1. Open $ADMIN_PUBLIC_URL/app/login"
echo "  2. Check /api/system/messenger-health in the admin UI"
echo "  3. Reissue MAX link for a candidate and open the bot in MAX"

while true; do
  if ! kill -0 "$ADMIN_PID" >/dev/null 2>&1; then
    echo "error: admin UI process exited unexpectedly" >&2
    exit 1
  fi
  if ! kill -0 "$MAX_PID" >/dev/null 2>&1; then
    echo "error: MAX bot process exited unexpectedly" >&2
    exit 1
  fi
  if ! kill -0 "$ADMIN_TUNNEL_PID" >/dev/null 2>&1; then
    echo "error: admin tunnel exited unexpectedly" >&2
    exit 1
  fi
  if ! kill -0 "$MAX_TUNNEL_PID" >/dev/null 2>&1; then
    echo "error: MAX tunnel exited unexpectedly" >&2
    exit 1
  fi
  sleep 3
done
