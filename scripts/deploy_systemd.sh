#!/usr/bin/env bash

set -euo pipefail

TARGET_REF="${1:-rc/hardening-candidate-scale-20260425-20}"
TARGET_SHA="${TARGET_SHA:-71c9ab387039b51e4384fee9290de50b041b69e5}"
ORIGIN_URL="${ORIGIN_URL:-https://github.com/padka/HR.git}"
ADMIN_DIR="${ADMIN_DIR:-/opt/recruitsmart_admin}"
MAXPILOT_DIR="${MAXPILOT_DIR:-/opt/recruitsmart_maxpilot}"
VENV_DIR="${VENV_DIR:-/opt/recruitsmart_admin/.venv}"
ADMIN_ENV_FILE="${ADMIN_ENV_FILE:-/opt/recruitsmart_admin/.env.prod}"
SERVICES=(
  recruitsmart-maxpilot-admin-api
  recruitsmart-admin
  recruitsmart-bot
)

timestamp() {
  date '+%Y-%m-%d %H:%M:%S'
}

log() {
  printf '[%s] %s\n' "$(timestamp)" "$*"
}

fail() {
  log "ERROR: $*"
  exit 1
}

require_file() {
  [[ -f "$1" ]] || fail "Required file not found: $1"
}

checkout_ref() {
  local dir="$1"
  log "Checking out ${TARGET_REF} in ${dir}"
  cd "$dir"
  git remote set-url origin "$ORIGIN_URL"
  git fetch --tags origin
  git rev-parse --verify "${TARGET_SHA}^{commit}" >/dev/null
  git reset --hard "$TARGET_SHA"
  local head
  head="$(git rev-parse HEAD)"
  [[ "$head" == "$TARGET_SHA" ]] || fail "${dir} resolved to ${head}, expected ${TARGET_SHA}"
  if [[ -n "$(git diff --name-only)" ]]; then
    git diff --name-only
    fail "${dir} has tracked file drift after reset"
  fi
}

run_migrations() {
  log "Running explicit schema migration"
  cd "$ADMIN_DIR"
  set -a
  # shellcheck disable=SC1090
  source "$ADMIN_ENV_FILE"
  set +a
  export ENVIRONMENT=production
  export AUTO_MIGRATE=false
  export MIGRATION_HISTORY_RECONCILED=true
  export RUN_MIGRATIONS=true
  if [[ -f alembic.ini ]]; then
    "$VENV_DIR/bin/alembic" upgrade head
  else
    "$VENV_DIR/bin/python" scripts/run_migrations.py
  fi
}

main() {
  [[ "$(id -u)" -eq 0 ]] || fail "Run as root on the production VPS"
  command -v git >/dev/null || fail "git is required"
  command -v systemctl >/dev/null || fail "systemctl is required"
  require_file "$ADMIN_ENV_FILE"
  require_file "$ADMIN_DIR/requirements.txt"
  require_file "$VENV_DIR/bin/python"
  require_file "$VENV_DIR/bin/pip"

  checkout_ref "$ADMIN_DIR"
  checkout_ref "$MAXPILOT_DIR"

  log "Installing Python dependencies"
  "$VENV_DIR/bin/pip" install -r "$ADMIN_DIR/requirements.txt"

  run_migrations

  log "Restarting systemd services"
  systemctl restart "${SERVICES[@]}"

  log "Verifying service status"
  for service in "${SERVICES[@]}"; do
    systemctl is-active --quiet "$service" || {
      systemctl status "$service" --no-pager || true
      fail "Service is not active: $service"
    }
    log "Service active: $service"
  done

  log "Deployment complete for ${TARGET_SHA}"
}

main "$@"
