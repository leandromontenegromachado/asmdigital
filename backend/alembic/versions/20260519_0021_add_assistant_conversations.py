"""add assistant conversations

Revision ID: 20260519_0021
Revises: 20260513_0019
Create Date: 2026-05-19 12:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260519_0021"
down_revision = "20260513_0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("telegram_chat_id", sa.String(length=80), nullable=True))
    op.add_column("users", sa.Column("telegram_username", sa.String(length=120), nullable=True))
    op.create_index("ix_users_telegram_chat_id", "users", ["telegram_chat_id"], unique=True)

    op.create_table(
        "assistant_conversations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("channel", sa.String(length=40), nullable=False),
        sa.Column("external_chat_id", sa.String(length=120), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("state_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_assistant_conversations_id", "assistant_conversations", ["id"], unique=False)
    op.create_index("ix_assistant_conversations_channel", "assistant_conversations", ["channel"], unique=False)
    op.create_index("ix_assistant_conversations_external_chat_id", "assistant_conversations", ["external_chat_id"], unique=False)
    op.create_index("ix_assistant_conversations_user_id", "assistant_conversations", ["user_id"], unique=False)

    op.create_table(
        "assistant_messages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("conversation_id", sa.Integer(), nullable=False),
        sa.Column("direction", sa.String(length=20), nullable=False),
        sa.Column("message_type", sa.String(length=40), nullable=False),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("raw_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["conversation_id"], ["assistant_conversations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_assistant_messages_id", "assistant_messages", ["id"], unique=False)
    op.create_index("ix_assistant_messages_conversation_id", "assistant_messages", ["conversation_id"], unique=False)

    op.create_table(
        "assistant_actions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("conversation_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("action_type", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("result_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["conversation_id"], ["assistant_conversations.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_assistant_actions_id", "assistant_actions", ["id"], unique=False)
    op.create_index("ix_assistant_actions_conversation_id", "assistant_actions", ["conversation_id"], unique=False)
    op.create_index("ix_assistant_actions_user_id", "assistant_actions", ["user_id"], unique=False)
    op.create_index("ix_assistant_actions_action_type", "assistant_actions", ["action_type"], unique=False)
    op.create_index("ix_assistant_actions_status", "assistant_actions", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_assistant_actions_status", table_name="assistant_actions")
    op.drop_index("ix_assistant_actions_action_type", table_name="assistant_actions")
    op.drop_index("ix_assistant_actions_user_id", table_name="assistant_actions")
    op.drop_index("ix_assistant_actions_conversation_id", table_name="assistant_actions")
    op.drop_index("ix_assistant_actions_id", table_name="assistant_actions")
    op.drop_table("assistant_actions")

    op.drop_index("ix_assistant_messages_conversation_id", table_name="assistant_messages")
    op.drop_index("ix_assistant_messages_id", table_name="assistant_messages")
    op.drop_table("assistant_messages")

    op.drop_index("ix_assistant_conversations_user_id", table_name="assistant_conversations")
    op.drop_index("ix_assistant_conversations_external_chat_id", table_name="assistant_conversations")
    op.drop_index("ix_assistant_conversations_channel", table_name="assistant_conversations")
    op.drop_index("ix_assistant_conversations_id", table_name="assistant_conversations")
    op.drop_table("assistant_conversations")

    op.drop_index("ix_users_telegram_chat_id", table_name="users")
    op.drop_column("users", "telegram_username")
    op.drop_column("users", "telegram_chat_id")
