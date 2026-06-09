"""Add semantic speaker role columns

Revision ID: 018
Revises: 017
Create Date: 2026-06-04

Adds:
  transcript_segments.role              (VARCHAR(32), NOT NULL DEFAULT 'UNKNOWN')
  transcript_segments.role_confidence   (FLOAT, nullable)
  calls.call_topology                   (VARCHAR(64), nullable)
  calls.call_topology_confidence        (FLOAT, nullable)

Back-fills role from existing speaker column for historical rows so the UI
keeps working without re-processing every old call.
"""
from alembic import op
import sqlalchemy as sa


revision = "018"
down_revision = "017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # transcript_segments — add semantic role columns
    op.add_column(
        "transcript_segments",
        sa.Column("role", sa.String(32), nullable=False, server_default="UNKNOWN"),
    )
    op.add_column(
        "transcript_segments",
        sa.Column("role_confidence", sa.Float(), nullable=True),
    )
    op.create_index(
        "ix_transcript_segments_role",
        "transcript_segments",
        ["role"],
    )

    # calls — add topology columns
    op.add_column(
        "calls",
        sa.Column("call_topology", sa.String(64), nullable=True),
    )
    op.add_column(
        "calls",
        sa.Column("call_topology_confidence", sa.Float(), nullable=True),
    )

    # Backfill historical rows so the UI/queries don't see UNKNOWN everywhere
    op.execute(
        "UPDATE transcript_segments SET role = 'HUMAN_AGENT', role_confidence = 0.6 "
        "WHERE speaker = 'AGENT'"
    )
    op.execute(
        "UPDATE transcript_segments SET role = 'HUMAN_CUSTOMER', role_confidence = 0.6 "
        "WHERE speaker = 'CUSTOMER'"
    )
    op.execute(
        "UPDATE transcript_segments SET role = 'AUTO_ATTENDANT', role_confidence = 0.6 "
        "WHERE speaker = 'SYSTEM'"
    )


def downgrade() -> None:
    op.drop_index("ix_transcript_segments_role", table_name="transcript_segments")
    op.drop_column("transcript_segments", "role_confidence")
    op.drop_column("transcript_segments", "role")
    op.drop_column("calls", "call_topology_confidence")
    op.drop_column("calls", "call_topology")
