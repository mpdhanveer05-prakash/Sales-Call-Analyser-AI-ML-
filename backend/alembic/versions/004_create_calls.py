"""create calls table

Revision ID: 004_create_calls
Revises: 003_create_agents
Create Date: 2026-04-18

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID, ENUM as PG_ENUM

revision: str = "004_create_calls"
down_revision: Union[str, None] = "003_create_agents"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE callstatus AS ENUM (
                'QUEUED', 'TRANSCRIBING', 'ANALYZING', 'SCORING', 'COMPLETED', 'FAILED'
            );
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
    """)
    op.create_table(
        "calls",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("agent_id", UUID(as_uuid=True), sa.ForeignKey("agents.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("uploaded_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("audio_url", sa.Text, nullable=False),
        sa.Column("original_filename", sa.String(500), nullable=False),
        sa.Column("file_size_bytes", sa.Integer, nullable=True),
        sa.Column("status", PG_ENUM("QUEUED", "TRANSCRIBING", "ANALYZING", "SCORING", "COMPLETED", "FAILED", name="callstatus", create_type=False), nullable=False, server_default="QUEUED"),
        sa.Column("duration_seconds", sa.Integer, nullable=True),
        sa.Column("call_date", sa.Date, nullable=False),
        sa.Column("disposition", sa.String(50), nullable=True),
        sa.Column("speech_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("sales_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_calls_agent_id", "calls", ["agent_id"])
    op.create_index("ix_calls_status", "calls", ["status"])
    op.create_index("ix_calls_call_date", "calls", ["call_date"])


def downgrade() -> None:
    op.drop_index("ix_calls_call_date", table_name="calls")
    op.drop_index("ix_calls_status", table_name="calls")
    op.drop_index("ix_calls_agent_id", table_name="calls")
    op.drop_table("calls")
    op.execute("DROP TYPE IF EXISTS callstatus")
