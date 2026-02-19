"""initial

Revision ID: 20260205_0001
Revises: 
Create Date: 2026-02-05 12:00:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20260205_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("email", sa.String(length=200), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=50), nullable=False, server_default="admin"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "connectors",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("type", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("config_json", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "mappings",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("connector_id", sa.Integer, sa.ForeignKey("connectors.id"), nullable=True),
        sa.Column("mapping_type", sa.String(length=80), nullable=False),
        sa.Column("rules_json", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_mappings_mapping_type", "mappings", ["mapping_type"], unique=False)

    op.create_table(
        "reports",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("type", sa.String(length=80), nullable=False),
        sa.Column("params_json", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("generated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="completed"),
        sa.Column("file_path", sa.String(length=500), nullable=True),
    )
    op.create_index("ix_reports_type", "reports", ["type"], unique=False)

    op.create_table(
        "report_rows",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("report_id", sa.Integer, sa.ForeignKey("reports.id"), nullable=False),
        sa.Column("cliente", sa.String(length=200), nullable=True),
        sa.Column("sistema", sa.String(length=200), nullable=True),
        sa.Column("entrega", sa.String(length=200), nullable=True),
        sa.Column("source_ref", sa.String(length=120), nullable=True),
        sa.Column("source_url", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_report_rows_report_id", "report_rows", ["report_id"], unique=False)

    op.create_table(
        "automations",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("key", sa.String(length=120), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("schedule_cron", sa.String(length=120), nullable=True),
        sa.Column("is_enabled", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("params_json", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_automations_key", "automations", ["key"], unique=True)

    op.create_table(
        "automation_runs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("automation_id", sa.Integer, sa.ForeignKey("automations.id"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="running"),
        sa.Column("summary_json", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("error_text", sa.Text, nullable=True),
    )
    op.create_index("ix_automation_runs_automation_id", "automation_runs", ["automation_id"], unique=False)

    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("channel", sa.String(length=80), nullable=False),
        sa.Column("to_ref", sa.String(length=200), nullable=True),
        sa.Column("subject", sa.String(length=200), nullable=True),
        sa.Column("body", sa.Text, nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("simulation", sa.Boolean, nullable=False, server_default=sa.text("false")),
    )


def downgrade() -> None:
    op.drop_table("notifications")
    op.drop_index("ix_automation_runs_automation_id", table_name="automation_runs")
    op.drop_table("automation_runs")
    op.drop_index("ix_automations_key", table_name="automations")
    op.drop_table("automations")
    op.drop_index("ix_report_rows_report_id", table_name="report_rows")
    op.drop_table("report_rows")
    op.drop_index("ix_reports_type", table_name="reports")
    op.drop_table("reports")
    op.drop_index("ix_mappings_mapping_type", table_name="mappings")
    op.drop_table("mappings")
    op.drop_table("connectors")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
