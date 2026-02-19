"""add user is_active

Revision ID: 20260205_0002
Revises: 20260205_0001
Create Date: 2026-02-05 16:45:00

"""
from alembic import op
import sqlalchemy as sa

revision = "20260205_0002"
down_revision = "20260205_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")))
    op.alter_column("users", "is_active", server_default=None)


def downgrade() -> None:
    op.drop_column("users", "is_active")
