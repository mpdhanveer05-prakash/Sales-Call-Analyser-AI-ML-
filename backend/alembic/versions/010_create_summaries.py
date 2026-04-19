"""create summaries table

Revision ID: 010_create_summaries
Revises: 009_create_sales_scores
Create Date: 2026-04-18

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "010_create_summaries"
down_revision: Union[str, None] = "009_create_sales_scores"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "summaries",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("call_id", UUID(as_uuid=True), sa.ForeignKey("calls.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("executive_summary", sa.Text, nullable=False),
        sa.Column("key_moments", sa.JSON, nullable=False, server_default=sa.text("'[]'")),
        sa.Column("coaching_suggestions", sa.JSON, nullable=False, server_default=sa.text("'[]'")),
        sa.Column("disposition_confidence", sa.Numeric(4, 3), nullable=True),
        sa.Column("disposition_reasoning", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_summaries_call_id", "summaries", ["call_id"])


def downgrade() -> None:
    op.drop_index("ix_summaries_call_id", table_name="summaries")
    op.drop_table("summaries")
