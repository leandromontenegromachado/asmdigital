"""add assistant command logs

Revision ID: 20260520_0023
Revises: 20260519_0022
Create Date: 2026-05-20 11:05:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260520_0023"
down_revision = "20260519_0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "assistant_command_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.String(length=120), nullable=True),
        sa.Column("user_name", sa.String(length=200), nullable=True),
        sa.Column("channel", sa.String(length=60), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("intent", sa.String(length=80), nullable=True),
        sa.Column("action", sa.String(length=120), nullable=True),
        sa.Column("response_message", sa.Text(), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("raw_payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_assistant_command_logs_id"), "assistant_command_logs", ["id"], unique=False)
    op.create_index("ix_assistant_command_logs_user_id", "assistant_command_logs", ["user_id"], unique=False)
    op.create_index("ix_assistant_command_logs_channel", "assistant_command_logs", ["channel"], unique=False)
    op.create_index("ix_assistant_command_logs_intent", "assistant_command_logs", ["intent"], unique=False)
    op.create_index("ix_assistant_command_logs_action", "assistant_command_logs", ["action"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_assistant_command_logs_action", table_name="assistant_command_logs")
    op.drop_index("ix_assistant_command_logs_intent", table_name="assistant_command_logs")
    op.drop_index("ix_assistant_command_logs_channel", table_name="assistant_command_logs")
    op.drop_index("ix_assistant_command_logs_user_id", table_name="assistant_command_logs")
    op.drop_index(op.f("ix_assistant_command_logs_id"), table_name="assistant_command_logs")
    op.drop_table("assistant_command_logs")
