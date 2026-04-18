"""create sales_scores table

Revision ID: 009_create_sales_scores
Revises: 008_create_scripts
Create Date: 2026-04-18

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "009_create_sales_scores"
down_revision: Union[str, None] = "008_create_scripts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "sales_scores",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("call_id", UUID(as_uuid=True), sa.ForeignKey("calls.id", ondelete="CASCADE"), nullable=False, unique=True),
        # LLM dimension scores (0-100, derived from 0-10 × 10)
        sa.Column("greeting", sa.Numeric(5, 1), nullable=False),
        sa.Column("rapport", sa.Numeric(5, 1), nullable=False),
        sa.Column("discovery", sa.Numeric(5, 1), nullable=False),
        sa.Column("value_explanation", sa.Numeric(5, 1), nullable=False),
        sa.Column("objection_handling", sa.Numeric(5, 1), nullable=False),
        sa.Column("script_adherence", sa.Numeric(5, 1), nullable=False),
        sa.Column("closing", sa.Numeric(5, 1), nullable=False),
        sa.Column("compliance", sa.Numeric(5, 1), nullable=False),
        sa.Column("composite", sa.Numeric(5, 1), nullable=False),
        # Per-dimension justifications and quotes from the LLM
        sa.Column("details", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_sales_scores_call_id", "sales_scores", ["call_id"])


def downgrade() -> None:
    op.drop_index("ix_sales_scores_call_id", table_name="sales_scores")
    op.drop_table("sales_scores")
