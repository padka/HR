FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

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

COPY . .
COPY --from=frontend-build /build/frontend/dist /app/frontend/dist

CMD ["uvicorn", "backend.apps.admin_ui.app:app", "--host", "0.0.0.0", "--port", "8000"]

FROM base AS dev

COPY requirements-dev.txt .
RUN pip install --no-cache-dir -r requirements-dev.txt

COPY . .

CMD ["uvicorn", "backend.apps.admin_ui.app:app", "--host", "0.0.0.0", "--port", "8000"]
