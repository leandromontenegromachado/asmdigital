"""add weekdays to fala ai reminders

Revision ID: 20260320_0005
Revises: 20260318_0004
Create Date: 2026-03-20 09:30:00

"""
from alembic import op
import sqlalchemy as sa


revision = "20260320_0005"
down_revision = "20260318_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "fala_ai_reminders",
        sa.Column("dias_semana", sa.String(length=32), nullable=False, server_default="1,2,3,4,5"),
    )


def downgrade() -> None:
    op.drop_column("fala_ai_reminders", "dias_semana")
