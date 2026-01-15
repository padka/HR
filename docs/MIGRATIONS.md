# Database Migrations Guide

## Overview

Database migrations are managed using Alembic and should be run **separately** before starting any application services.

⚠️ **Important:** Migrations are no longer run automatically on application startup. This prevents race conditions in multi-instance deployments and follows production best practices.

---

## Running Migrations

### Local Development

```bash
# Run migrations
python scripts/run_migrations.py

# Or use Python 3 explicitly
python3 scripts/run_migrations.py
```

### Docker/Docker Compose

Add a migration step before starting services:

```yaml
services:
  # Migration job - runs once before other services
  migrate:
    build: .
    command: python scripts/run_migrations.py
    environment:
      DATABASE_URL: postgresql://user:pass@db:5432/dbname
    depends_on:
      - db

  # Application services - start after migrations
  admin_ui:
    build: .
    command: uvicorn backend.apps.admin_ui.app:app --host 0.0.0.0
    depends_on:
      migrate:
        condition: service_completed_successfully
    environment:
      DATABASE_URL: postgresql://user:pass@db:5432/dbname

  bot:
    build: .
    command: python -m backend.apps.bot.app
    depends_on:
      migrate:
        condition: service_completed_successfully
    environment:
      DATABASE_URL: postgresql://user:pass@db:5432/dbname
```

### Kubernetes

Use an init container or a Job:

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: db-migrate
spec:
  template:
    spec:
      containers:
      - name: migrate
        image: your-app:latest
        command: ["python", "scripts/run_migrations.py"]
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: db-credentials
              key: url
      restartPolicy: OnFailure
```

### CI/CD Pipeline

Add a migration step to your pipeline:

```yaml
# GitHub Actions example
jobs:
  migrate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Run migrations
        run: |
          python scripts/run_migrations.py
        env:
          DATABASE_URL: ${{ secrets.DATABASE_URL }}

  deploy:
    needs: migrate
    runs-on: ubuntu-latest
    steps:
      - name: Deploy application
        # ... deployment steps
```

---

## Creating New Migrations

### Auto-generate from model changes

```bash
# After modifying SQLAlchemy models
alembic revision --autogenerate -m "Add new field to User table"
```

### Create empty migration

```bash
alembic revision -m "Custom data migration"
```

### Review and edit

Always review auto-generated migrations before applying:

```bash
# Check the generated migration file in backend/migrations/versions/
cat backend/migrations/versions/XXXX_add_new_field.py
```

---

## Migration Best Practices

### DO ✅

1. **Run migrations before deployment**
   - Migrations should complete before new code is deployed
   - Use health checks to ensure migrations succeeded

2. **Test migrations on staging first**
   - Always test migrations on a copy of production data
   - Verify rollback procedures work

3. **Make migrations backward-compatible**
   - New code should work with old schema temporarily
   - Allows zero-downtime deployments

4. **Use database transactions**
   - Alembic uses transactions by default
   - Failed migrations will rollback automatically

5. **Keep migrations small and focused**
   - One migration per logical change
   - Easier to debug and rollback

### DON'T ❌

1. **Don't run migrations in application startup**
   - Causes race conditions with multiple instances
   - Can lead to deadlocks

2. **Don't modify applied migrations**
   - Creates inconsistent state across environments
   - Use new migrations to fix issues

3. **Don't skip migrations**
   - Always apply migrations in order
   - Skipping can cause data corruption

4. **Don't run migrations manually with SQL**
   - Alembic tracks applied migrations
   - Manual changes break migration history

---

## Troubleshooting

### Migration fails with "table already exists"

This usually means migrations were partially applied:

```bash
# Check current migration version
alembic current

# If needed, stamp to specific version
alembic stamp <revision>
```

### Multiple instances trying to migrate

Use a distributed lock or ensure only one instance runs migrations:

```python
# Example with PostgreSQL advisory lock
from sqlalchemy import text

with engine.begin() as conn:
    # Acquire lock
    conn.execute(text("SELECT pg_advisory_lock(123456)"))
    try:
        # Run migrations
        alembic.command.upgrade(alembic_cfg, "head")
    finally:
        # Release lock
        conn.execute(text("SELECT pg_advisory_unlock(123456)"))
```

### Rollback failed migration

```bash
# Rollback to previous version
alembic downgrade -1

# Or rollback to specific version
alembic downgrade <revision>
```

---

## Migration Script Details

The `scripts/run_migrations.py` script:

- ✅ Loads environment configuration
- ✅ Runs all pending Alembic migrations
- ✅ Provides clear logging output
- ✅ Returns proper exit codes for CI/CD
- ✅ Handles errors gracefully

### Exit Codes

- `0` - Success, all migrations applied
- `1` - Failure, migration error occurred

### Environment Variables

Required:
- `DATABASE_URL` - Database connection string

Optional:
- `SQL_ECHO` - Enable SQL logging (default: false)

---

## Integration with Application Startup

Applications **no longer** run migrations automatically. You will see this comment in the code:

```python
# backend/apps/admin_ui/app.py
@asynccontextmanager
async def lifespan(app: FastAPI):
    # NOTE: Database migrations should be run separately before starting the app
    # Run: python scripts/run_migrations.py
    # ... rest of startup code
```

This ensures:
- ✅ No race conditions in multi-instance deployments
- ✅ Clear separation of concerns
- ✅ Better control over deployment process
- ✅ Proper error handling and monitoring

---

## See Also

- [Alembic Documentation](https://alembic.sqlalchemy.org/)
- [SQLAlchemy Documentation](https://www.sqlalchemy.org/)
- [Zero-Downtime Migrations](https://fly.io/blog/zero-downtime-postgres-migrations/)
