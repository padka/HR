# RecruitSmart Admin — Codex System Document

## Project Overview
RecruitSmart Admin is a recruitment pipeline management system consisting of:
- **FastAPI** backend (admin UI + bot API)
- **React/TypeScript** frontend (SPA)
- **Telegram Bot** (aiogram) for candidate interactions
- **PostgreSQL** database with Alembic migrations
- **Redis** for notifications broker and cache

## Key Architecture Decisions
- Async-first: FastAPI + asyncio + asyncpg
- Unit of Work pattern for transaction management
- Repository pattern for data access
- City-scoped templates and reminder policies
- Vacancy-based question sets for Test1/Test2
- APScheduler for reminder jobs with Redis jobstore

## Branch Strategy
- `main` — production-ready code
- `codex/*` — AI-assisted feature branches
- `feature/*` — manual feature branches
- `testing` — staging integration branch

## Test Command
```bash
make test
cd frontend/app && npm run lint && npm run typecheck && npm run test && npm run test:e2e
```
