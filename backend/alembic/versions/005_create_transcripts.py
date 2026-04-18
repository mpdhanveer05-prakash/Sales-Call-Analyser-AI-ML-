"""create transcripts table

Revision ID: 005_create_transcripts
Revises: 004_create_calls
Create Date: 2026-04-18

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "005_create_transcripts"
down_revision: Union[str, None] = "004_create_calls"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "transcripts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("call_id", UUID(as_uuid=True), sa.ForeignKey("calls.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("language", sa.String(10), nullable=True),
        sa.Column("duration_seconds", sa.Numeric(8, 2), nullable=True),
        sa.Column("segment_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_transcripts_call_id", "transcripts", ["call_id"])


def downgrade() -> None:
    op.drop_index("ix_transcripts_call_id", table_name="transcripts")
    op.drop_table("transcripts")
