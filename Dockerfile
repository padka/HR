FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 1000 appgroup \
    && useradd --uid 1000 --gid appgroup --shell /bin/bash --create-home appuser

WORKDIR /app

FROM node:20-alpine AS frontend-build

WORKDIR /build/frontend/app

COPY frontend/app/package.json frontend/app/package-lock.json ./
RUN npm ci

COPY frontend/app ./
RUN npm run build

FROM base AS prod

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=appuser:appgroup . .
COPY --from=frontend-build --chown=appuser:appgroup /build/frontend/dist /app/frontend/dist

# Create data directory with proper permissions
RUN mkdir -p /app/data/logs && chown -R appuser:appgroup /app/data

USER appuser

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/ready || exit 1

CMD ["uvicorn", "backend.apps.admin_ui.app:app", "--host", "0.0.0.0", "--port", "8000"]

FROM base AS dev

COPY requirements-dev.txt .
RUN pip install --no-cache-dir -r requirements-dev.txt

COPY --chown=appuser:appgroup . .

# Create data directory with proper permissions
RUN mkdir -p /app/data/logs && chown -R appuser:appgroup /app/data

USER appuser

CMD ["uvicorn", "backend.apps.admin_ui.app:app", "--host", "0.0.0.0", "--port", "8000"]
