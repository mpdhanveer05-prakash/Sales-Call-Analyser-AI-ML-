"""create transcript_segments table

Revision ID: 006_create_transcript_segments
Revises: 005_create_transcripts
Create Date: 2026-04-18

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "006_create_transcript_segments"
down_revision: Union[str, None] = "005_create_transcripts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "transcript_segments",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("transcript_id", UUID(as_uuid=True), sa.ForeignKey("transcripts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("speaker", sa.String(20), nullable=False),   # AGENT | CUSTOMER
        sa.Column("start_ms", sa.Integer, nullable=False),
        sa.Column("end_ms", sa.Integer, nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_transcript_segments_transcript_id", "transcript_segments", ["transcript_id"])
    op.create_index("ix_transcript_segments_speaker", "transcript_segments", ["speaker"])
    op.create_index("ix_transcript_segments_start_ms", "transcript_segments", ["start_ms"])


def downgrade() -> None:
    op.drop_index("ix_transcript_segments_start_ms", table_name="transcript_segments")
    op.drop_index("ix_transcript_segments_speaker", table_name="transcript_segments")
    op.drop_index("ix_transcript_segments_transcript_id", table_name="transcript_segments")
    op.drop_table("transcript_segments")
