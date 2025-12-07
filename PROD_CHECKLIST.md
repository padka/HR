# Production Deployment Checklist

This document provides step-by-step instructions for deploying the RecruitSmart Admin application to production.

## Prerequisites

- **PostgreSQL database server** (version 12.0 or higher - **required**)
- **Redis server** (version 5+ - **required**)
- Python 3.9+
- Telegram Bot Token (from [@BotFather](https://t.me/botfather))
- Dedicated data directory with **write permissions** (outside repository)

## Required Environment Variables

The following environment variables **must** be set for production deployment:

### Core Configuration

```bash
# Environment (must be "production")
export ENVIRONMENT=production

# Database (PostgreSQL only - SQLite is forbidden in production)
export DATABASE_URL=postgresql://user:password@db.example.com:5432/recruitsmart

# Redis (required for caching and notifications)
export REDIS_URL=redis://redis.example.com:6379/0

# Notification broker (must be "redis" in production)
export NOTIFICATION_BROKER=redis

# Data directory (MUST be outside the repository and writable)
# Ensure the directory exists and has proper permissions:
#   sudo mkdir -p /var/lib/recruitsmart_admin
#   sudo chown $USER:$USER /var/lib/recruitsmart_admin
export DATA_DIR=/var/lib/recruitsmart_admin

# Session security (REQUIRED in production - minimum 32 characters)
# MUST be explicitly set (auto-generation is disabled in production)
# Generate a cryptographically random secret:
export SESSION_SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")
# Or use an existing strong secret (minimum 32 characters)
```

### Bot Configuration

```bash
# Telegram Bot Token
export BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz

# Admin credentials for web interface
export ADMIN_USER=admin
export ADMIN_PASSWORD=<strong-password>

# Bot behavior
export BOT_ENABLED=1
export BOT_INTEGRATION_ENABLED=1
export BOT_AUTOSTART=0  # Don't auto-start bot in production (manual control)

# Timezone
export TZ=Europe/Moscow
```

### Optional Configuration

```bash
# Logging
export LOG_LEVEL=INFO
export LOG_JSON=1

# Session cookies (secure by default in production)
export SESSION_COOKIE_SECURE=1
export SESSION_COOKIE_SAMESITE=strict

# Database connection pooling
export DB_POOL_SIZE=20
export DB_MAX_OVERFLOW=10
export DB_POOL_TIMEOUT=30
export DB_POOL_RECYCLE=3600

# Webhook mode (if using webhooks instead of polling)
export BOT_USE_WEBHOOK=0
# export BOT_WEBHOOK_URL=https://example.com/bot/webhook
```

## Deployment Steps

### 1. Prepare Environment

```bash
# Create data directory outside repository
sudo mkdir -p /var/lib/recruitsmart_admin
sudo chown $USER:$USER /var/lib/recruitsmart_admin

# Set all environment variables (see above)
# Recommended: Use a .env file or systemd environment files
cat > /var/lib/recruitsmart_admin/.env <<EOF
ENVIRONMENT=production
DATABASE_URL=postgresql://...
REDIS_URL=redis://...
NOTIFICATION_BROKER=redis
DATA_DIR=/var/lib/recruitsmart_admin
SESSION_SECRET=...
BOT_TOKEN=...
ADMIN_USER=admin
ADMIN_PASSWORD=...
TZ=Europe/Moscow
EOF

# Load environment variables
source /var/lib/recruitsmart_admin/.env
```

### 2. Run Smoke Tests

```bash
# Run pre-deployment smoke tests
./scripts/prod_smoke.sh
```

Expected output:
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✓ ALL CHECKS PASSED - Ready for production deployment
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

If any check fails, fix the issue before proceeding.

### 3. Run Database Migrations

```bash
# Apply database migrations
python3 scripts/run_migrations.py
```

Expected output:
```
============================================================
Database Migration Script
============================================================
Database URL: localhost:5432/recruitsmart
Running migrations...
✓ Migrations completed successfully
============================================================
```

### 4. Start Services

#### Start Admin UI (Web Interface)

```bash
# Using uvicorn (do NOT use --reload in production)
uvicorn backend.apps.admin_api.main:app --host 0.0.0.0 --port 8000 --workers 4
```

Or using a production ASGI server like gunicorn:

```bash
gunicorn backend.apps.admin_api.main:app \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --workers 4 \
  --timeout 120 \
  --access-logfile /var/log/recruitsmart/access.log \
  --error-logfile /var/log/recruitsmart/error.log
```

#### Start Bot

```bash
# Start the Telegram bot
python3 bot.py
```

### 5. Verify Services

#### Health Endpoint Check

The application provides a comprehensive `/health` endpoint that checks all critical components:

```bash
# Check application health
curl http://localhost:8000/health

# Expected response (HTTP 200):
{
  "status": "healthy",
  "timestamp": "2024-12-04T10:30:00Z",
  "components": {
    "application": {"status": "up"},
    "database": {"status": "up", "latency_ms": 5.23},
    "redis": {"status": "up", "latency_ms": 2.14}
  },
  "response_time_ms": 8.45
}
```

**Status Codes**:
- `200 OK` - All components healthy
- `503 Service Unavailable` - One or more components unhealthy

**Use in Monitoring**:
- **Kubernetes liveness probe**: `GET /health`
- **Docker health check**: `curl -f http://localhost:8000/health || exit 1`
- **Load balancer health check**: Configure to check `/health` endpoint
- **Monitoring tools**: Configure alerts on HTTP 503 responses

#### Root Endpoint Check

```bash
curl http://localhost:8000/
# Expected: {"ok": true, "admin": "/admin", "webapp_api": "/api/webapp", "health": "/health"}
```

#### Check Logs

```bash
# Check admin UI logs
tail -f /var/lib/recruitsmart_admin/logs/app.log

# Look for successful startup messages
# ✓ Phase 2 Cache initialized: redis.example.com:6379
# ✓ Notification service started
```

#### Bot Verification

```bash
# Check bot logs for startup
# Expected: BOOT: using bot id=..., username=@...
```

## Business Smoke Testing

After deployment, perform these manual tests to verify functionality:

### 1. Basic Bot Flow

- [ ] Send `/start` to the bot
- [ ] Complete registration (name, city)
- [ ] Complete Test 1 (introductory questions)
- [ ] Receive slot selection for interview
- [ ] Book a slot successfully

### 2. Duplicate Booking Prevention

- [ ] Try to book the same slot twice
- [ ] Verify error message about slot already booked

### 3. Test 2 Flow

- [ ] Complete Test 1
- [ ] Start Test 2 (technical questions)
- [ ] Answer questions (timed)
- [ ] Verify Test 2 results

### 4. Question/Template Updates

- [ ] Edit a test question in admin UI
- [ ] Edit a message template in admin UI
- [ ] Verify changes are visible immediately in bot (no restart needed)

### 5. Missing Question Handling

- [ ] Verify bot doesn't crash when a question ID is missing
- [ ] Check logs for graceful error handling

## Production Monitoring

### Critical Log Patterns to Watch

#### ⚠️ Warnings to Investigate

```
OperationalError: database is locked
```
- **Cause**: SQLite being used (should not happen in production)
- **Action**: Verify DATABASE_URL is PostgreSQL

```
KeyError: 'question_id'
```
- **Cause**: Missing question in database
- **Action**: Add missing questions via admin UI

```
Failed to initialize cache
```
- **Cause**: Redis connection failed
- **Action**: Check Redis server status and REDIS_URL

### Service Health Checks

#### Redis Connectivity

```bash
redis-cli -u "$REDIS_URL" ping
# Expected: PONG
```

#### Database Connectivity

```bash
psql "$DATABASE_URL" -c "SELECT 1;"
# Expected: 1 row returned
```

#### Admin UI Health

```bash
curl -f http://localhost:8000/ || echo "Admin UI down!"
```

## Common Production Issues

### Issue: Production validation errors in development environment

**Symptom**: Application fails to start with "PRODUCTION CONFIGURATION ERRORS" even though you're developing locally.

**Diagnosis**:
```bash
# Check your environment variable
echo $ENVIRONMENT

# Check what settings are being loaded
python3 -c "from backend.core.settings import get_settings; print(get_settings().environment)"
```

**Solution**:

1. **If ENVIRONMENT is set to "production"**, change it:
   ```bash
   export ENVIRONMENT=development
   # OR add to .env file
   echo "ENVIRONMENT=development" >> .env
   ```

2. **If ENVIRONMENT is not set**, the default is "development" and validation should be skipped. Check for:
   - Cached settings (restart Python/server)
   - Environment variables being set elsewhere (`.bashrc`, `.zshrc`, systemd)

3. **Clear any cached settings**:
   ```bash
   # If using Python REPL or imports
   from backend.core.settings import get_settings
   get_settings.cache_clear()
   ```

**Why this happens**:
- Production validation ONLY runs when `ENVIRONMENT=production` (case-insensitive)
- Default is "development" for safety
- Check is case-insensitive: "Production", "PRODUCTION", "production" all trigger validation
- All other values (development, staging, test, etc.) skip validation

**Verification**:
```bash
# This should work without errors in development:
ENVIRONMENT=development python3 -c "from backend.core.settings import get_settings; print('✓ Development mode works')"

# This should fail with validation errors:
ENVIRONMENT=production python3 -c "from backend.core.settings import get_settings" 2>&1 | grep "PRODUCTION CONFIGURATION ERRORS"
```

---

### Issue: "SQLite database is forbidden in production"

**Cause**: DATABASE_URL is not set or points to SQLite

**Fix**:
```bash
export DATABASE_URL=postgresql://user:pass@host:5432/dbname
./scripts/prod_smoke.sh  # Verify fix
```

### Issue: "REDIS_URL must be set in production"

**Cause**: REDIS_URL environment variable is missing

**Fix**:
```bash
export REDIS_URL=redis://localhost:6379/0
./scripts/prod_smoke.sh  # Verify fix
```

### Issue: "DATA_DIR is inside repository"

**Cause**: DATA_DIR points to a location inside the git repository

**Fix**:
```bash
export DATA_DIR=/var/lib/recruitsmart_admin
mkdir -p "$DATA_DIR"
./scripts/prod_smoke.sh  # Verify fix
```

### Issue: "NOTIFICATION_BROKER must be redis"

**Cause**: NOTIFICATION_BROKER is set to "memory" or not set

**Fix**:
```bash
export NOTIFICATION_BROKER=redis
./scripts/prod_smoke.sh  # Verify fix
```

### Issue: Bot not receiving messages

**Causes**:
1. BOT_TOKEN is incorrect or expired
2. Bot is not started
3. Network connectivity issues

**Fix**:
```bash
# Verify bot token
curl "https://api.telegram.org/bot${BOT_TOKEN}/getMe"

# Restart bot
python3 bot.py
```

### Issue: Session not persisting in admin UI

**Causes**:
1. SESSION_SECRET is too weak or not set
2. SESSION_COOKIE_SECURE is True but using HTTP

**Fix**:
```bash
# Generate strong session secret
export SESSION_SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")

# If using HTTP (not recommended in production)
export SESSION_COOKIE_SECURE=0
```

## Rollback Procedure

If issues occur in production:

1. **Stop services immediately**:
   ```bash
   # Stop admin UI (find PID)
   pkill -f "uvicorn.*admin_api"

   # Stop bot
   pkill -f "python.*bot.py"
   ```

2. **Revert to previous deployment** (if using git):
   ```bash
   git checkout <previous-stable-tag>
   python3 scripts/run_migrations.py  # Migrations are idempotent
   ```

3. **Restart services** using known-good configuration

4. **Investigate logs**:
   ```bash
   tail -100 /var/lib/recruitsmart_admin/logs/app.log
   ```

## Security Considerations

- **Never commit** `.env` files or secrets to git
- Use **strong, unique** SESSION_SECRET (minimum 32 characters)
- Use **strong** ADMIN_PASSWORD (avoid default passwords)
- Run services with **non-root user** when possible
- Use **HTTPS** for admin UI (set SESSION_COOKIE_SECURE=1)
- Keep **database credentials** secure (use read-only replicas for analytics if needed)
- Regularly **rotate** SESSION_SECRET and BOT_TOKEN
- Monitor **failed login attempts** in admin UI

## Performance Tuning

### Database Connection Pool

For high-traffic deployments:

```bash
export DB_POOL_SIZE=50
export DB_MAX_OVERFLOW=20
export DB_POOL_TIMEOUT=60
export DB_POOL_RECYCLE=1800
```

### Worker Processes

Scale workers based on CPU cores:

```bash
# Admin UI workers (recommendation: 2 * CPU_CORES + 1)
uvicorn backend.apps.admin_api.main:app --workers 8
```

### Redis Configuration

For better Redis performance:

```redis
# redis.conf
maxmemory 2gb
maxmemory-policy allkeys-lru
save ""  # Disable persistence if using as cache only
```

## Support and Troubleshooting

For issues not covered in this checklist:

1. Check application logs: `/var/lib/recruitsmart_admin/logs/app.log`
2. Check smoke test results: `./scripts/prod_smoke.sh`
3. Run tests: `pytest -v tests/test_prod_*.py`
4. Review recent commits: `git log --oneline -10`

## Changelog

- **2025-12-04**: Added production validation guards, smoke tests, and comprehensive deployment documentation
