"""Add sentiment_timeline to summaries, has_keyword_hit to calls, keyword_alerts and call_keyword_hits tables

Revision ID: 016
Revises: 015
Create Date: 2026-04-20
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "016"
down_revision = "015_add_cancelled_status"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add sentiment_timeline column to summaries
    op.add_column("summaries", sa.Column("sentiment_timeline", sa.JSON(), nullable=True))

    # Add has_keyword_hit to calls
    op.add_column("calls", sa.Column("has_keyword_hit", sa.Boolean(), nullable=False, server_default="false"))

    # Create keyword_alerts table
    op.create_table(
        "keyword_alerts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("keyword", sa.String(200), nullable=False, unique=True),
        sa.Column("category", sa.String(50), nullable=False, server_default="CUSTOM"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # Create call_keyword_hits table
    op.create_table(
        "call_keyword_hits",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("call_id", UUID(as_uuid=True), sa.ForeignKey("calls.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("keyword_alert_id", UUID(as_uuid=True), sa.ForeignKey("keyword_alerts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("hit_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sample_quotes", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("call_keyword_hits")
    op.drop_table("keyword_alerts")
    op.drop_column("calls", "has_keyword_hit")
    op.drop_column("summaries", "sentiment_timeline")
