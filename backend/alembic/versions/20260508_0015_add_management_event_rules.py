"""add management event rules

Revision ID: 20260508_0015
Revises: 20260508_0014
Create Date: 2026-05-08 16:20:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260508_0015"
down_revision = "20260508_0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "management_event_rules",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("condition_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("action_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_management_event_rules_id", "management_event_rules", ["id"], unique=False)
    op.create_index("ix_management_event_rules_is_active", "management_event_rules", ["is_active"], unique=False)
    op.create_index("ix_management_event_rules_priority", "management_event_rules", ["priority"], unique=False)
    op.create_index("ix_management_event_rules_created_by", "management_event_rules", ["created_by"], unique=False)

    op.create_table(
        "management_event_actions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("rule_id", sa.Integer(), nullable=False),
        sa.Column("management_event_id", sa.Integer(), nullable=False),
        sa.Column("pending_item_id", sa.Integer(), nullable=True),
        sa.Column("action_type", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="executed"),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("action_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("result_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["management_event_id"], ["management_events.id"]),
        sa.ForeignKeyConstraint(["pending_item_id"], ["pending_items.id"]),
        sa.ForeignKeyConstraint(["rule_id"], ["management_event_rules.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_management_event_actions_id", "management_event_actions", ["id"], unique=False)
    op.create_index("ix_management_event_actions_rule_id", "management_event_actions", ["rule_id"], unique=False)
    op.create_index("ix_management_event_actions_management_event_id", "management_event_actions", ["management_event_id"], unique=False)
    op.create_index("ix_management_event_actions_pending_item_id", "management_event_actions", ["pending_item_id"], unique=False)
    op.create_index("ix_management_event_actions_action_type", "management_event_actions", ["action_type"], unique=False)
    op.create_index("ix_management_event_actions_status", "management_event_actions", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_management_event_actions_status", table_name="management_event_actions")
    op.drop_index("ix_management_event_actions_action_type", table_name="management_event_actions")
    op.drop_index("ix_management_event_actions_pending_item_id", table_name="management_event_actions")
    op.drop_index("ix_management_event_actions_management_event_id", table_name="management_event_actions")
    op.drop_index("ix_management_event_actions_rule_id", table_name="management_event_actions")
    op.drop_index("ix_management_event_actions_id", table_name="management_event_actions")
    op.drop_table("management_event_actions")

    op.drop_index("ix_management_event_rules_created_by", table_name="management_event_rules")
    op.drop_index("ix_management_event_rules_priority", table_name="management_event_rules")
    op.drop_index("ix_management_event_rules_is_active", table_name="management_event_rules")
    op.drop_index("ix_management_event_rules_id", table_name="management_event_rules")
    op.drop_table("management_event_rules")
