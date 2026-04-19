"""create objections table

Revision ID: 013_create_objections
Revises: 012_create_coaching_clips
Create Date: 2026-04-18

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "013_create_objections"
down_revision: Union[str, None] = "012_create_coaching_clips"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "objections",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("call_id", UUID(as_uuid=True), sa.ForeignKey("calls.id", ondelete="CASCADE"), nullable=False),
        sa.Column("timestamp_ms", sa.Integer, nullable=False),
        sa.Column("objection_type", sa.String(50), nullable=False),
        sa.Column("quote", sa.Text, nullable=False),
        sa.Column("resolved", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_objections_call_id", "objections", ["call_id"])


def downgrade() -> None:
    op.drop_index("ix_objections_call_id", table_name="objections")
    op.drop_table("objections")
