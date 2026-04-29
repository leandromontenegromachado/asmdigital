"""add evaluation rh data

Revision ID: 20260428_0010
Revises: 20260428_0009
Create Date: 2026-04-28 16:30:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260428_0010"
down_revision = "20260428_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "employee_rh_data",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("cycle_id", sa.Integer(), sa.ForeignKey("evaluation_cycles.id"), nullable=False),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id"), nullable=False),
        sa.Column("career_level", sa.Integer(), nullable=True),
        sa.Column("last_merit_date", sa.Date(), nullable=True),
        sa.Column("admission_date", sa.Date(), nullable=True),
        sa.Column("is_level_one_separate_budget", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("eligible_for_merit", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("eligibility_reason", sa.Text(), nullable=True),
        sa.Column("raw_data_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("cycle_id", "employee_id", name="uq_employee_rh_data_cycle_employee"),
    )
    op.create_index("ix_employee_rh_data_id", "employee_rh_data", ["id"])
    op.create_index("ix_employee_rh_data_cycle_id", "employee_rh_data", ["cycle_id"])
    op.create_index("ix_employee_rh_data_employee_id", "employee_rh_data", ["employee_id"])


def downgrade() -> None:
    op.drop_table("employee_rh_data")
