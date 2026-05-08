"""add pending items

Revision ID: 20260508_0014
Revises: 20260508_0013
Create Date: 2026-05-08 12:40:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260508_0014"
down_revision = "20260508_0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pending_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="open"),
        sa.Column("priority", sa.String(length=40), nullable=False, server_default="medium"),
        sa.Column("source_type", sa.String(length=80), nullable=True),
        sa.Column("source_id", sa.String(length=120), nullable=True),
        sa.Column("management_event_id", sa.Integer(), nullable=True),
        sa.Column("responsible_id", sa.Integer(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ignored_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("escalated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reopened_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["management_event_id"], ["management_events.id"]),
        sa.ForeignKeyConstraint(["responsible_id"], ["employees.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_pending_items_id", "pending_items", ["id"], unique=False)
    op.create_index("ix_pending_items_status", "pending_items", ["status"], unique=False)
    op.create_index("ix_pending_items_priority", "pending_items", ["priority"], unique=False)
    op.create_index("ix_pending_items_source_type", "pending_items", ["source_type"], unique=False)
    op.create_index("ix_pending_items_source_id", "pending_items", ["source_id"], unique=False)
    op.create_index("ix_pending_items_management_event_id", "pending_items", ["management_event_id"], unique=False)
    op.create_index("ix_pending_items_responsible_id", "pending_items", ["responsible_id"], unique=False)
    op.create_index("ix_pending_items_created_by", "pending_items", ["created_by"], unique=False)
    op.create_index("ix_pending_items_due_date", "pending_items", ["due_date"], unique=False)

    op.create_table(
        "pending_item_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("pending_item_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=60), nullable=False),
        sa.Column("old_status", sa.String(length=40), nullable=True),
        sa.Column("new_status", sa.String(length=40), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("actor_id", sa.Integer(), nullable=True),
        sa.Column("payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["pending_item_id"], ["pending_items.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_pending_item_events_id", "pending_item_events", ["id"], unique=False)
    op.create_index("ix_pending_item_events_pending_item_id", "pending_item_events", ["pending_item_id"], unique=False)
    op.create_index("ix_pending_item_events_event_type", "pending_item_events", ["event_type"], unique=False)
    op.create_index("ix_pending_item_events_actor_id", "pending_item_events", ["actor_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_pending_item_events_actor_id", table_name="pending_item_events")
    op.drop_index("ix_pending_item_events_event_type", table_name="pending_item_events")
    op.drop_index("ix_pending_item_events_pending_item_id", table_name="pending_item_events")
    op.drop_index("ix_pending_item_events_id", table_name="pending_item_events")
    op.drop_table("pending_item_events")

    op.drop_index("ix_pending_items_due_date", table_name="pending_items")
    op.drop_index("ix_pending_items_created_by", table_name="pending_items")
    op.drop_index("ix_pending_items_responsible_id", table_name="pending_items")
    op.drop_index("ix_pending_items_management_event_id", table_name="pending_items")
    op.drop_index("ix_pending_items_source_id", table_name="pending_items")
    op.drop_index("ix_pending_items_source_type", table_name="pending_items")
    op.drop_index("ix_pending_items_priority", table_name="pending_items")
    op.drop_index("ix_pending_items_status", table_name="pending_items")
    op.drop_index("ix_pending_items_id", table_name="pending_items")
    op.drop_table("pending_items")
