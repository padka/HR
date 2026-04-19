"""Add Phase A additive schema foundation tables.

This migration is intentionally additive-only:
- it creates the new target schema tables from RFC-007;
- it adds nullable bridge columns to candidate_journey_sessions;
- it does not backfill data;
- it does not drop or rewrite any legacy tables.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.engine import Connection

from backend.migrations.utils import column_exists, index_exists, table_exists

revision = "0102_phase_a_schema_foundation"
down_revision = "0101_add_hh_outbound_job_fields"
branch_labels = None
depends_on = None


def _register_reference_tables(metadata: sa.MetaData) -> None:
    # Register existing parent tables in this metadata so SQLAlchemy can resolve
    # foreign keys for the new Phase A tables without trying to create the legacy
    # tables themselves.
    for table_name in (
        "users",
        "recruiters",
        "vacancies",
        "cities",
        "slot_assignments",
        "ai_request_logs",
        "ai_outputs",
        "candidate_journey_sessions",
    ):
        sa.Table(
            table_name,
            metadata,
            sa.Column("id", sa.Integer()),
            extend_existing=True,
        )


def _build_tables(metadata: sa.MetaData) -> list[sa.Table]:
    _register_reference_tables(metadata)

    candidate_channel_identities = sa.Table(
        "candidate_channel_identities",
        metadata,
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("candidate_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("channel", sa.String(length=32), nullable=False),
        sa.Column("external_user_id", sa.String(length=128), nullable=True),
        sa.Column("username_or_handle", sa.String(length=255), nullable=True),
        sa.Column("is_primary", sa.Boolean(), nullable=False),
        sa.Column("linked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verification_status", sa.String(length=24), nullable=True),
        sa.Column("reachability_status", sa.String(length=24), nullable=True),
        sa.Column("delivery_health", sa.String(length=24), nullable=True),
        sa.Column("last_successful_delivery_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_failed_delivery_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_hard_fail_code", sa.String(length=64), nullable=True),
        sa.Column("consent_status", sa.String(length=24), nullable=True),
        sa.Column("serviceability_status", sa.String(length=24), nullable=True),
        sa.Column("cooldown_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Index("ix_candidate_channel_identities_candidate_channel", "candidate_id", "channel"),
        sa.Index("ix_candidate_channel_identities_channel_external_user_id", "channel", "external_user_id"),
        sa.Index("ix_candidate_identity_delivery_updated", "candidate_id", "delivery_health", "updated_at"),
        sa.Index("ix_candidate_identity_reachability_updated", "candidate_id", "reachability_status", "updated_at"),
        sa.Index(
            "uq_candidate_channel_identities_primary",
            "candidate_id",
            "channel",
            unique=True,
            sqlite_where=sa.text("is_primary = 1"),
            postgresql_where=sa.text("is_primary IS TRUE"),
        ),
    )

    requisitions = sa.Table(
        "requisitions",
        metadata,
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("vacancy_id", sa.Integer(), sa.ForeignKey("vacancies.id"), nullable=True),
        sa.Column("city_id", sa.Integer(), sa.ForeignKey("cities.id"), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("headcount", sa.Integer(), nullable=False),
        sa.Column("priority", sa.String(length=16), nullable=False),
        sa.Column("owner_type", sa.String(length=32), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sla_config_json", sa.JSON(), nullable=True),
        sa.Column("source_plan_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Index("ix_requisitions_status_owner", "status", "owner_type", "owner_id"),
        sa.Index("ix_requisitions_vacancy_status", "vacancy_id", "status"),
        sa.Index("ix_requisitions_city_status", "city_id", "status"),
        sa.Index("ix_requisitions_opened_at", sa.text("opened_at DESC")),
    )

    applications = sa.Table(
        "applications",
        metadata,
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("candidate_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("requisition_id", sa.BigInteger(), sa.ForeignKey("requisitions.id"), nullable=True),
        sa.Column("vacancy_id", sa.Integer(), sa.ForeignKey("vacancies.id"), nullable=True),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("source_detail", sa.String(length=255), nullable=True),
        sa.Column("recruiter_id", sa.Integer(), sa.ForeignKey("recruiters.id"), nullable=True),
        sa.Column("lifecycle_status", sa.String(length=32), nullable=False),
        sa.Column("lifecycle_reason", sa.Text(), nullable=True),
        sa.Column("final_outcome", sa.String(length=32), nullable=True),
        sa.Column("final_outcome_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Index("ix_applications_candidate_created", "candidate_id", "created_at"),
        sa.Index("ix_applications_requisition_status", "requisition_id", "lifecycle_status"),
        sa.Index("ix_applications_recruiter_status", "recruiter_id", "lifecycle_status"),
        sa.Index("ix_applications_vacancy_status", "vacancy_id", "lifecycle_status"),
    )

    application_events = sa.Table(
        "application_events",
        metadata,
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("event_id", sa.String(length=36), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor_type", sa.String(length=16), nullable=False),
        sa.Column("actor_id", sa.String(length=64), nullable=True),
        sa.Column("candidate_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("application_id", sa.BigInteger(), sa.ForeignKey("applications.id"), nullable=True),
        sa.Column("requisition_id", sa.BigInteger(), sa.ForeignKey("requisitions.id"), nullable=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("status_from", sa.String(length=32), nullable=True),
        sa.Column("status_to", sa.String(length=32), nullable=True),
        sa.Column("source", sa.String(length=32), nullable=True),
        sa.Column("channel", sa.String(length=32), nullable=True),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("correlation_id", sa.String(length=64), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("event_id", name="uq_application_events_event_id"),
        sa.Index("ix_application_events_candidate_occurred", "candidate_id", sa.text("occurred_at DESC")),
        sa.Index("ix_application_events_application_occurred", "application_id", sa.text("occurred_at DESC")),
        sa.Index("ix_application_events_requisition_occurred", "requisition_id", sa.text("occurred_at DESC")),
        sa.Index("ix_application_events_type_occurred", "event_type", sa.text("occurred_at DESC")),
        sa.Index("ix_application_events_correlation_id", "correlation_id"),
    )

    interviews = sa.Table(
        "interviews",
        metadata,
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("application_id", sa.BigInteger(), sa.ForeignKey("applications.id"), nullable=False),
        sa.Column("slot_assignment_id", sa.Integer(), sa.ForeignKey("slot_assignments.id"), nullable=True),
        sa.Column("kind", sa.String(length=24), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("no_show_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("result", sa.String(length=32), nullable=True),
        sa.Column("result_reason", sa.Text(), nullable=True),
        sa.Column("interviewer_id", sa.Integer(), sa.ForeignKey("recruiters.id"), nullable=True),
        sa.Column("feedback_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Index("ix_interviews_application_status", "application_id", "status"),
        sa.Index("ix_interviews_slot_assignment", "slot_assignment_id"),
        sa.Index("ix_interviews_scheduled_at", "scheduled_at"),
    )

    recruiter_tasks = sa.Table(
        "recruiter_tasks",
        metadata,
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("application_id", sa.BigInteger(), sa.ForeignKey("applications.id"), nullable=True),
        sa.Column("candidate_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("owner_recruiter_id", sa.Integer(), sa.ForeignKey("recruiters.id"), nullable=False),
        sa.Column("task_type", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sla_breached_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "origin_event_id",
            sa.String(length=36),
            sa.ForeignKey("application_events.event_id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("payload_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Index("ix_recruiter_tasks_owner_status_due", "owner_recruiter_id", "status", "due_at"),
        sa.Index("ix_recruiter_tasks_application_status", "application_id", "status"),
        sa.Index("ix_recruiter_tasks_candidate_status", "candidate_id", "status"),
    )

    dedup_candidate_pairs = sa.Table(
        "dedup_candidate_pairs",
        metadata,
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("candidate_a_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("candidate_b_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("match_score", sa.Numeric(5, 4), nullable=False),
        sa.Column("match_reasons_json", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("decided_by", sa.String(length=64), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.CheckConstraint("candidate_a_id < candidate_b_id", name="ck_dedup_candidate_pairs_order"),
        sa.UniqueConstraint(
            "candidate_a_id",
            "candidate_b_id",
            name="uq_dedup_candidate_pairs_normalized_pair",
        ),
        sa.Index("ix_dedup_candidate_pairs_status_created", "status", sa.text("created_at DESC")),
    )

    ai_decision_records = sa.Table(
        "ai_decision_records",
        metadata,
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("ai_request_log_id", sa.Integer(), sa.ForeignKey("ai_request_logs.id"), nullable=True),
        sa.Column("ai_output_id", sa.Integer(), sa.ForeignKey("ai_outputs.id"), nullable=True),
        sa.Column("candidate_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("application_id", sa.BigInteger(), sa.ForeignKey("applications.id"), nullable=True),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("recommendation_json", sa.JSON(), nullable=False),
        sa.Column("human_action", sa.String(length=16), nullable=False),
        sa.Column(
            "final_action_event_id",
            sa.String(length=36),
            sa.ForeignKey("application_events.event_id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Index("ix_ai_decision_records_candidate_created", "candidate_id", "created_at"),
        sa.Index("ix_ai_decision_records_application_kind_created", "application_id", "kind", "created_at"),
        sa.Index("ix_ai_decision_records_human_action_created", "human_action", "created_at"),
    )

    candidate_access_tokens = sa.Table(
        "candidate_access_tokens",
        metadata,
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("token_id", sa.String(length=36), nullable=False),
        sa.Column("token_hash", sa.String(length=128), nullable=False),
        sa.Column("candidate_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("application_id", sa.BigInteger(), sa.ForeignKey("applications.id"), nullable=True),
        sa.Column("journey_session_id", sa.Integer(), sa.ForeignKey("candidate_journey_sessions.id"), nullable=True),
        sa.Column("token_kind", sa.String(length=24), nullable=False),
        sa.Column("journey_surface", sa.String(length=24), nullable=False),
        sa.Column("auth_method", sa.String(length=24), nullable=False),
        sa.Column("launch_channel", sa.String(length=16), nullable=False),
        sa.Column("launch_payload_json", sa.JSON(), nullable=True),
        sa.Column("start_param", sa.String(length=512), nullable=True),
        sa.Column("provider_user_id", sa.String(length=64), nullable=True),
        sa.Column("provider_chat_id", sa.String(length=64), nullable=True),
        sa.Column("session_version_snapshot", sa.Integer(), nullable=True),
        sa.Column("phone_verification_state", sa.String(length=24), nullable=True),
        sa.Column("phone_delivery_channel", sa.String(length=16), nullable=True),
        sa.Column("secret_hash", sa.String(length=128), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("correlation_id", sa.String(length=64), nullable=True),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("issued_by_type", sa.String(length=32), nullable=True),
        sa.Column("issued_by_id", sa.String(length=64), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.UniqueConstraint("token_id", name="uq_candidate_access_tokens_token_id"),
        sa.UniqueConstraint("token_hash", name="uq_candidate_access_tokens_token_hash"),
        sa.Index("ix_candidate_access_tokens_candidate_token_kind_expires", "candidate_id", "token_kind", "expires_at"),
        sa.Index("ix_candidate_access_tokens_application_token_kind_expires", "application_id", "token_kind", "expires_at"),
        sa.Index("ix_candidate_access_tokens_journey_session_token_kind", "journey_session_id", "token_kind"),
        sa.Index("ix_candidate_access_tokens_launch_channel_auth_created", "launch_channel", "auth_method", "created_at"),
        sa.Index(
            "uq_candidate_access_tokens_start_param",
            "start_param",
            unique=True,
            sqlite_where=sa.text("start_param IS NOT NULL"),
            postgresql_where=sa.text("start_param IS NOT NULL"),
        ),
    )

    candidate_access_sessions = sa.Table(
        "candidate_access_sessions",
        metadata,
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("candidate_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("application_id", sa.BigInteger(), sa.ForeignKey("applications.id"), nullable=True),
        sa.Column("journey_session_id", sa.Integer(), sa.ForeignKey("candidate_journey_sessions.id"), nullable=False),
        sa.Column("origin_token_id", sa.BigInteger(), sa.ForeignKey("candidate_access_tokens.id"), nullable=True),
        sa.Column("journey_surface", sa.String(length=24), nullable=False),
        sa.Column("auth_method", sa.String(length=24), nullable=False),
        sa.Column("launch_channel", sa.String(length=16), nullable=False),
        sa.Column("provider_session_id", sa.String(length=128), nullable=True),
        sa.Column("provider_user_id", sa.String(length=64), nullable=True),
        sa.Column("session_version_snapshot", sa.Integer(), nullable=False),
        sa.Column("phone_verification_state", sa.String(length=24), nullable=True),
        sa.Column("phone_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("phone_delivery_channel", sa.String(length=16), nullable=True),
        sa.Column("csrf_nonce", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("refreshed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("correlation_id", sa.String(length=64), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.UniqueConstraint("session_id", name="uq_candidate_access_sessions_session_id"),
        sa.Index("ix_candidate_access_sessions_candidate_status_expires", "candidate_id", "status", "expires_at"),
        sa.Index("ix_candidate_access_sessions_application_status_expires", "application_id", "status", "expires_at"),
        sa.Index("ix_candidate_access_sessions_journey_status", "journey_session_id", "status"),
        sa.Index("ix_candidate_access_sessions_provider_surface_issued", "provider_user_id", "journey_surface", "issued_at"),
    )

    message_threads = sa.Table(
        "message_threads",
        metadata,
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("thread_uuid", sa.String(length=36), nullable=False),
        sa.Column("candidate_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("application_id", sa.BigInteger(), sa.ForeignKey("applications.id"), nullable=True),
        sa.Column("requisition_id", sa.BigInteger(), sa.ForeignKey("requisitions.id"), nullable=True),
        sa.Column("thread_kind", sa.String(length=32), nullable=False),
        sa.Column("purpose_scope", sa.String(length=32), nullable=False),
        sa.Column("source_entity_type", sa.String(length=32), nullable=True),
        sa.Column("source_entity_id", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("current_primary_channel", sa.String(length=32), nullable=True),
        sa.Column("last_inbound_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_outbound_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "last_message_id",
            sa.BigInteger(),
            sa.ForeignKey(
                "messages.id",
                use_alter=True,
                name="fk_message_threads_last_message_id",
                ondelete="SET NULL",
            ),
            nullable=True,
        ),
        sa.Column("thread_context_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Index("ix_message_threads_candidate_updated", "candidate_id", "updated_at"),
        sa.Index("ix_message_threads_application_updated", "application_id", "updated_at"),
        sa.Index("ix_message_threads_status_updated", "status", "updated_at"),
    )

    messages = sa.Table(
        "messages",
        metadata,
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("message_uuid", sa.String(length=36), nullable=False),
        sa.Column("thread_id", sa.BigInteger(), sa.ForeignKey("message_threads.id"), nullable=False),
        sa.Column("candidate_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("application_id", sa.BigInteger(), sa.ForeignKey("applications.id"), nullable=True),
        sa.Column("requisition_id", sa.BigInteger(), sa.ForeignKey("requisitions.id"), nullable=True),
        sa.Column("direction", sa.String(length=16), nullable=False),
        sa.Column("intent_key", sa.String(length=64), nullable=False),
        sa.Column("purpose_scope", sa.String(length=32), nullable=False),
        sa.Column("sender_type", sa.String(length=16), nullable=False),
        sa.Column("sender_id", sa.String(length=64), nullable=True),
        sa.Column("template_family_key", sa.String(length=100), nullable=True),
        sa.Column("template_version", sa.Integer(), nullable=True),
        sa.Column("template_context_json", sa.JSON(), nullable=True),
        sa.Column("canonical_payload_json", sa.JSON(), nullable=True),
        sa.Column("render_context_json", sa.JSON(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("correlation_id", sa.String(length=64), nullable=True),
        sa.Column("dedupe_scope_key", sa.String(length=160), nullable=True),
        sa.Column("reply_to_message_id", sa.BigInteger(), sa.ForeignKey("messages.id"), nullable=True),
        sa.Column("intent_status", sa.String(length=24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("idempotency_key", name="uq_messages_idempotency_key"),
        sa.Index("ix_messages_thread_created", "thread_id", "created_at"),
        sa.Index("ix_messages_candidate_created", "candidate_id", "created_at"),
        sa.Index("ix_messages_application_intent_created", "application_id", "intent_key", "created_at"),
        sa.Index("ix_messages_dedupe_created", "dedupe_scope_key", "created_at"),
    )

    message_deliveries = sa.Table(
        "message_deliveries",
        metadata,
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("delivery_uuid", sa.String(length=36), nullable=False),
        sa.Column("message_id", sa.BigInteger(), sa.ForeignKey("messages.id"), nullable=False),
        sa.Column("thread_id", sa.BigInteger(), sa.ForeignKey("message_threads.id"), nullable=False),
        sa.Column("candidate_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("application_id", sa.BigInteger(), sa.ForeignKey("applications.id"), nullable=True),
        sa.Column("channel", sa.String(length=32), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("identity_id", sa.BigInteger(), sa.ForeignKey("candidate_channel_identities.id"), nullable=True),
        sa.Column("destination_fingerprint", sa.String(length=160), nullable=True),
        sa.Column("route_order", sa.Integer(), nullable=False),
        sa.Column("channel_attempt_no", sa.Integer(), nullable=False),
        sa.Column("overall_attempt_no", sa.Integer(), nullable=False),
        sa.Column("delivery_status", sa.String(length=24), nullable=False),
        sa.Column("failure_class", sa.String(length=16), nullable=True),
        sa.Column("failure_code", sa.String(length=64), nullable=True),
        sa.Column("provider_message_id", sa.String(length=128), nullable=True),
        sa.Column("provider_correlation_id", sa.String(length=128), nullable=True),
        sa.Column("rendered_payload_json", sa.JSON(), nullable=True),
        sa.Column("request_payload_json", sa.JSON(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=160), nullable=False),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("terminal_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("idempotency_key", name="uq_message_deliveries_idempotency_key"),
        sa.Index("ix_message_deliveries_message_attempt", "message_id", "overall_attempt_no"),
        sa.Index("ix_message_deliveries_candidate_channel_created", "candidate_id", "channel", "created_at"),
        sa.Index("ix_message_deliveries_status_retry", "delivery_status", "next_retry_at"),
        sa.Index("ix_message_deliveries_provider_message", "provider", "provider_message_id"),
    )

    provider_receipts = sa.Table(
        "provider_receipts",
        metadata,
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("receipt_uuid", sa.String(length=36), nullable=False),
        sa.Column("delivery_id", sa.BigInteger(), sa.ForeignKey("message_deliveries.id"), nullable=False),
        sa.Column("message_id", sa.BigInteger(), sa.ForeignKey("messages.id"), nullable=False),
        sa.Column("channel", sa.String(length=32), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("provider_message_id", sa.String(length=128), nullable=True),
        sa.Column("provider_event_id", sa.String(length=160), nullable=True),
        sa.Column("receipt_type", sa.String(length=24), nullable=False),
        sa.Column("provider_status_code", sa.String(length=64), nullable=True),
        sa.Column("provider_status_text", sa.Text(), nullable=True),
        sa.Column("normalized_failure_class", sa.String(length=16), nullable=True),
        sa.Column("normalized_failure_code", sa.String(length=64), nullable=True),
        sa.Column("raw_payload_json", sa.JSON(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Index("ix_provider_receipts_delivery_time", "delivery_id", "occurred_at"),
        sa.Index("ix_provider_receipts_provider_message", "provider", "provider_message_id"),
        sa.Index(
            "uq_provider_receipts_provider_event_present",
            "provider",
            "provider_event_id",
            unique=True,
            sqlite_where=sa.text("provider_event_id IS NOT NULL"),
            postgresql_where=sa.text("provider_event_id IS NOT NULL"),
        ),
    )

    candidate_contact_policies = sa.Table(
        "candidate_contact_policies",
        metadata,
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("candidate_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("application_id", sa.BigInteger(), sa.ForeignKey("applications.id"), nullable=True),
        sa.Column("purpose_scope", sa.String(length=32), nullable=False),
        sa.Column("preferred_channel", sa.String(length=32), nullable=True),
        sa.Column("fallback_order_json", sa.JSON(), nullable=False),
        sa.Column("fallback_enabled", sa.Boolean(), nullable=False),
        sa.Column("consent_status", sa.String(length=24), nullable=False),
        sa.Column("serviceability_status", sa.String(length=24), nullable=False),
        sa.Column("do_not_contact", sa.Boolean(), nullable=False),
        sa.Column("quiet_windows_json", sa.JSON(), nullable=True),
        sa.Column("max_messages_per_day", sa.Integer(), nullable=True),
        sa.Column("min_spacing_minutes", sa.Integer(), nullable=True),
        sa.Column("last_contacted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("policy_version", sa.Integer(), nullable=False),
        sa.Column("updated_by", sa.String(length=64), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Index("ix_candidate_contact_policies_preferred_channel", "preferred_channel"),
        sa.Index("ix_candidate_contact_policies_do_not_contact_updated", "do_not_contact", "updated_at"),
        sa.Index(
            "uq_candidate_contact_policies_candidate_purpose",
            "candidate_id",
            "purpose_scope",
            unique=True,
            sqlite_where=sa.text("application_id IS NULL"),
            postgresql_where=sa.text("application_id IS NULL"),
        ),
        sa.Index(
            "uq_candidate_contact_policies_candidate_application_purpose",
            "candidate_id",
            "application_id",
            "purpose_scope",
            unique=True,
            sqlite_where=sa.text("application_id IS NOT NULL"),
            postgresql_where=sa.text("application_id IS NOT NULL"),
        ),
    )

    channel_health_registry = sa.Table(
        "channel_health_registry",
        metadata,
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("channel", sa.String(length=32), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("runtime_surface", sa.String(length=32), nullable=False),
        sa.Column("health_status", sa.String(length=24), nullable=False),
        sa.Column("failure_domain", sa.String(length=64), nullable=True),
        sa.Column("reason_code", sa.String(length=64), nullable=True),
        sa.Column("reason_text", sa.Text(), nullable=True),
        sa.Column("circuit_state", sa.String(length=24), nullable=False),
        sa.Column("last_probe_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_failure_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_recovered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("probe_payload_json", sa.JSON(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("channel", "provider", "runtime_surface", name="uq_channel_health_registry_channel_provider_surface"),
        sa.Index("ix_channel_health_registry_status_updated", "health_status", "updated_at"),
    )

    return [
        candidate_channel_identities,
        requisitions,
        applications,
        application_events,
        interviews,
        recruiter_tasks,
        dedup_candidate_pairs,
        ai_decision_records,
        candidate_access_tokens,
        candidate_access_sessions,
        message_threads,
        messages,
        message_deliveries,
        provider_receipts,
        candidate_contact_policies,
        channel_health_registry,
    ]


def _add_candidate_journey_bridge_columns(conn: Connection) -> None:
    if not table_exists(conn, "candidate_journey_sessions"):
        return

    if not column_exists(conn, "candidate_journey_sessions", "application_id"):
        conn.execute(
            sa.text(
                "ALTER TABLE candidate_journey_sessions "
                "ADD COLUMN application_id BIGINT REFERENCES applications(id)"
            )
        )
    if not column_exists(conn, "candidate_journey_sessions", "last_access_session_id"):
        conn.execute(
            sa.text(
                "ALTER TABLE candidate_journey_sessions "
                "ADD COLUMN last_access_session_id BIGINT REFERENCES candidate_access_sessions(id)"
            )
        )
    if not column_exists(conn, "candidate_journey_sessions", "last_surface"):
        conn.execute(
            sa.text("ALTER TABLE candidate_journey_sessions ADD COLUMN last_surface VARCHAR(32)")
        )
    if not column_exists(conn, "candidate_journey_sessions", "last_auth_method"):
        conn.execute(
            sa.text("ALTER TABLE candidate_journey_sessions ADD COLUMN last_auth_method VARCHAR(32)")
        )

    if not index_exists(conn, "candidate_journey_sessions", "ix_candidate_journey_sessions_application_status"):
        conn.execute(
            sa.text(
                "CREATE INDEX IF NOT EXISTS ix_candidate_journey_sessions_application_status "
                "ON candidate_journey_sessions (application_id, status)"
            )
        )
    if not index_exists(conn, "candidate_journey_sessions", "ix_candidate_journey_sessions_last_access_session"):
        conn.execute(
            sa.text(
                "CREATE INDEX IF NOT EXISTS ix_candidate_journey_sessions_last_access_session "
                "ON candidate_journey_sessions (last_access_session_id)"
            )
        )


def upgrade(conn: Connection) -> None:
    metadata = sa.MetaData()
    metadata.bind = conn
    tables = _build_tables(metadata)
    metadata.create_all(conn, tables=tables, checkfirst=True)
    _add_candidate_journey_bridge_columns(conn)


def downgrade(conn: Connection) -> None:  # pragma: no cover
    # Additive-only Phase A migration: we intentionally do not drop tables or
    # columns here to avoid destructive rollback semantics.
    return
