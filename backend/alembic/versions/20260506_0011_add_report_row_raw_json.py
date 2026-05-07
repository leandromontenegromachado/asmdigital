"""add report row raw json

Revision ID: 20260506_0011
Revises: 20260428_0010
Create Date: 2026-05-06 16:20:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260506_0011"
down_revision = "20260428_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("report_rows", sa.Column("raw_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    op.drop_column("report_rows", "raw_json")
