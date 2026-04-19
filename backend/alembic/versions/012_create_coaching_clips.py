"""create coaching_clips table

Revision ID: 012_create_coaching_clips
Revises: 011_add_embedding_to_calls
Create Date: 2026-04-18

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "012_create_coaching_clips"
down_revision: Union[str, None] = "011_add_embedding_to_calls"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "coaching_clips",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("call_id", UUID(as_uuid=True), sa.ForeignKey("calls.id", ondelete="CASCADE"), nullable=False),
        sa.Column("start_ms", sa.Integer, nullable=False),
        sa.Column("end_ms", sa.Integer, nullable=False),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("reason", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_coaching_clips_call_id", "coaching_clips", ["call_id"])


def downgrade() -> None:
    op.drop_index("ix_coaching_clips_call_id", table_name="coaching_clips")
    op.drop_table("coaching_clips")
