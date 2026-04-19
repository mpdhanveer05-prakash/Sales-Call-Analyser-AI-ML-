"""add performance indexes on calls table

Revision ID: 014_add_performance_indexes
Revises: 013_create_objections
Create Date: 2026-04-18

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "014_add_performance_indexes"
down_revision: Union[str, None] = "013_create_objections"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_calls_agent_status_date",
        "calls",
        ["agent_id", "status", sa.text("call_date DESC")],
        postgresql_ops={"call_date": "DESC"},
    )
    op.create_index(
        "ix_calls_status_date",
        "calls",
        ["status", sa.text("call_date DESC")],
        postgresql_ops={"call_date": "DESC"},
    )


def downgrade() -> None:
    op.drop_index("ix_calls_status_date", table_name="calls")
    op.drop_index("ix_calls_agent_status_date", table_name="calls")
