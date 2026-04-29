"""add evaluation module tables

Revision ID: 20260424_0006
Revises: 20260320_0005
Create Date: 2026-04-24 21:45:00

"""
from alembic import op
import sqlalchemy as sa


revision = "20260424_0006"
down_revision = "20260320_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "evaluation_cycles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="OPEN"),
        sa.Column("top_n", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("min_score_360", sa.Float(), nullable=False, server_default="70"),
        sa.Column("weight_360", sa.Float(), nullable=False, server_default="0.35"),
        sa.Column("weight_rpm", sa.Float(), nullable=False, server_default="0.20"),
        sa.Column("weight_ihpe", sa.Float(), nullable=False, server_default="0.20"),
        sa.Column("weight_project", sa.Float(), nullable=False, server_default="0.15"),
        sa.Column("weight_evolution", sa.Float(), nullable=False, server_default="0.10"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_evaluation_cycles_id", "evaluation_cycles", ["id"])

    op.create_table(
        "evaluation_scores",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("cycle_id", sa.Integer(), sa.ForeignKey("evaluation_cycles.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("score_360", sa.Float(), nullable=False, server_default="0"),
        sa.Column("rpm", sa.Float(), nullable=False, server_default="0"),
        sa.Column("ihpe", sa.Float(), nullable=False, server_default="0"),
        sa.Column("project_impact", sa.Float(), nullable=False, server_default="0"),
        sa.Column("evolution", sa.Float(), nullable=False, server_default="0"),
        sa.Column("final_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("is_eligible", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("eligibility_reason", sa.String(length=300), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("cycle_id", "user_id", name="uq_evaluation_score_cycle_user"),
    )
    op.create_index("ix_evaluation_scores_id", "evaluation_scores", ["id"])
    op.create_index("ix_evaluation_scores_cycle_id", "evaluation_scores", ["cycle_id"])
    op.create_index("ix_evaluation_scores_user_id", "evaluation_scores", ["user_id"])

    op.create_table(
        "evaluation_calibrations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("cycle_id", sa.Integer(), sa.ForeignKey("evaluation_cycles.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("manager_decision", sa.String(length=50), nullable=False, server_default="Sem decisao"),
        sa.Column("justification", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("cycle_id", "user_id", name="uq_evaluation_calibration_cycle_user"),
    )
    op.create_index("ix_evaluation_calibrations_id", "evaluation_calibrations", ["id"])
    op.create_index("ix_evaluation_calibrations_cycle_id", "evaluation_calibrations", ["cycle_id"])
    op.create_index("ix_evaluation_calibrations_user_id", "evaluation_calibrations", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_evaluation_calibrations_user_id", table_name="evaluation_calibrations")
    op.drop_index("ix_evaluation_calibrations_cycle_id", table_name="evaluation_calibrations")
    op.drop_index("ix_evaluation_calibrations_id", table_name="evaluation_calibrations")
    op.drop_table("evaluation_calibrations")

    op.drop_index("ix_evaluation_scores_user_id", table_name="evaluation_scores")
    op.drop_index("ix_evaluation_scores_cycle_id", table_name="evaluation_scores")
    op.drop_index("ix_evaluation_scores_id", table_name="evaluation_scores")
    op.drop_table("evaluation_scores")

    op.drop_index("ix_evaluation_cycles_id", table_name="evaluation_cycles")
    op.drop_table("evaluation_cycles")
