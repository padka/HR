from __future__ import annotations

from backend.domain import models as _models  # noqa: F401
from backend.domain.base import Base
from backend.domain.candidates import models as _candidate_models  # noqa: F401
from backend.domain.messaging import models as _messaging_models  # noqa: F401

EXPECTED_PHASE_A_TABLES = {
    "candidate_channel_identities",
    "requisitions",
    "applications",
    "application_events",
    "interviews",
    "recruiter_tasks",
    "dedup_candidate_pairs",
    "ai_decision_records",
    "candidate_access_tokens",
    "candidate_access_sessions",
    "message_threads",
    "messages",
    "message_deliveries",
    "provider_receipts",
    "candidate_contact_policies",
    "channel_health_registry",
}


def test_phase_a_models_are_registered_in_metadata() -> None:
    table_names = set(Base.metadata.tables)

    assert EXPECTED_PHASE_A_TABLES.issubset(table_names)

    journey_columns = set(Base.metadata.tables["candidate_journey_sessions"].columns.keys())
    assert {
        "application_id",
        "last_access_session_id",
        "last_surface",
        "last_auth_method",
    }.issubset(journey_columns)


def test_phase_a_metadata_contains_key_safe_constraints() -> None:
    application_events = Base.metadata.tables["application_events"]
    access_tokens = Base.metadata.tables["candidate_access_tokens"]
    access_sessions = Base.metadata.tables["candidate_access_sessions"]
    contact_policies = Base.metadata.tables["candidate_contact_policies"]

    application_event_constraints = {
        constraint.name for constraint in application_events.constraints if constraint.name
    }
    access_token_constraints = {
        constraint.name for constraint in access_tokens.constraints if constraint.name
    }
    access_session_constraints = {
        constraint.name for constraint in access_sessions.constraints if constraint.name
    }
    contact_policy_indexes = {index.name for index in contact_policies.indexes}

    assert "uq_application_events_event_id" in application_event_constraints
    assert "uq_candidate_access_tokens_token_id" in access_token_constraints
    assert "uq_candidate_access_tokens_token_hash" in access_token_constraints
    assert "uq_candidate_access_sessions_session_id" in access_session_constraints
    assert "uq_candidate_contact_policies_candidate_purpose" in contact_policy_indexes
    assert "uq_candidate_contact_policies_candidate_application_purpose" in contact_policy_indexes
