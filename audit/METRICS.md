# Runtime and Bundle Metrics

- Cold start (lifespan) time: 0.001s
- Total FastAPI routes: 57
- SQLAlchemy model count: 16
- Test file count: 32
- main.css size: 39528 bytes; unique selectors: 60
- Tailwind class tokens in templates: 1256 (unique: 386)

## Smoke test summary

### smoke_no_db
- - startup: <lifespan> → EXCEPTION
- detail: OperationalError: (sqlite3.OperationalError) no such table: slot_reminder_jobs

### smoke_with_db
- - dashboard: / → 200
- - recruiters: /recruiters → 200
- - questions: /questions → 200
- - templates: /templates → 200
- - slots: /slots → 200
