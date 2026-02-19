"""add prompt report templates

Revision ID: 20260212_0003
Revises: 20260205_0002
Create Date: 2026-02-12 10:15:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260212_0003"
down_revision = "20260205_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "prompt_report_templates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("connector_id", sa.Integer(), sa.ForeignKey("connectors.id"), nullable=False),
        sa.Column("prompt_text", sa.Text(), nullable=False),
        sa.Column("params_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("schedule_cron", sa.String(length=120), nullable=True),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_prompt_report_templates_connector_id", "prompt_report_templates", ["connector_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_prompt_report_templates_connector_id", table_name="prompt_report_templates")
    op.drop_table("prompt_report_templates")
