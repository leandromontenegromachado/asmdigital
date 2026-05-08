"""add management events

Revision ID: 20260508_0013
Revises: 20260507_0012
Create Date: 2026-05-08 11:20:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260508_0013"
down_revision = "20260507_0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "management_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("source_type", sa.String(length=80), nullable=True),
        sa.Column("source_id", sa.String(length=120), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="pending"),
        sa.Column("severity", sa.String(length=40), nullable=False, server_default="medium"),
        sa.Column("responsible_id", sa.Integer(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ignored_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["responsible_id"], ["employees.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_management_events_id", "management_events", ["id"], unique=False)
    op.create_index("ix_management_events_event_type", "management_events", ["event_type"], unique=False)
    op.create_index("ix_management_events_source_type", "management_events", ["source_type"], unique=False)
    op.create_index("ix_management_events_source_id", "management_events", ["source_id"], unique=False)
    op.create_index("ix_management_events_status", "management_events", ["status"], unique=False)
    op.create_index("ix_management_events_severity", "management_events", ["severity"], unique=False)
    op.create_index("ix_management_events_responsible_id", "management_events", ["responsible_id"], unique=False)
    op.create_index("ix_management_events_created_by", "management_events", ["created_by"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_management_events_created_by", table_name="management_events")
    op.drop_index("ix_management_events_responsible_id", table_name="management_events")
    op.drop_index("ix_management_events_severity", table_name="management_events")
    op.drop_index("ix_management_events_status", table_name="management_events")
    op.drop_index("ix_management_events_source_id", table_name="management_events")
    op.drop_index("ix_management_events_source_type", table_name="management_events")
    op.drop_index("ix_management_events_event_type", table_name="management_events")
    op.drop_index("ix_management_events_id", table_name="management_events")
    op.drop_table("management_events")
