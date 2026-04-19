from __future__ import annotations

from pathlib import Path

from backend.core.sqlite_dev_schema import repair_sqlite_schema
from backend.domain import analytics_models as _analytics_models  # noqa: F401
from backend.domain import auth_account as _auth_account  # noqa: F401
from backend.domain import models as _models  # noqa: F401
from backend.domain.ai import models as _ai_models  # noqa: F401
from backend.domain.base import Base
from backend.domain.candidates import models as _candidate_models  # noqa: F401
from backend.domain.hh_integration import models as _hh_models  # noqa: F401
from backend.domain.messaging import models as _messaging_models  # noqa: F401
from backend.domain.tests import models as _test_models  # noqa: F401
from sqlalchemy import create_engine, inspect, text


def test_repair_sqlite_schema_adds_missing_columns(tmp_path: Path):
    db_path = tmp_path / "legacy-dev.db"
    engine = create_engine(f"sqlite:///{db_path}", future=True)
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE cities (id INTEGER PRIMARY KEY, name VARCHAR(120) NOT NULL, tz VARCHAR(64), active BOOLEAN NOT NULL DEFAULT 1, criteria TEXT, experts TEXT, plan_week INTEGER, plan_month INTEGER, responsible_recruiter_id INTEGER)"))
        conn.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY, fio VARCHAR(120), phone VARCHAR(32), city VARCHAR(120), candidate_status VARCHAR(32))"))
        conn.execute(text("CREATE TABLE questions (id INTEGER PRIMARY KEY, test_id INTEGER NOT NULL, text TEXT NOT NULL, \"key\" VARCHAR(120), payload JSON, type VARCHAR(32) NOT NULL, \"order\" INTEGER NOT NULL DEFAULT 0)"))
        conn.execute(text("CREATE TABLE candidate_journey_sessions (id INTEGER PRIMARY KEY, candidate_id INTEGER NOT NULL, journey_key VARCHAR(64) NOT NULL DEFAULT 'candidate_portal', journey_version VARCHAR(32) NOT NULL DEFAULT 'v1', entry_channel VARCHAR(32) NOT NULL DEFAULT 'web', current_step_key VARCHAR(64) NOT NULL DEFAULT 'profile', status VARCHAR(16) NOT NULL DEFAULT 'active', payload_json JSON, session_version INTEGER NOT NULL DEFAULT 1, started_at TIMESTAMP, last_activity_at TIMESTAMP, completed_at TIMESTAMP)"))

    repair_sqlite_schema(engine=engine, metadata=Base.metadata)

    inspector = inspect(engine)
    city_columns = {column["name"] for column in inspector.get_columns("cities")}
    user_columns = {column["name"] for column in inspector.get_columns("users")}
    question_columns = {column["name"] for column in inspector.get_columns("questions")}
    journey_columns = {column["name"] for column in inspector.get_columns("candidate_journey_sessions")}

    assert {"intro_address", "contact_name", "contact_phone"}.issubset(city_columns)
    assert {
        "hh_resume_id",
        "hh_negotiation_id",
        "hh_vacancy_id",
        "hh_synced_at",
        "hh_sync_status",
        "hh_sync_error",
        "messenger_platform",
        "max_user_id",
    }.issubset(user_columns)
    assert {"title", "is_active"}.issubset(question_columns)
    assert {
        "application_id",
        "last_access_session_id",
        "last_surface",
        "last_auth_method",
    }.issubset(journey_columns)
