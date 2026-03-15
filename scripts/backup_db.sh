#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKUP_DIR="/var/backups/recruitsmart"
BACKUP_PREFIX="db_backup"
MIN_BACKUP_SIZE_BYTES=1024

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

require_command() {
  command -v "$1" >/dev/null 2>&1 || fail "Required command not found: $1"
}

load_env_file() {
  if [[ -f "$PROJECT_ROOT/.env" ]]; then
    set -a
    # shellcheck disable=SC1091
    source "$PROJECT_ROOT/.env"
    set +a
  fi
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

rotate_backups() {
  local keep_count="$1"
  local pattern="$2"
  mapfile -t backups < <(find "$BACKUP_DIR" -maxdepth 1 -type f -name "$pattern" -print | sort -r)
  if (( ${#backups[@]} > keep_count )); then
    for backup in "${backups[@]:keep_count}"; do
      rm -f "$backup"
      log "Removed old backup: $backup"
    done
  fi
}

main() {
  local backup_stamp backup_file backup_size

  cd "$PROJECT_ROOT"

  require_command docker
  docker compose version >/dev/null 2>&1 || fail "docker compose is not available"

  [[ -f docker-compose.yml ]] || fail "docker-compose.yml not found in $PROJECT_ROOT"
  [[ -f .env ]] || fail ".env file is required in $PROJECT_ROOT"

  load_env_file

  docker volume inspect postgres_data >/dev/null 2>&1 || fail "Docker volume 'postgres_data' does not exist"
  verify_postgres_running

  mkdir -p "$BACKUP_DIR"

  backup_stamp="$(date '+%Y%m%d_%H%M%S')"
  backup_file="$BACKUP_DIR/${BACKUP_PREFIX}_${backup_stamp}.dump"

  log "Creating PostgreSQL backup"
  docker compose exec -T postgres pg_dump \
    -U "${POSTGRES_USER:-recruitsmart}" \
    -d "${POSTGRES_DB:-recruitsmart}" \
    --format=custom \
    --file=/tmp/backup.dump

  docker compose exec -T postgres sh -c 'test -s /tmp/backup.dump'
  docker compose cp postgres:/tmp/backup.dump "$backup_file"
  docker compose exec -T postgres rm -f /tmp/backup.dump >/dev/null 2>&1 || true

  [[ -s "$backup_file" ]] || fail "Backup file was not created: $backup_file"
  backup_size="$(stat -c '%s' "$backup_file")"
  (( backup_size >= MIN_BACKUP_SIZE_BYTES )) || fail "Backup file is too small: ${backup_size} bytes"

  rotate_backups 10 "${BACKUP_PREFIX}_*.dump"

  log "Backup created: $backup_file"
  log "Backup size: $(du -h "$backup_file" | awk '{print $1}') (${backup_size} bytes)"
}

main "$@"
