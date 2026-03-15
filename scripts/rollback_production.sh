#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG_DIR="/var/log/recruitsmart"
BACKUP_DIR="/var/backups/recruitsmart"
MIN_BACKUP_SIZE_BYTES=1024
HEALTH_RETRIES=3
HEALTH_RETRY_DELAY=5
STARTUP_WAIT_SECONDS=15
SAFETY_BACKUP_FILE=""

timestamp() {
  date '+%Y-%m-%d %H:%M:%S'
}

log() {
  printf '[%s] %s\n' "$(timestamp)" "$*"
}

step() {
  log "$1"
}

fail() {
  log "ERROR: $*"
  exit 1
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || fail "Required command not found: $1"
}

load_env_file() {
  set -a
  # shellcheck disable=SC1091
  source "$PROJECT_ROOT/.env"
  set +a
}

postgres_container_id() {
  docker compose ps -q postgres
}

verify_postgres_running() {
  local container_id state health
  container_id="$(postgres_container_id)"
  [[ -n "$container_id" ]] || fail "Postgres container is not running"

  state="$(docker inspect -f '{{.State.Status}}' "$container_id")"
  [[ "$state" == "running" ]] || fail "Postgres container state is '$state', expected 'running'"

  health="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$container_id")"
  [[ "$health" == "healthy" ]] || fail "Postgres container health is '$health', expected 'healthy'"
}

