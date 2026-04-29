"""rebuild evaluation module for final performance MVP

Revision ID: 20260427_0007
Revises: 20260424_0006
Create Date: 2026-04-27 00:00:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260427_0007"
down_revision = "20260424_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_table("evaluation_calibrations")
    op.drop_table("evaluation_scores")
    op.drop_table("evaluation_cycles")

    op.create_table(
        "evaluation_cycles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="RASCUNHO"),
        sa.Column("performance_weight", sa.Float(), nullable=False, server_default="0.45"),
        sa.Column("behavior_weight", sa.Float(), nullable=False, server_default="0.35"),
        sa.Column("potential_weight", sa.Float(), nullable=False, server_default="0.20"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_evaluation_cycles_id", "evaluation_cycles", ["id"])

    op.create_table(
        "employees",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("email", sa.String(length=200), nullable=False),
        sa.Column("department", sa.String(length=120), nullable=True),
        sa.Column("position", sa.String(length=120), nullable=True),
        sa.Column("manager_id", sa.Integer(), sa.ForeignKey("employees.id"), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("email", name="uq_employees_email"),
    )
    op.create_index("ix_employees_id", "employees", ["id"])
    op.create_index("ix_employees_email", "employees", ["email"])
    op.create_index("ix_employees_department", "employees", ["department"])

    op.create_table(
        "performance_indicators",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("cycle_id", sa.Integer(), sa.ForeignKey("evaluation_cycles.id"), nullable=False),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id"), nullable=False),
        sa.Column("rpm_original", sa.Float(), nullable=True),
        sa.Column("rpm_normalized", sa.Float(), nullable=True),
        sa.Column("ihpe_original", sa.Float(), nullable=True),
        sa.Column("ihpe_normalized", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("cycle_id", "employee_id", name="uq_performance_indicator_cycle_employee"),
    )
    op.create_index("ix_performance_indicators_id", "performance_indicators", ["id"])
    op.create_index("ix_performance_indicators_cycle_id", "performance_indicators", ["cycle_id"])
    op.create_index("ix_performance_indicators_employee_id", "performance_indicators", ["employee_id"])

    op.create_table(
        "reviews_360",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("cycle_id", sa.Integer(), sa.ForeignKey("evaluation_cycles.id"), nullable=False),
        sa.Column("evaluator_id", sa.Integer(), sa.ForeignKey("employees.id"), nullable=False),
        sa.Column("evaluated_id", sa.Integer(), sa.ForeignKey("employees.id"), nullable=False),
        sa.Column("relation_type", sa.String(length=30), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_reviews_360_id", "reviews_360", ["id"])
    op.create_index("ix_reviews_360_cycle_id", "reviews_360", ["cycle_id"])
    op.create_index("ix_reviews_360_evaluator_id", "reviews_360", ["evaluator_id"])
    op.create_index("ix_reviews_360_evaluated_id", "reviews_360", ["evaluated_id"])
    op.create_index("ix_reviews_360_relation_type", "reviews_360", ["relation_type"])

    op.create_table(
        "potential_scores",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("cycle_id", sa.Integer(), sa.ForeignKey("evaluation_cycles.id"), nullable=False),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id"), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("cycle_id", "employee_id", name="uq_potential_score_cycle_employee"),
    )
    op.create_index("ix_potential_scores_id", "potential_scores", ["id"])
    op.create_index("ix_potential_scores_cycle_id", "potential_scores", ["cycle_id"])
    op.create_index("ix_potential_scores_employee_id", "potential_scores", ["employee_id"])

    op.create_table(
        "evaluation_scores",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("cycle_id", sa.Integer(), sa.ForeignKey("evaluation_cycles.id"), nullable=False),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id"), nullable=False),
        sa.Column("performance_score", sa.Float(), nullable=True),
        sa.Column("behavior_score", sa.Float(), nullable=True),
        sa.Column("potential_score", sa.Float(), nullable=True),
        sa.Column("preliminary_final_score", sa.Float(), nullable=True),
        sa.Column("suggested_category", sa.String(length=40), nullable=True),
        sa.Column("final_category", sa.String(length=40), nullable=True),
        sa.Column("nine_box_position", sa.String(length=40), nullable=True),
        sa.Column("calibration_justification", sa.Text(), nullable=True),
        sa.Column("calibrated_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("calibrated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("cycle_id", "employee_id", name="uq_evaluation_score_cycle_employee"),
    )
    op.create_index("ix_evaluation_scores_id", "evaluation_scores", ["id"])
    op.create_index("ix_evaluation_scores_cycle_id", "evaluation_scores", ["cycle_id"])
    op.create_index("ix_evaluation_scores_employee_id", "evaluation_scores", ["employee_id"])

    op.create_table(
        "evaluation_alerts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("cycle_id", sa.Integer(), sa.ForeignKey("evaluation_cycles.id"), nullable=False),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id"), nullable=False),
        sa.Column("alert_type", sa.String(length=60), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
    )
    op.create_index("ix_evaluation_alerts_id", "evaluation_alerts", ["id"])
    op.create_index("ix_evaluation_alerts_cycle_id", "evaluation_alerts", ["cycle_id"])
    op.create_index("ix_evaluation_alerts_employee_id", "evaluation_alerts", ["employee_id"])
    op.create_index("ix_evaluation_alerts_alert_type", "evaluation_alerts", ["alert_type"])

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("entity_type", sa.String(length=100), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=True),
        sa.Column("old_value", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("new_value", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_audit_logs_id", "audit_logs", ["id"])
    op.create_index("ix_audit_logs_user_id", "audit_logs", ["user_id"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_entity_type", "audit_logs", ["entity_type"])
    op.create_index("ix_audit_logs_entity_id", "audit_logs", ["entity_id"])


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("evaluation_alerts")
    op.drop_table("evaluation_scores")
    op.drop_table("potential_scores")
    op.drop_table("reviews_360")
    op.drop_table("performance_indicators")
    op.drop_table("employees")
    op.drop_table("evaluation_cycles")
