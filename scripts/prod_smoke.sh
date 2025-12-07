#!/usr/bin/env bash
#
# Production Smoke Test Script
#
# This script validates production configuration and runs basic smoke tests
# to ensure the application is properly configured before deployment.
#
# Exit codes:
#   0 - All checks passed
#   1 - One or more checks failed
#
# Usage:
#   ./scripts/prod_smoke.sh
#

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Track overall status
FAIL_COUNT=0
PASS_COUNT=0

# Helper functions
pass() {
    echo -e "${GREEN}✓ PASS${NC}: $1"
    ((PASS_COUNT++))
}

fail() {
    echo -e "${RED}✗ FAIL${NC}: $1"
    ((FAIL_COUNT++))
}

warn() {
    echo -e "${YELLOW}⚠ WARN${NC}: $1"
}

section() {
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "$1"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
}

# Get project root (where this script lives)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

section "Production Smoke Test"
echo "Project root: $PROJECT_ROOT"
echo "Timestamp: $(date '+%Y-%m-%d %H:%M:%S')"

# ============================================================================
# 1. Environment Variable Checks
# ============================================================================
section "1. Checking Environment Variables"

# Check ENVIRONMENT
if [[ "${ENVIRONMENT:-}" == "production" ]]; then
    pass "ENVIRONMENT=production"
else
    fail "ENVIRONMENT must be 'production' (got: '${ENVIRONMENT:-<not set>}')"
fi

# Check DATABASE_URL
if [[ -z "${DATABASE_URL:-}" ]]; then
    fail "DATABASE_URL is not set"
else
    # Check if it's Postgres
    if [[ "${DATABASE_URL}" == *"postgres"* ]] || [[ "${DATABASE_URL}" == *"postgresql"* ]]; then
        # Hide password in output
        DB_DISPLAY=$(echo "$DATABASE_URL" | sed 's|://[^:]*:[^@]*@|://***:***@|')
        pass "DATABASE_URL is PostgreSQL ($DB_DISPLAY)"
    else
        fail "DATABASE_URL must be PostgreSQL (got: ${DATABASE_URL%%://*}://...)"
    fi

    # Check if it's NOT SQLite
    if [[ "${DATABASE_URL}" == *"sqlite"* ]]; then
        fail "DATABASE_URL cannot be SQLite in production"
    fi
fi

# Check REDIS_URL
if [[ -z "${REDIS_URL:-}" ]]; then
    fail "REDIS_URL is not set"
else
    pass "REDIS_URL is set"
fi

# Check NOTIFICATION_BROKER
if [[ "${NOTIFICATION_BROKER:-}" == "redis" ]]; then
    pass "NOTIFICATION_BROKER=redis"
else
    fail "NOTIFICATION_BROKER must be 'redis' (got: '${NOTIFICATION_BROKER:-<not set>}')"
fi

# Check DATA_DIR
if [[ -z "${DATA_DIR:-}" ]]; then
    fail "DATA_DIR is not set"
else
    DATA_DIR_ABS=$(cd "$DATA_DIR" 2>/dev/null && pwd || echo "$DATA_DIR")

    # Check if DATA_DIR exists
    if [[ -d "$DATA_DIR" ]]; then
        pass "DATA_DIR exists: $DATA_DIR_ABS"

        # Check if DATA_DIR is writable
        TEST_FILE="$DATA_DIR/.write_test_$$"
        if touch "$TEST_FILE" 2>/dev/null; then
            rm -f "$TEST_FILE"
            pass "DATA_DIR is writable"
        else
            fail "DATA_DIR exists but is not writable (check permissions)"
        fi
    else
        fail "DATA_DIR does not exist: $DATA_DIR"
    fi

    # Check if DATA_DIR is outside repo
    # Get repo root via git
    if command -v git &> /dev/null; then
        REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || echo "$PROJECT_ROOT")
    else
        REPO_ROOT="$PROJECT_ROOT"
    fi
    REPO_ROOT_ABS=$(cd "$REPO_ROOT" && pwd)

    # Check if DATA_DIR is inside REPO_ROOT
    case "$DATA_DIR_ABS" in
        "$REPO_ROOT_ABS"*)
            fail "DATA_DIR ($DATA_DIR_ABS) is inside repository ($REPO_ROOT_ABS)"
            ;;
        *)
            pass "DATA_DIR is outside repository"
            ;;
    esac
fi

# Check SESSION_SECRET
if [[ -z "${SESSION_SECRET:-}" ]] && [[ -z "${SECRET_KEY:-}" ]]; then
    fail "SESSION_SECRET or SECRET_KEY must be set"
