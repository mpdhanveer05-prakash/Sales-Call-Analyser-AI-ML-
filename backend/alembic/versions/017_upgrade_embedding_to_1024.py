"""Upgrade embedding column from 384 to 1024 dimensions (bge-large-en-v1.5)

Revision ID: 017
Revises: 016
Create Date: 2026-06-04

WARNING: Existing 384-dim embeddings will be wiped (set to NULL). After this
migration runs, re-process the index_task for any calls you want re-embedded,
or simply wait — new completed calls embed automatically with the new model.
"""
from alembic import op


revision = "017"
down_revision = "016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # pgvector does not allow ALTER COLUMN TYPE between different vector
    # dimensions; drop and recreate the column with the new dimension.
    op.execute("ALTER TABLE calls DROP COLUMN IF EXISTS embedding")
    op.execute("ALTER TABLE calls ADD COLUMN embedding vector(1024)")


def downgrade() -> None:
    op.execute("ALTER TABLE calls DROP COLUMN IF EXISTS embedding")
    op.execute("ALTER TABLE calls ADD COLUMN embedding vector(384)")
