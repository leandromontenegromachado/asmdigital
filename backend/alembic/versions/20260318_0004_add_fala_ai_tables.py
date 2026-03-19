"""add fala ai tables

Revision ID: 20260318_0004
Revises: 20260212_0003
Create Date: 2026-03-18 10:30:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260318_0004"
down_revision = "20260212_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "fala_ai_checkins",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("tipo", sa.String(length=40), nullable=False, server_default="manual"),
        sa.Column("origem", sa.String(length=40), nullable=False, server_default="web"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_fala_ai_checkins_user_id", "fala_ai_checkins", ["user_id"], unique=False)
    op.create_index("ix_fala_ai_checkins_created_at", "fala_ai_checkins", ["created_at"], unique=False)

    op.create_table(
        "fala_ai_reminders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("mensagem", sa.Text(), nullable=False),
        sa.Column("horario", sa.Time(), nullable=False),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "fala_ai_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("evento", sa.String(length=120), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_fala_ai_logs_evento", "fala_ai_logs", ["evento"], unique=False)
    op.create_index("ix_fala_ai_logs_created_at", "fala_ai_logs", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_fala_ai_logs_created_at", table_name="fala_ai_logs")
    op.drop_index("ix_fala_ai_logs_evento", table_name="fala_ai_logs")
    op.drop_table("fala_ai_logs")

    op.drop_table("fala_ai_reminders")

    op.drop_index("ix_fala_ai_checkins_created_at", table_name="fala_ai_checkins")
    op.drop_index("ix_fala_ai_checkins_user_id", table_name="fala_ai_checkins")
    op.drop_table("fala_ai_checkins")
