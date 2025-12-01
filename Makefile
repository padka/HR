.PHONY: help test test-cov migrate migrate-test docker-up docker-down docker-logs clean install dev dev-sqlite dev-postgres ensure-venv

VENV := .venv
PYTHON := $(VENV)/bin/python

# Default target
help:
	@echo "Recruitsmart Admin - Available Make targets:"
	@echo ""
	@echo "  make install          - Install Python dependencies"
	@echo "  make migrate          - Run database migrations"
	@echo "  make dev              - Start development server"
	@echo ""
	@echo "  make test             - Run all tests"
	@echo "  make test-cov         - Run all tests with coverage"
	@echo "  make migrate-test     - Apply migrations to sqlite test database"
	@echo ""
	@echo "  make docker-up        - Start Redis services in background"
	@echo "  make docker-down      - Stop Redis services"
	@echo "  make docker-logs      - Show Redis logs"
	@echo ""
	@echo "  make clean            - Remove temporary files and caches"

ensure-venv:
	@if [ ! -x "$(PYTHON)" ]; then python3 -m venv $(VENV); fi

# Install dependencies
install: ensure-venv
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -r requirements-dev.txt

# Run database migrations
migrate:
	ENVIRONMENT=development REDIS_URL="" $(PYTHON) scripts/run_migrations.py

migrate-test: ensure-venv
	ENVIRONMENT=test DATABASE_URL="sqlite:///./data/test.db" REDIS_URL="" $(PYTHON) scripts/run_migrations.py

# Start development server
dev:
	ENVIRONMENT=development REDIS_URL="" $(PYTHON) scripts/dev_server.py

dev-sqlite:
	DATABASE_URL="" ENVIRONMENT=development REDIS_URL="" $(PYTHON) scripts/dev_server.py

dev-postgres:
	@echo "Hint: make sure asyncpg is installed (python -m pip install asyncpg) and Postgres is running (docker compose up -d postgres)."
	ENVIRONMENT=development REDIS_URL="" $(PYTHON) scripts/dev_server.py

# Run tests (in-memory Redis, SQLite test DB)
test: ensure-venv
	$(PYTHON) -m pip show pytest >/dev/null 2>&1 || $(PYTHON) -m pip install -r requirements-dev.txt
	DATABASE_URL="sqlite+aiosqlite:///./data/test.db" \
	ENVIRONMENT=test \
	REDIS_URL="" \
	REDIS_NOTIFICATIONS_URL="" \
	NOTIFICATION_BROKER="memory" \
	BOT_ENABLED=0 \
	BOT_INTEGRATION_ENABLED=0 \
	ADMIN_USER=admin \
	ADMIN_PASSWORD=admin \
	SESSION_SECRET="test-session-secret-0123456789abcdef0123456789abcd" \
	$(PYTHON) -m pytest -q --disable-warnings --maxfail=1

# Run tests with coverage
test-cov: ensure-venv
	$(PYTHON) -m pip show pytest >/dev/null 2>&1 || $(PYTHON) -m pip install -r requirements-dev.txt
	DATABASE_URL="sqlite+aiosqlite:///./data/test.db" \
	ENVIRONMENT=test \
	REDIS_URL="" \
	REDIS_NOTIFICATIONS_URL="" \
	NOTIFICATION_BROKER="memory" \
	BOT_ENABLED=0 \
	BOT_INTEGRATION_ENABLED=0 \
	ADMIN_USER=admin \
	ADMIN_PASSWORD=admin \
	SESSION_SECRET="test-session-secret-0123456789abcdef0123456789abcd" \
	$(PYTHON) -m pytest --cov=backend --cov-report=term-missing

# Docker management
docker-up:
	docker-compose up -d
	@echo "Redis services started. Use 'make docker-logs' to view logs."

docker-down:
	docker-compose down

docker-logs:
	docker-compose logs -f

# Clean temporary files
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name "*.pyo" -delete 2>/dev/null || true
	find . -type f -name ".coverage" -delete 2>/dev/null || true
	@echo "Cleaned temporary files and caches."
