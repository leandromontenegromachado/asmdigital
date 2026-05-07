"""add actionable notifications

Revision ID: 20260507_0012
Revises: 20260506_0011
Create Date: 2026-05-07 17:10:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260507_0012"
down_revision = "20260506_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("employees", sa.Column("teams_user_id", sa.String(length=200), nullable=True))
    op.add_column("employees", sa.Column("matricula", sa.String(length=80), nullable=True))
    op.add_column("employees", sa.Column("cargo", sa.String(length=120), nullable=True))
    op.add_column("employees", sa.Column("setor", sa.String(length=120), nullable=True))
    op.add_column("employees", sa.Column("recebe_notificacao", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("employees", sa.Column("participa_avaliacao", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("employees", sa.Column("canal_preferencial", sa.String(length=40), nullable=False, server_default="email"))
    op.create_index("ix_employees_matricula", "employees", ["matricula"], unique=True)
    op.create_index("ix_employees_setor", "employees", ["setor"], unique=False)

    op.execute("update employees set setor = department where setor is null and department is not null")
    op.execute("update employees set cargo = position where cargo is null and position is not null")

    op.create_table(
        "notification_templates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("channel", sa.String(length=40), nullable=False, server_default="email"),
        sa.Column("subject", sa.String(length=200), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_notification_templates_id", "notification_templates", ["id"], unique=False)

    op.create_table(
        "notification_rules",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("automation_id", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("send_condition", sa.String(length=120), nullable=True),
        sa.Column("recipient_type", sa.String(length=60), nullable=False, server_default="responsavel"),
        sa.Column("preferred_channel", sa.String(length=40), nullable=False, server_default="email"),
        sa.Column("fallback_channel", sa.String(length=40), nullable=True),
        sa.Column("template_id", sa.Integer(), nullable=True),
        sa.Column("requires_approval", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("notify_manager", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("manager_condition", sa.String(length=120), nullable=True),
        sa.Column("params_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["automation_id"], ["automations.id"]),
        sa.ForeignKeyConstraint(["template_id"], ["notification_templates.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_notification_rules_id", "notification_rules", ["id"], unique=False)
    op.create_index("ix_notification_rules_automation_id", "notification_rules", ["automation_id"], unique=False)

    op.add_column("notifications", sa.Column("execution_id", sa.Integer(), nullable=True))
    op.add_column("notifications", sa.Column("automation_id", sa.Integer(), nullable=True))
    op.add_column("notifications", sa.Column("employee_id", sa.Integer(), nullable=True))
    op.add_column("notifications", sa.Column("recipient", sa.String(length=200), nullable=True))
    op.add_column("notifications", sa.Column("message", sa.Text(), nullable=True))
    op.add_column("notifications", sa.Column("data_envio", sa.DateTime(timezone=True), nullable=True))
    op.add_column("notifications", sa.Column("error", sa.Text(), nullable=True))
    op.add_column("notifications", sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"))
    op.create_foreign_key("fk_notifications_execution_id", "notifications", "automation_runs", ["execution_id"], ["id"])
    op.create_foreign_key("fk_notifications_automation_id", "notifications", "automations", ["automation_id"], ["id"])
    op.create_foreign_key("fk_notifications_employee_id", "notifications", "employees", ["employee_id"], ["id"])
    op.create_index("ix_notifications_execution_id", "notifications", ["execution_id"], unique=False)
    op.create_index("ix_notifications_automation_id", "notifications", ["automation_id"], unique=False)
    op.create_index("ix_notifications_employee_id", "notifications", ["employee_id"], unique=False)
    op.execute("update notifications set recipient = to_ref where recipient is null")
    op.execute("update notifications set message = body where message is null")


def downgrade() -> None:
    op.drop_index("ix_notifications_employee_id", table_name="notifications")
    op.drop_index("ix_notifications_automation_id", table_name="notifications")
    op.drop_index("ix_notifications_execution_id", table_name="notifications")
    op.drop_constraint("fk_notifications_employee_id", "notifications", type_="foreignkey")
    op.drop_constraint("fk_notifications_automation_id", "notifications", type_="foreignkey")
    op.drop_constraint("fk_notifications_execution_id", "notifications", type_="foreignkey")
    op.drop_column("notifications", "attempts")
    op.drop_column("notifications", "error")
    op.drop_column("notifications", "data_envio")
    op.drop_column("notifications", "message")
    op.drop_column("notifications", "recipient")
    op.drop_column("notifications", "employee_id")
    op.drop_column("notifications", "automation_id")
    op.drop_column("notifications", "execution_id")

    op.drop_index("ix_notification_rules_automation_id", table_name="notification_rules")
    op.drop_index("ix_notification_rules_id", table_name="notification_rules")
    op.drop_table("notification_rules")
    op.drop_index("ix_notification_templates_id", table_name="notification_templates")
    op.drop_table("notification_templates")

    op.drop_index("ix_employees_setor", table_name="employees")
    op.drop_index("ix_employees_matricula", table_name="employees")
    op.drop_column("employees", "canal_preferencial")
    op.drop_column("employees", "participa_avaliacao")
    op.drop_column("employees", "recebe_notificacao")
    op.drop_column("employees", "setor")
    op.drop_column("employees", "cargo")
    op.drop_column("employees", "matricula")
    op.drop_column("employees", "teams_user_id")
