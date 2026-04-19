"""create users table

Revision ID: 002_create_users
Revises: 001_create_teams
Create Date: 2026-04-18

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID, ENUM as PG_ENUM

revision: str = "002_create_users"
down_revision: Union[str, None] = "001_create_teams"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Use postgresql.ENUM with create_type=False — the DO block handles creation
    # idempotently, and PG_ENUM skips dialect adaptation that strips create_type.
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE userrole AS ENUM ('ADMIN', 'MANAGER', 'AGENT');
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
    """)
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("role", PG_ENUM("ADMIN", "MANAGER", "AGENT", name="userrole", create_type=False), nullable=False, server_default="AGENT"),
        sa.Column("team_id", UUID(as_uuid=True), sa.ForeignKey("teams.id", ondelete="SET NULL"), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
    op.execute("DROP TYPE IF EXISTS userrole")
