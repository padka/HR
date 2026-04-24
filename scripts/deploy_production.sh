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
SERVICE_WAIT_TIMEOUT=60
ROLLBACK_COMMIT=""
CURRENT_COMMIT=""
BACKUP_FILE=""
MIGRATION_STATUS="not-run"
HEALTH_STATUS="pending"
SHOULD_RUN_MIGRATIONS=1

timestamp() {
  date '+%Y-%m-%d %H:%M:%S'
}

log() {
  printf '[%s] %s\n' "$(timestamp)" "$*"
}

step() {
  log "Step $1: $2"
}

fail() {
  log "ERROR: $*"
  exit 1
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || fail "Required command not found: $1"
}

is_truthy() {
  case "$(printf '%s' "${1:-}" | tr '[:upper:]' '[:lower:]')" in
    1|true|yes|on) return 0 ;;
    *) return 1 ;;
  esac
}

is_falsey() {
  case "$(printf '%s' "${1:-}" | tr '[:upper:]' '[:lower:]')" in
    0|false|no|off) return 0 ;;
    *) return 1 ;;
  esac
}

validate_migration_contract() {
  if is_falsey "${RUN_MIGRATIONS:-true}"; then
    is_truthy "${CODE_ONLY_DEPLOY_APPROVED:-false}" || fail \
      "RUN_MIGRATIONS=false requires CODE_ONLY_DEPLOY_APPROVED=true. Use only for approved code-only staging validation."
    SHOULD_RUN_MIGRATIONS=0
    log "Migration runner disabled by RUN_MIGRATIONS=false"
    return
  fi

  is_truthy "${MIGRATION_HISTORY_RECONCILED:-false}" || fail \
    "Migration history is not reconciled. Recover/reconstruct missing 0104/0105 first, or set RUN_MIGRATIONS=false CODE_ONLY_DEPLOY_APPROVED=true for code-only staging validation."
  SHOULD_RUN_MIGRATIONS=1
}

load_env_file() {
  local has_run_migrations="${RUN_MIGRATIONS+x}"
  local run_migrations_value="${RUN_MIGRATIONS:-}"
  local has_code_only_approved="${CODE_ONLY_DEPLOY_APPROVED+x}"
  local code_only_approved_value="${CODE_ONLY_DEPLOY_APPROVED:-}"
  local has_auto_migrate="${AUTO_MIGRATE+x}"
  local auto_migrate_value="${AUTO_MIGRATE:-}"
  local has_history_reconciled="${MIGRATION_HISTORY_RECONCILED+x}"
  local history_reconciled_value="${MIGRATION_HISTORY_RECONCILED:-}"

  set -a
  # shellcheck disable=SC1091
  source "$PROJECT_ROOT/.env"
  set +a

  [[ "$has_run_migrations" == "x" ]] && export RUN_MIGRATIONS="$run_migrations_value"
  [[ "$has_code_only_approved" == "x" ]] && export CODE_ONLY_DEPLOY_APPROVED="$code_only_approved_value"
  [[ "$has_auto_migrate" == "x" ]] && export AUTO_MIGRATE="$auto_migrate_value"
  [[ "$has_history_reconciled" == "x" ]] && export MIGRATION_HISTORY_RECONCILED="$history_reconciled_value"
}

