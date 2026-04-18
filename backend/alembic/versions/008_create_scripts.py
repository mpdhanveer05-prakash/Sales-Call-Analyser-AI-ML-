"""create scripts table

Revision ID: 008_create_scripts
Revises: 007_create_speech_scores
Create Date: 2026-04-18

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "008_create_scripts"
down_revision: Union[str, None] = "007_create_speech_scores"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "scripts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("rubric", sa.JSON, nullable=False, server_default="'{}'"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_scripts_is_active", "scripts", ["is_active"])


def downgrade() -> None:
    op.drop_index("ix_scripts_is_active", table_name="scripts")
    op.drop_table("scripts")
