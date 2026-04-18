"""create speech_scores table

Revision ID: 007_create_speech_scores
Revises: 006_create_transcript_segments
Create Date: 2026-04-18

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "007_create_speech_scores"
down_revision: Union[str, None] = "006_create_transcript_segments"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "speech_scores",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("call_id", UUID(as_uuid=True), sa.ForeignKey("calls.id", ondelete="CASCADE"), nullable=False, unique=True),
        # Dimension scores (0-100)
        sa.Column("pronunciation", sa.Numeric(5, 1), nullable=False),
        sa.Column("intonation", sa.Numeric(5, 1), nullable=False),
        sa.Column("fluency", sa.Numeric(5, 1), nullable=False),
        sa.Column("grammar", sa.Numeric(5, 1), nullable=False),
        sa.Column("vocabulary", sa.Numeric(5, 1), nullable=False),
        sa.Column("pace", sa.Numeric(5, 1), nullable=False),
        sa.Column("clarity", sa.Numeric(5, 1), nullable=False),
        sa.Column("filler_score", sa.Numeric(5, 1), nullable=False),
        sa.Column("composite", sa.Numeric(5, 1), nullable=False),
        # Raw metrics for audit / re-scoring
        sa.Column("fillers_per_min", sa.Numeric(6, 2), nullable=True),
        sa.Column("pace_wpm", sa.Numeric(6, 1), nullable=True),
        sa.Column("talk_ratio", sa.Numeric(5, 4), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_speech_scores_call_id", "speech_scores", ["call_id"])


def downgrade() -> None:
    op.drop_index("ix_speech_scores_call_id", table_name="speech_scores")
    op.drop_table("speech_scores")
