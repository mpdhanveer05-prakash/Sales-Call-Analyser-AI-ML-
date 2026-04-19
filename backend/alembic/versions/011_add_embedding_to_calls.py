"""add embedding column to calls table

Revision ID: 011_add_embedding_to_calls
Revises: 010_create_summaries
Create Date: 2026-04-19

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision: str = "011_add_embedding_to_calls"
down_revision: Union[str, None] = "010_create_summaries"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE calls ADD COLUMN IF NOT EXISTS embedding vector(384)")


def downgrade() -> None:
    op.execute("ALTER TABLE calls DROP COLUMN IF EXISTS embedding")
