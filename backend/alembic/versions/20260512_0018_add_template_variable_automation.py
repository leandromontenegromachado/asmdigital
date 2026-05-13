"""add template variable automation

Revision ID: 20260512_0018
Revises: 20260512_0017
Create Date: 2026-05-12 20:10:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260512_0018"
down_revision = "20260512_0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("notification_templates", sa.Column("variable_automation_id", sa.Integer(), nullable=True))
    op.create_index("ix_notification_templates_variable_automation_id", "notification_templates", ["variable_automation_id"], unique=False)
    op.create_foreign_key(
        "fk_notification_templates_variable_automation_id",
        "notification_templates",
        "automations",
        ["variable_automation_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_notification_templates_variable_automation_id", "notification_templates", type_="foreignkey")
    op.drop_index("ix_notification_templates_variable_automation_id", table_name="notification_templates")
    op.drop_column("notification_templates", "variable_automation_id")
