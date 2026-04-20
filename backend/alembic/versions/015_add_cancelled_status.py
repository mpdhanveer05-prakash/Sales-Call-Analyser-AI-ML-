"""add cancelled status to callstatus enum

Revision ID: 015_add_cancelled_status
Revises: 014_add_performance_indexes
Create Date: 2026-04-20
"""
from typing import Union
from alembic import op

revision: str = "015_add_cancelled_status"
down_revision: Union[str, None] = "014_add_performance_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE callstatus ADD VALUE IF NOT EXISTS 'CANCELLED'")


def downgrade() -> None:
    # PostgreSQL does not support removing enum values; downgrade is a no-op
    pass
