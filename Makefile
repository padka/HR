.PHONY: help test test-slot-flow test-all docker-up docker-down docker-logs clean install migrate dev

# Python interpreter (use venv if available, otherwise python3)
PYTHON := $(shell if [ -f .venv/bin/python ]; then echo .venv/bin/python; else echo python3; fi)

# Default target
help:
	@echo "Recruitsmart Admin - Available Make targets:"
	@echo ""
	@echo "  make install          - Install Python dependencies"
	@echo "  make migrate          - Run database migrations"
	@echo "  make dev              - Start development server"
	@echo ""
	@echo "  make test             - Run all tests"
	@echo "  make test-slot-flow   - Run slot workflow tests (manual assignment, intro day)"
	@echo "  make test-all         - Run all tests including integration"
	@echo ""
	@echo "  make docker-up        - Start Redis services in background"
	@echo "  make docker-down      - Stop Redis services"
	@echo "  make docker-logs      - Show Redis logs"
	@echo ""
	@echo "  make clean            - Remove temporary files and caches"

# Install dependencies
install:
	$(PYTHON) -m pip install --upgrade pip
	pip install -r requirements-dev.txt

# Run database migrations
migrate:
	ENVIRONMENT=development REDIS_URL="" $(PYTHON) scripts/run_migrations.py

# Start development server
dev:
	ENVIRONMENT=development REDIS_URL="" $(PYTHON) scripts/dev_server.py

# Run all tests (fast)
test:
	ENVIRONMENT=development REDIS_URL="" $(PYTHON) -m pytest tests/ -v --tb=short

# Run slot workflow tests (as specified in ND21.md)
test-slot-flow:
	@echo "Running slot flow tests (manual assignment, intro day, repositories)..."
	ENVIRONMENT=development REDIS_URL="" $(PYTHON) -m pytest \
		tests/test_domain_repositories.py \
		tests/test_manual_slot_assignment.py \
		tests/test_intro_day_flow.py \
		-v --tb=short

# Run all tests including integration (requires Redis)
test-all:
	@echo "Starting Redis services..."
	docker-compose up -d
	@echo "Waiting for Redis to be ready..."
	@sleep 3
	@echo "Running all tests..."
	ENVIRONMENT=development REDIS_URL="redis://localhost:6379/0" $(PYTHON) -m pytest tests/ -v --tb=short
	@echo "Tests complete. Redis services still running (use 'make docker-down' to stop)"

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