current_branch() {
  git symbolic-ref --quiet --short HEAD 2>/dev/null || true
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

create_backup() {
  local backup_stamp backup_size
  backup_stamp="$(date '+%Y%m%d_%H%M%S')"
  BACKUP_FILE="$BACKUP_DIR/pre_deploy_${backup_stamp}.dump"

  docker compose exec -T postgres pg_dump \
    -U "${POSTGRES_USER:-recruitsmart}" \
    -d "${POSTGRES_DB:-recruitsmart}" \
    --format=custom \
    --file=/tmp/backup.dump

  docker compose exec -T postgres sh -c 'test -s /tmp/backup.dump'
  docker compose cp postgres:/tmp/backup.dump "$BACKUP_FILE"
  docker compose exec -T postgres rm -f /tmp/backup.dump >/dev/null 2>&1 || true

  [[ -s "$BACKUP_FILE" ]] || fail "Backup file was not created: $BACKUP_FILE"
  backup_size="$(stat -c '%s' "$BACKUP_FILE")"
  (( backup_size >= MIN_BACKUP_SIZE_BYTES )) || fail "Backup file is too small: ${backup_size} bytes"

  rotate_backups 5 'pre_deploy_*.dump'

  log "Backup created: $BACKUP_FILE"
  log "Backup size: $(du -h "$BACKUP_FILE" | awk '{print $1}') (${backup_size} bytes)"
}

restore_backup() {
  local source_backup="$1"
  [[ -f "$source_backup" ]] || fail "Backup file not found for restore: $source_backup"

  log "Restoring database from backup: $source_backup"
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

print_rollback_instructions() {
  log "Rollback instructions:"
  log "  git checkout ${ROLLBACK_COMMIT}"
  log "  docker compose build --no-cache"
  log "  docker compose up -d"
  log "  restore backup if needed: ${BACKUP_FILE}"
}

main() {
  local start_epoch log_file branch new_commit wait_elapsed

  start_epoch="$(date +%s)"
  mkdir -p "$LOG_DIR"
  log_file="$LOG_DIR/deploy_$(date '+%Y%m%d_%H%M%S').log"
  exec > >(tee -a "$log_file") 2>&1

  cd "$PROJECT_ROOT"

  step 0 "Pre-flight checks"
  require_command docker
  require_command git
  require_command curl
  require_command python3

  docker compose version >/dev/null 2>&1 || fail "docker compose is not available"
  docker info >/dev/null 2>&1 || fail "Current user cannot access Docker daemon"

  [[ -f docker-compose.yml ]] || fail "docker-compose.yml not found in $PROJECT_ROOT"
  [[ -f .env ]] || fail ".env file is required in $PROJECT_ROOT"

  load_env_file
  validate_migration_contract

  docker volume inspect postgres_data >/dev/null 2>&1 || fail "Docker volume 'postgres_data' does not exist"
  verify_postgres_running

  branch="$(current_branch)"
  if [[ -z "$branch" ]]; then
    branch="${DEPLOY_BRANCH:-main}"
    log "Detached HEAD detected, checking out deployment branch '$branch'"
    git checkout "$branch"
  fi

  CURRENT_COMMIT="$(git rev-parse HEAD)"
  log "Deployment started at: $(timestamp)"
  log "Current branch: $branch"
  log "Current commit: $CURRENT_COMMIT"
  log "Log file: $log_file"

  step 1 "Database backup"
  mkdir -p "$BACKUP_DIR"
  create_backup

  step 2 "Git pull & validate"
  ROLLBACK_COMMIT="$(git rev-parse HEAD)"
  git fetch origin
  if ! git pull --ff-only origin "$branch"; then
    fail "git pull failed; deployment aborted"
  fi
  if git diff --name-only --diff-filter=U | grep -q .; then
    fail "Merge conflicts detected after git pull"
  fi
  new_commit="$(git rev-parse HEAD)"
  log "Updated commit: $new_commit"
  if [[ "$ROLLBACK_COMMIT" == "$new_commit" ]]; then
    log "No new commits to deploy"
  else
    git log --oneline "${ROLLBACK_COMMIT}..${new_commit}"
  fi

  step 3 "Build Docker image"
  if ! docker compose build --no-cache; then
    log "Docker build failed"
    log "Rollback git to previous commit with: git checkout ${ROLLBACK_COMMIT}"
    exit 1
  fi
  docker image inspect recruitsmart-admin:latest >/dev/null 2>&1 || fail "Image recruitsmart-admin:latest was not built"
  log "Docker image verified: recruitsmart-admin:latest"

  step 4 "Stop application services (keep postgres + redis running)"
  docker compose stop admin_ui admin_api bot max_bot || true
  docker compose rm -f admin_ui admin_api bot max_bot migrate || true
  verify_postgres_running

  if (( SHOULD_RUN_MIGRATIONS )); then
    step 5 "Run migrations"
    if docker compose run --rm migrate; then
      MIGRATION_STATUS="success"
      log "Migrations completed successfully"
    else
      MIGRATION_STATUS="failed"
      log "Migration failed; collecting logs and attempting recovery"
      docker compose logs --tail=100 migrate || true
      set +e
      restore_backup "$BACKUP_FILE"
      restore_status=$?
      git checkout "$ROLLBACK_COMMIT"
      git_status=$?
      docker compose build --no-cache
      rebuild_status=$?
      set -e
      log "Restore attempt exit code: $restore_status"
      log "Git rollback exit code: $git_status"
      log "Rollback rebuild exit code: $rebuild_status"
      fail "Migration failed; deployment aborted after restore/rollback attempt"
    fi
  else
    step 5 "Skip migrations"
    MIGRATION_STATUS="skipped"
    log "Migrations skipped for approved code-only validation"
  fi

  step 6 "Start all services"
  if (( SHOULD_RUN_MIGRATIONS )); then
    docker compose up -d
  else
    docker compose up -d postgres redis_notifications redis_cache
    docker compose up -d --no-deps admin_ui admin_api bot
  fi
  wait_elapsed=0
  until (( wait_elapsed >= SERVICE_WAIT_TIMEOUT )); do
    if docker compose ps --services --filter status=running | grep -q '^admin_ui$' \
      && docker compose ps --services --filter status=running | grep -q '^admin_api$' \
      && docker compose ps --services --filter status=running | grep -q '^bot$'; then
      break
    fi
    sleep 5
    wait_elapsed=$((wait_elapsed + 5))
  done
  docker compose ps

  step 7 "Health verification"
  sleep "$STARTUP_WAIT_SECONDS"
  HEALTH_STATUS="failed"
  for attempt in $(seq 1 "$HEALTH_RETRIES"); do
    if health_check_once; then
      HEALTH_STATUS="healthy"
      log "Health checks passed on attempt ${attempt}/${HEALTH_RETRIES}"
      break
    fi
    log "Health check attempt ${attempt}/${HEALTH_RETRIES} failed"
    if (( attempt < HEALTH_RETRIES )); then
      sleep "$HEALTH_RETRY_DELAY"
    fi
  done

  if [[ "$HEALTH_STATUS" != "healthy" ]]; then
    docker compose logs --tail=50 admin_ui admin_api || true
    log "WARNING: health checks failed after ${HEALTH_RETRIES} attempts"
    print_rollback_instructions
    exit 1
  fi

  step 8 "Cleanup"
  docker image prune -f

  log "Deployment summary"
  log "Previous commit: $ROLLBACK_COMMIT"
  log "New commit: $(git rev-parse HEAD)"
  log "Migration status: $MIGRATION_STATUS"
  log "Service health: $HEALTH_STATUS"
  log "Backup file: $BACKUP_FILE"
  log "Total deployment time: $(( $(date +%s) - start_epoch ))s"
  log "URL: https://admin.recruitsmart.ru"
}

main "$@"