else
    SECRET="${SESSION_SECRET:-${SECRET_KEY:-}}"
    if [[ ${#SECRET} -lt 32 ]]; then
        fail "SESSION_SECRET must be at least 32 characters (current: ${#SECRET})"
    else
        pass "SESSION_SECRET is set and sufficiently long"
    fi
fi

# ============================================================================
# 2. Redis Connectivity (Optional)
# ============================================================================
section "2. Checking Redis Connectivity"

if command -v redis-cli &> /dev/null && [[ -n "${REDIS_URL:-}" ]]; then
    if redis-cli -u "$REDIS_URL" ping &> /dev/null; then
        pass "Redis is reachable and responding to PING"
    else
        warn "Redis is not reachable (redis-cli ping failed). Continuing anyway."
    fi
else
    if [[ -z "${REDIS_URL:-}" ]]; then
        warn "Skipping Redis connectivity check (REDIS_URL not set)"
    else
        warn "Skipping Redis connectivity check (redis-cli not found)"
    fi
fi

# ============================================================================
# 3. Python Environment Check
# ============================================================================
section "3. Checking Python Environment"

# Check if python3 exists
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version)
    pass "Python is available: $PYTHON_VERSION"
else
    fail "python3 command not found"
fi

# Check if we can import backend modules
if python3 -c "import backend.core.settings" 2>/dev/null; then
    pass "Backend modules are importable"
else
    fail "Cannot import backend modules (check Python path and dependencies)"
fi

# ============================================================================
# 4. Settings Validation
# ============================================================================
section "4. Validating Production Settings"

# Try to load settings - this will trigger our production validation
if python3 -c "from backend.core.settings import get_settings; get_settings()" 2>/dev/null; then
    pass "Production settings validation passed"
else
    fail "Production settings validation failed (see error above)"
fi

# ============================================================================
# 5. PostgreSQL Version Check
# ============================================================================
section "5. Checking PostgreSQL Version"

if [[ -n "${DATABASE_URL:-}" ]] && [[ "${DATABASE_URL}" == *"postgres"* ]]; then
    # Try to extract version from PostgreSQL
    PG_VERSION=$(python3 -c "
import sys
import os
try:
    from sqlalchemy import create_engine, text
    # Use sync URL
    db_url = os.getenv('DATABASE_URL', '')
    # Convert async URL to sync if needed
    if '+aiosqlite' in db_url:
        db_url = db_url.replace('+aiosqlite', '')
    elif '+asyncpg' in db_url:
        db_url = db_url.replace('+asyncpg', '')

    engine = create_engine(db_url, pool_pre_ping=True)
    with engine.connect() as conn:
        result = conn.execute(text('SELECT version()')).scalar()
        # Parse version number (e.g., 'PostgreSQL 14.5 on ...' -> '14.5')
        parts = result.split()
        if len(parts) >= 2:
            version = parts[1]
            print(version)
        else:
            print('unknown')
except Exception as e:
    print(f'error: {e}', file=sys.stderr)
    sys.exit(1)
" 2>&1)

    if [[ $? -eq 0 ]] && [[ "$PG_VERSION" != "error:"* ]]; then
        # Parse major version
        MAJOR_VERSION=$(echo "$PG_VERSION" | cut -d. -f1)

        if [[ "$MAJOR_VERSION" =~ ^[0-9]+$ ]] && [[ $MAJOR_VERSION -ge 12 ]]; then
            pass "PostgreSQL $PG_VERSION (supported, minimum 12.0)"
        elif [[ "$MAJOR_VERSION" =~ ^[0-9]+$ ]] && [[ $MAJOR_VERSION -lt 12 ]]; then
            warn "PostgreSQL $PG_VERSION detected. Version 12+ recommended."
        else
            warn "Could not determine PostgreSQL version (got: $PG_VERSION)"
        fi
    else
        warn "Could not check PostgreSQL version (database may not be accessible yet)"
    fi
else
    warn "Skipping PostgreSQL version check (not using PostgreSQL or DATABASE_URL not set)"
fi

# ============================================================================
# 6. Database Migration Check
# ============================================================================
section "6. Running Database Migrations"

if [[ -f "scripts/run_migrations.py" ]]; then
    echo "Running: python3 scripts/run_migrations.py"
    if python3 scripts/run_migrations.py; then
        pass "Database migrations completed successfully"
    else
        fail "Database migrations failed"
    fi
else
    warn "Migration script not found at scripts/run_migrations.py"
fi

# ============================================================================
# Summary
# ============================================================================
section "Summary"

echo "Passed: $PASS_COUNT"
echo "Failed: $FAIL_COUNT"

if [[ $FAIL_COUNT -eq 0 ]]; then
    echo -e "\n${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}✓ ALL CHECKS PASSED - Ready for production deployment${NC}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"
    exit 0
else
    echo -e "\n${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${RED}✗ SMOKE TEST FAILED - Fix errors before deployment${NC}"
    echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"
    exit 1
fi
