"""Add tests, questions, and answer_options tables."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0064_add_test_questions_tables"
down_revision = "0063_add_candidate_rejection_reason"

def upgrade(conn):
    # Tests table
    conn.execute(
        sa.text(
            """
            CREATE TABLE IF NOT EXISTS tests (
                id SERIAL PRIMARY KEY,
                title VARCHAR(255) NOT NULL,
                slug VARCHAR(50) NOT NULL UNIQUE
            )
            """
        )
    )

    # Questions table
    # Note: using jsonb for payload if postgres, but let's stick to standard SQL where possible 
    # or handle dialect specific types. 
    # For simplicity and broad compatibility (like 0001_initial_schema using sa.JSON),
    # I will use sa.JSON type via CreateTable construct or just raw SQL if I know the dialect.
    # Given the project uses raw SQL in some migrations and metadata in others.
    # 0001 used metadata. 0063... let's check.
    
    # I'll use metadata approach as it's cleaner for types.
    metadata = sa.MetaData()
    
    sa.Table(
        "questions",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("test_id", sa.Integer, nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("key", sa.String(50), nullable=True),
        sa.Column("payload", sa.JSON, nullable=True),
        sa.Column("type", sa.String(32), nullable=False, server_default="single_choice"),
        sa.Column("order", sa.Integer, nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["test_id"], ["tests.id"], ondelete="CASCADE"),
    )

    sa.Table(
        "answer_options",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("question_id", sa.Integer, nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("is_correct", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("points", sa.Float, nullable=False, server_default="0.0"),
        sa.ForeignKeyConstraint(["question_id"], ["questions.id"], ondelete="CASCADE"),
    )
    
    # Create tables defined in metadata
    # We skip 'tests' because I created it with raw SQL? No, let's include it here for consistency if not exists.
    # But I already wrote raw SQL for tests. Let's stick to metadata for all to be safe.
    # Actually, I'll remove the raw SQL for tests and use metadata for all 3.
    
    tests = sa.Table(
        "tests",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(50), nullable=False, unique=True),
    )
    
    metadata.create_all(conn)


def downgrade(conn):
    conn.execute(sa.text("DROP TABLE IF EXISTS answer_options"))
    conn.execute(sa.text("DROP TABLE IF EXISTS questions"))
    conn.execute(sa.text("DROP TABLE IF EXISTS tests"))