create_safety_backup() {
  local backup_stamp backup_size
  mkdir -p "$BACKUP_DIR"
  backup_stamp="$(date '+%Y%m%d_%H%M%S')"
  SAFETY_BACKUP_FILE="$BACKUP_DIR/pre_rollback_${backup_stamp}.dump"

  docker compose exec -T postgres pg_dump \
    -U "${POSTGRES_USER:-recruitsmart}" \
    -d "${POSTGRES_DB:-recruitsmart}" \
    --format=custom \
    --file=/tmp/backup.dump

  docker compose exec -T postgres sh -c 'test -s /tmp/backup.dump'
  docker compose cp postgres:/tmp/backup.dump "$SAFETY_BACKUP_FILE"
  docker compose exec -T postgres rm -f /tmp/backup.dump >/dev/null 2>&1 || true

  [[ -s "$SAFETY_BACKUP_FILE" ]] || fail "Safety backup was not created: $SAFETY_BACKUP_FILE"
  backup_size="$(stat -c '%s' "$SAFETY_BACKUP_FILE")"
  (( backup_size >= MIN_BACKUP_SIZE_BYTES )) || fail "Safety backup is too small: ${backup_size} bytes"

  mapfile -t backups < <(find "$BACKUP_DIR" -maxdepth 1 -type f -name 'pre_rollback_*.dump' -print | sort -r)
  if (( ${#backups[@]} > 5 )); then
    for backup in "${backups[@]:5}"; do
      rm -f "$backup"
      log "Removed old rollback backup: $backup"
    done
  fi

  log "Safety backup created: $SAFETY_BACKUP_FILE"
  log "Safety backup size: $(du -h "$SAFETY_BACKUP_FILE" | awk '{print $1}') (${backup_size} bytes)"
}

restore_backup() {
  local source_backup="$1"
  [[ -f "$source_backup" ]] || fail "Backup file not found: $source_backup"
  [[ -s "$source_backup" ]] || fail "Backup file is empty: $source_backup"

  docker compose cp "$source_backup" postgres:/tmp/backup.dump
  docker compose exec -T postgres pg_restore \
    -U "${POSTGRES_USER:-recruitsmart}" \
    -d "${POSTGRES_DB:-recruitsmart}" \
    --clean \
    --if-exists \
    /tmp/backup.dump
  docker compose exec -T postgres rm -f /tmp/backup.dump >/dev/null 2>&1 || true
}

check_service_states() {
  python3 -c 'import json, sys
text = sys.stdin.read().strip()
rows = []
if text:
    for line in text.splitlines():
        item = json.loads(line)
        if isinstance(item, list):
            rows.extend(item)
        else:
            rows.append(item)
bad = []
for row in rows:
    state = str(row.get("State", "")).lower()
    if "restarting" in state or "exited" in state or "dead" in state:
        bad.append(f"{row.get('Service', row.get('Name', 'unknown'))}:{state}")
if bad:
    print("\\n".join(bad))
    sys.exit(1)
sys.exit(0)
' < <(docker compose ps --format json)
}

health_check_once() {
  curl -sf http://localhost:8000/ready >/dev/null 2>&1 || curl -sf http://localhost:8000/health >/dev/null 2>&1
  if curl -sf http://localhost:8100/ >/dev/null 2>&1; then
    log "admin_api health check: OK"
  else
    log "admin_api health check skipped"
  fi
  check_service_states
}

verify_stack_health() {
  local attempt
  sleep "$STARTUP_WAIT_SECONDS"
  for attempt in $(seq 1 "$HEALTH_RETRIES"); do
    if health_check_once; then
      log "Health checks passed on attempt ${attempt}/${HEALTH_RETRIES}"
      return 0
    fi
    log "Health check attempt ${attempt}/${HEALTH_RETRIES} failed"
    if (( attempt < HEALTH_RETRIES )); then
      sleep "$HEALTH_RETRY_DELAY"
    fi
  done
  docker compose logs --tail=50 admin_ui admin_api || true
  return 1
}

restart_stack() {
  docker compose up -d
  docker compose ps
}

main() {
  local start_epoch log_file target_arg target_commit mode current_commit

  start_epoch="$(date +%s)"
  mkdir -p "$LOG_DIR"
  log_file="$LOG_DIR/rollback_$(date '+%Y%m%d_%H%M%S').log"
  exec > >(tee -a "$log_file") 2>&1

  cd "$PROJECT_ROOT"

  step "Pre-flight checks"
  require_command docker
  require_command git
  require_command curl
  require_command python3

  docker compose version >/dev/null 2>&1 || fail "docker compose is not available"
  docker info >/dev/null 2>&1 || fail "Current user cannot access Docker daemon"
  [[ -f docker-compose.yml ]] || fail "docker-compose.yml not found in $PROJECT_ROOT"
  [[ -f .env ]] || fail ".env file is required in $PROJECT_ROOT"

  load_env_file

  docker volume inspect postgres_data >/dev/null 2>&1 || fail "Docker volume 'postgres_data' does not exist"
  verify_postgres_running

  step "Creating safety backup"
  create_safety_backup

  target_arg="${1:-}"
  if [[ -n "$target_arg" && -f "$target_arg" ]]; then
    mode="backup"
    log "Rollback mode: database restore from $target_arg"
  else
    mode="commit"
    target_commit="${target_arg:-HEAD~1}"
    git rev-parse --verify "${target_commit}^{commit}" >/dev/null 2>&1 || fail "Invalid rollback commit: $target_commit"
    current_commit="$(git rev-parse HEAD)"
    log "Rollback mode: git checkout $target_commit"
    log "Current commit before rollback: $current_commit"
  fi

  step "Stopping application services (keeping postgres + redis running)"
  docker compose stop admin_ui admin_api bot max_bot || true
  docker compose rm -f admin_ui admin_api bot max_bot migrate || true
  verify_postgres_running

  if [[ "$mode" == "backup" ]]; then
    step "Restoring database backup"
    restore_backup "$target_arg"
  else
    step "Rolling back git checkout and rebuilding image"
    git checkout "$target_commit"
    docker compose build --no-cache
    docker image inspect recruitsmart-admin:latest >/dev/null 2>&1 || fail "Image recruitsmart-admin:latest was not built"
  fi

  step "Starting stack"
  restart_stack

  step "Health verification"
  if ! verify_stack_health; then
    fail "Rollback completed but health verification failed"
  fi

  log "Rollback summary"
  log "Mode: $mode"
  if [[ "$mode" == "backup" ]]; then
    log "Restored backup: $target_arg"
  else
    log "Active commit: $(git rev-parse HEAD)"
  fi
  log "Safety backup: $SAFETY_BACKUP_FILE"
  log "Total rollback time: $(( $(date +%s) - start_epoch ))s"
  log "URL: https://admin.recruitsmart.ru"
}

main "$@"
